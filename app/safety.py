"""Input validation and defense-in-depth networking checks.

Not a replacement for an egress firewall. Non-Python subprocesses and administrator-
configured proxies must be isolated at the operating-system/network layer in production.
"""
from contextlib import contextmanager
import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

PLATFORMS = {
    'YouTube': ('youtube.com', 'youtu.be'),
    'X / Twitter': ('x.com', 'twitter.com'),
    'TikTok': ('tiktok.com',),
    'Instagram': ('instagram.com',),
    'Facebook': ('facebook.com', 'fb.watch'),
    'Vimeo': ('vimeo.com',),
    '哔哩哔哩': ('bilibili.com', 'b23.tv'),
    'Dailymotion': ('dailymotion.com', 'dai.ly'),
    'Reddit': ('reddit.com', 'redd.it'),
    'Twitch': ('twitch.tv',),
}

# Share short links that no allowed yt-dlp extractor claims directly (the generic
# extractor is disabled). The worker expands them with one guarded request first.
SHORT_LINK_HOSTS = ('b23.tv', 'fb.watch')


class UserError(Exception):
    def __init__(self, message: str, code: str = 'INVALID_REQUEST', status: int = 400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.split('%')[0])
        if getattr(ip, 'ipv4_mapped', None):
            ip = ip.ipv4_mapped
        # Also exclude transition mechanisms which can embed a non-public IPv4.
        return ip.is_global and not ip.is_multicast and not (
            ip.version == 6 and (ip.sixtofour is not None or ip.teredo is not None)
        )
    except ValueError:
        return False


def normalize_url(text: str) -> tuple[str, str]:
    if not isinstance(text, str) or len(text) > 4096:
        raise UserError('链接内容过长，请只粘贴单个视频链接。')
    matches = re.findall(r'https?://[^\s<>"\u3000]+', text.strip(), re.I)
    if not matches:
        raise UserError('请粘贴以 https:// 或 http:// 开头的视频链接。')
    if len(matches) != 1:
        raise UserError('一次请只解析一个视频链接。')
    url = matches[0].rstrip('。，、！；）)]}〉》\'')
    if any(ord(c) < 32 for c in url) or '\\' in url:
        raise UserError('链接包含无效字符。')
    try:
        parts = urlsplit(url)
        hostname = (parts.hostname or '').lower().rstrip('.').encode('idna').decode('ascii')
        if parts.username or parts.password or parts.port not in (None, 80, 443):
            raise ValueError
    except (ValueError, UnicodeError):
        raise UserError('链接格式不正确，不支持自定义端口或带账号密码的地址。')
    platform = next((name for name, domains in PLATFORMS.items()
                     if any(hostname == d or hostname.endswith('.' + d) for d in domains)), None)
    if not platform:
        raise UserError('暂不支持这个域名。请使用支持平台的视频原始链接。', 'UNSUPPORTED_SITE')
    if not parts.path or parts.path == '/':
        raise UserError('这看起来是平台首页，请粘贴具体视频的分享链接。')
    if platform == 'YouTube' and parts.path.rstrip('/') in ('/playlist', '/feed', '/results'):
        raise UserError('当前版本只下载单条视频，不支持播放列表或搜索页。')
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k not in ('si', 'fbclid', 'igsh', 'feature')]
    return urlunsplit(('https', hostname, parts.path, urlencode(query), '')), platform


def is_short_link(url: str) -> bool:
    host = (urlsplit(url).hostname or '').lower()
    return any(host == d or host.endswith('.' + d) for d in SHORT_LINK_HOSTS)


def public_thumbnail(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        p = urlsplit(value)
        host = p.hostname or ''
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
            return None
        approved = ('ytimg.com', 'twimg.com', 'tiktokcdn.com', 'tiktokcdn-us.com',
                    'tiktokcdn-eu.com', 'fbcdn.net', 'cdninstagram.com', 'vimeocdn.com',
                    'hdslb.com', 'dmcdn.net', 'redd.it', 'redditmedia.com', 'jtvnw.net',
                    'ttwstatic.com', 'ttwstatic.net')
        return value if any(host == d or host.endswith('.' + d) for d in approved) else None
    except ValueError:
        return None


def friendly_error(raw: str) -> tuple[str, str]:
    text = raw.lower()
    rules = [
        # FFmpeg rules come first: "ffmpeg is not installed" must not fall into the generic
        # dependency rule, and a merge failure must not be reported as "not installed".
        (('ffmpeg not found', 'ffprobe not found', 'ffmpeg is not installed', 'ffprobe is not installed',
          'ffmpeg-location', 'ffmpeg/avconv not found', 'ffprobe/avprobe'),
         'MISSING_FFMPEG', '服务端未安装 FFmpeg / FFprobe，暂时无法合并或检查视频。'),
        (('postprocessing', 'ffmpeg exited', 'ffprobe exited', 'merging formats', 'conversion failed',
          'error opening output', 'ffmpeg', 'ffprobe'),
         'MERGE_FAILED', 'FFmpeg 合并或检查视频失败。请重新解析后重试；仍失败时请更新 FFmpeg 与解析引擎，并查看服务端日志。'),
        (('drm', 'encrypted media'), 'DRM_PROTECTED', '该视频受 DRM 保护，本站不提供解密或绕过。'),
        (('not installed', 'no module named'), 'MISSING_DEPENDENCY', '服务端缺少解析组件，请按部署说明安装依赖。'),
        (('sign in', 'login', 'log in', 'cookies', 'private video', 'authentication', 'captcha', 'bot'),
         'AUTH_REQUIRED', '平台要求登录或人机验证。B站可在“平台账号”中重新扫码；其他平台请使用公开可访问的视频。'),
        (('429', 'too many requests'), 'RATE_LIMITED', '平台暂时限制了请求频率，请稍后重试。'),
        (('geo', 'not available in your country', 'not available in your region'),
         'REGION_RESTRICTED', '该视频在服务器所在地区不可用。'),
        (('403', 'forbidden'), 'PLATFORM_BLOCKED', '平台拒绝了服务器请求。请更新解析引擎，并检查服务器网络。'),
        (('404', 'not found', 'removed', 'unavailable', 'deleted'),
         'NOT_AVAILABLE', '视频已删除、不可见，或当前链接无法访问。'),
        (('unsupported url', 'no suitable extractor'), 'UNSUPPORTED_URL', '这个链接暂时无法解析，请使用视频详情页的原始链接。'),
        (('name resolution', 'getaddrinfo', 'nodename', 'network is unreachable', 'connection refused'),
         'NETWORK_ERROR', '服务器无法连接视频平台，请检查 DNS、网络连接及服务端代理配置。'),
        (('timed out', 'timeout'), 'TIMEOUT', '平台响应超时，请稍后重试或检查服务器网络。'),
        (('no video formats', 'requested format', 'no formats'),
         'NO_FORMATS', '当前没有可下载的格式，或清晰度已失效。请重新解析。'),
        (('blocked network', 'private address'), 'UNSAFE_TARGET', '请求被安全策略阻止：不能访问私网或非公开地址。'),
    ]
    for needles, code, message in rules:
        if any(n in text for n in needles):
            return code, message
    return 'EXTRACTION_FAILED', '解析或下载失败。请检查视频是否公开可访问，并更新 yt-dlp 后重试。'


@contextmanager
def network_guard(proxy: str = ''):
    """Guard DNS resolution and Python TCP connects, including redirected requests."""
    original_dns = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    proxy_ips: set[tuple[str, int]] = set()
    proxy_host, proxy_port = None, None
    if proxy:
        parsed = urlsplit(proxy)
        if parsed.scheme not in ('http', 'https', 'socks5', 'socks5h') or not parsed.hostname:
            raise UserError('YTDLP_PROXY 配置无效。', 'PROXY_CONFIG')
        proxy_host = parsed.hostname
        proxy_port = parsed.port or (443 if parsed.scheme == 'https' else 1080 if parsed.scheme.startswith('socks') else 80)
        for item in original_dns(proxy_host, proxy_port, type=socket.SOCK_STREAM):
            proxy_ips.add((item[4][0], proxy_port))

    def guarded_dns(host, port, *args, **kwargs):
        result = original_dns(host, port, *args, **kwargs)
        if host == proxy_host and int(port or 0) == proxy_port:
            return result
        if any(not is_public_ip(item[4][0]) for item in result):
            raise OSError('Blocked network request to private address')
        return result

    def verify(sock, address):
        if sock.family not in (socket.AF_INET, socket.AF_INET6):
            return
        host, port = address[:2]
        if (host, int(port)) in proxy_ips:
            return
        try:
            ipaddress.ip_address(host.split('%')[0])
        except ValueError:
            guarded_dns(host, port, type=socket.SOCK_STREAM)
        else:
            if not is_public_ip(host):
                raise OSError('Blocked network request to private address')

    def guarded_connect(sock, address):
        verify(sock, address)
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        verify(sock, address)
        return original_connect_ex(sock, address)

    socket.getaddrinfo = guarded_dns
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    try:
        yield
    finally:
        socket.getaddrinfo = original_dns
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
