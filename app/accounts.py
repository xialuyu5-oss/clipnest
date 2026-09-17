"""Bilibili QR login. Credentials live only in this process, per site session.

No password collection, browser cookie harvesting, refresh-token persistence,
or caller-controlled upstream URLs. User approval happens in the Bilibili app.
"""
import asyncio
import base64
from dataclasses import dataclass, field
from http.cookiejar import Cookie
import io
import re
import secrets
import time
from urllib.parse import urlsplit

import httpx
import qrcode
from qrcode.image.pure import PyPNGImage

from .safety import UserError

GENERATE = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate'
POLL = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll'
NAV = 'https://api.bilibili.com/x/web-interface/nav'
COOKIE_NAMES = {'SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5', 'sid'}
QR_TARGETS = {('passport.bilibili.com', '/h5-app/passport/login/scan'),
              ('passport.bilibili.com', '/qrcode/h5/login'),
              ('account.bilibili.com', '/h5/account-h5/auth/scan-web')}


def scoped_cookies(jar) -> list[dict]:
    now = time.time()
    return [{'name': c.name, 'value': c.value, 'domain': '.bilibili.com', 'path': '/',
             'expires': min(c.expires or int(now + 86400), int(now + 86400))}
            for c in jar if c.name in COOKIE_NAMES and c.domain.lstrip('.') == 'bilibili.com'
            and (not c.expires or c.expires > now) and len(c.value) < 4096
            and not any(ord(x) < 32 or ord(x) == 127 for x in c.value)]


def install_cookies(jar, values: list[dict]) -> None:
    for c in values:
        if (c.get('name') not in COOKIE_NAMES or c.get('domain') != '.bilibili.com'
                or c.get('path') != '/' or not isinstance(c.get('value'), str)
                or len(c['value']) > 4096 or any(ord(x) < 32 or ord(x) == 127 for x in c['value'])):
            raise UserError('平台登录会话无效，请重新扫码。', 'ACCOUNT_INVALID', 401)
        if c.get('expires', 0) <= time.time():
            raise UserError('平台登录会话已过期，请重新扫码。', 'ACCOUNT_EXPIRED', 401)
        jar.set_cookie(Cookie(0, c['name'], c['value'], None, False, '.bilibili.com',
                              True, True, '/', True, True, c['expires'], False,
                              None, None, {'HttpOnly': None}, False))


@dataclass(repr=False)
class Account:
    cookies: list[dict]
    vip: bool
    expires: float
    version: str = field(default_factory=lambda: secrets.token_urlsafe(18))


@dataclass(repr=False)
class Pending:
    id: str
    key: str
    expires: float
    last_poll: float = 0


class Accounts:
    def __init__(self, proxy: str = ''):
        self.proxy = proxy
        self.accounts: dict[str, Account] = {}
        self.pending: dict[str, Pending] = {}
        self.begin_versions: dict[str, str] = {}
        self.polling: set[str] = set()

    async def request(self, url: str, cookies=None, params=None):
        if url not in (GENERATE, POLL, NAV):
            # Programming error guard; unlike assert it survives python -O.
            raise RuntimeError('Refusing to contact a non-allowlisted upstream URL')
        jar = httpx.Cookies()
        if cookies:
            install_cookies(jar.jar, cookies)
        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False,
                    proxy=self.proxy or None, cookies=jar,
                    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}) as client:
                async with asyncio.timeout(18):
                    async with client.stream('GET', url, params=params) as response:
                        response.raise_for_status()
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > 128 * 1024:
                                raise UserError('平台响应过大，请稍后重试。', 'ACCOUNT_RESPONSE', 502)
                        import json
                        result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError('Unexpected response type')
                return result, scoped_cookies(client.cookies.jar)
        except (httpx.HTTPError, TimeoutError, ValueError):
            # Never echo URLs, query parameters, Set-Cookie, or platform bodies.
            raise UserError('无法连接 B站登录服务，请检查网络后重试。', 'ACCOUNT_NETWORK', 502) from None

    def clear(self, owner: str):
        self.accounts.pop(owner, None)
        self.pending.pop(owner, None)
        self.begin_versions.pop(owner, None)

    def sweep(self, owners):
        now = time.time()
        for owner in set(self.accounts) | set(self.pending) | set(self.begin_versions):
            if owner not in owners:
                self.clear(owner)
            else:
                if owner in self.pending and self.pending[owner].expires <= now:
                    self.pending.pop(owner, None)
                if owner in self.accounts and self.accounts[owner].expires <= now:
                    self.accounts.pop(owner, None)

    def current(self, owner: str, version=None) -> Account:
        account = self.accounts.get(owner)
        if not account or account.expires <= time.time():
            self.accounts.pop(owner, None)
            raise UserError('B站登录会话已失效，请重新扫码。', 'ACCOUNT_EXPIRED', 401)
        if version is not None and account.version != version:
            raise UserError('平台账号已变更，请重新解析视频。', 'ACCOUNT_CHANGED', 409)
        return account

    def status(self, owner: str):
        try:
            account = self.current(owner)
        except UserError:
            return {'platform': 'bilibili', 'status': 'disconnected', 'storage': 'memory'}
        return {'platform': 'bilibili', 'status': 'connected', 'vip': account.vip,
                'expires_at': account.expires, 'storage': 'memory'}

    async def begin(self, owner: str):
        if owner in self.accounts:
            raise UserError('请先断开当前 B站账号，再切换账号。', 'ACCOUNT_CONNECTED', 409)
        ticket = secrets.token_urlsafe(18)
        self.begin_versions[owner] = ticket
        self.pending.pop(owner, None)
        result, _ = await self.request(GENERATE)
        data = result.get('data') or {}
        url, key = data.get('url', ''), data.get('qrcode_key', '')
        try:
            p = urlsplit(url)
            valid = (result.get('code') == 0 and p.scheme == 'https' and (p.hostname, p.path) in QR_TARGETS
                     and not p.username and not p.password and p.port in (None, 443)
                     and len(url) <= 2048 and re.fullmatch(r'[a-zA-Z0-9_-]{16,128}', key))
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise UserError('平台二维码接口已变化，请更新后重试。', 'ACCOUNT_RESPONSE', 502)
        if self.begin_versions.get(owner) != ticket:
            raise UserError('扫码登录已取消。', 'LOGIN_CANCELLED', 409)
        pending = Pending(secrets.token_urlsafe(18), key, time.time() + 180)
        self.pending[owner] = pending
        image = qrcode.make(url, image_factory=PyPNGImage, box_size=6, border=4)
        buffer = io.BytesIO()
        image.save(buffer)
        return {'flow_id': pending.id, 'expires_at': pending.expires,
                'qr_image': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode(),
                'status': 'waiting'}

    async def verify(self, owner: str):
        account = self.current(owner)
        result, _ = await self.request(NAV, account.cookies)
        if self.accounts.get(owner) is not account:
            raise UserError('平台账号已变更，请重新操作。', 'ACCOUNT_CHANGED', 409)
        if result.get('code') != 0 or not (result.get('data') or {}).get('isLogin'):
            self.accounts.pop(owner, None)
            raise UserError('B站会话已过期，请重新扫码。', 'ACCOUNT_EXPIRED', 401)
        info = result['data']
        account.vip = (info.get('vip') or {}).get('status', info.get('vipStatus', 0)) == 1
        return account

    async def poll(self, owner: str, flow_id: str):
        pending = self.pending.get(owner)
        if not pending or not secrets.compare_digest(pending.id, flow_id) or pending.expires <= time.time():
            raise UserError('二维码已过期或已取消，请重新生成。', 'QR_EXPIRED', 410)
        if owner in self.polling or time.monotonic() - pending.last_poll < 2:
            raise UserError('请稍后再检查扫码状态。', 'RATE_LIMITED', 429)
        pending.last_poll = time.monotonic()
        self.polling.add(owner)
        try:
            result, cookies = await self.request(POLL, params={'qrcode_key': pending.key})
            if self.pending.get(owner) is not pending:
                raise UserError('扫码登录已取消。', 'LOGIN_CANCELLED', 409)
            data = result.get('data') or {}
            if result.get('code') != 0:
                raise UserError('B站未接受扫码请求，请重新生成二维码。', 'ACCOUNT_RESPONSE', 502)
            code = data.get('code')
            if code in (86101, 86090):
                return {'status': 'waiting' if code == 86101 else 'scanned'}
            if code == 86038:
                self.pending.pop(owner, None)
                raise UserError('二维码已过期，请重新生成。', 'QR_EXPIRED', 410)
            if code != 0:
                raise UserError('平台未完成授权，请重新扫码。', 'ACCOUNT_RESPONSE', 502)
            if not any(c['name'] == 'SESSDATA' for c in cookies):
                raise UserError('平台没有返回有效登录会话，请重新扫码。', 'ACCOUNT_RESPONSE', 502)
            # Check membership before installing the new account, and re-check
            # pending identity after every await so cancellation cannot resurrect it.
            nav, _ = await self.request(NAV, cookies)
            if self.pending.get(owner) is not pending:
                raise UserError('扫码登录已取消。', 'LOGIN_CANCELLED', 409)
            info = nav.get('data') or {}
            if nav.get('code') != 0 or not info.get('isLogin'):
                raise UserError('登录会话校验失败，请重新扫码。', 'ACCOUNT_INVALID', 401)
            expires = min([time.time() + 86400] + [c['expires'] for c in cookies if c['name'] == 'SESSDATA'])
            self.accounts[owner] = Account(cookies, (info.get('vip') or {}).get('status', info.get('vipStatus', 0)) == 1, expires)
            self.pending.pop(owner, None)
            self.begin_versions.pop(owner, None)
            return self.status(owner)
        finally:
            self.polling.discard(owner)
