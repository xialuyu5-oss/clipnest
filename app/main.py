"""Single-process FastAPI service. Run with exactly one Uvicorn worker."""
import asyncio
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
import hmac
import hashlib
import ipaddress
import importlib.metadata
import json
import logging
from pathlib import Path
import re
import secrets
import shutil
import time
from urllib.parse import urlsplit
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, Settings, settings
from .accounts import Accounts
from .media import public_media
from .process import run_worker
from .safety import PLATFORMS, UserError, normalize_url
from .environment import report as local_environment_report

COOKIE = 'clipnest_session'
SESSION_TTL = 86400
ANALYSIS_TTL = 1800
ACTIVE = {'queued', 'downloading', 'processing'}
VERSION = '1.3.1'
logger = logging.getLogger('clipnest')


def same_secret(supplied: str, expected: str) -> bool:
    """Constant-time comparison that accepts any text.

    hmac.compare_digest raises TypeError for non-ASCII str input, which turned a wrong
    password or a garbage CSRF header into HTTP 500. Compare UTF-8 bytes instead.
    """
    return hmac.compare_digest(supplied.encode('utf-8', 'surrogatepass'),
                               expected.encode('utf-8', 'surrogatepass'))


def dependency_status() -> dict:
    try:
        engine = importlib.metadata.version('yt-dlp')
    except importlib.metadata.PackageNotFoundError:
        engine = None
    runtime = 'deno' if shutil.which('deno') else 'node' if shutil.which('node') else None
    try:
        ejs = importlib.metadata.version('yt-dlp-ejs')
    except importlib.metadata.PackageNotFoundError:
        ejs = None
    return {'yt_dlp': engine, 'ffmpeg': bool(shutil.which('ffmpeg')),
            'ffprobe': bool(shutil.which('ffprobe')), 'js_runtime': runtime, 'ejs': ejs}


@dataclass
class Session:
    token: str
    csrf: str
    expires: float

    @property
    def owner(self) -> str:
        # Persist only a one-way ownership identifier, never the session credential.
        return hashlib.sha256(self.token.encode()).hexdigest()


@dataclass
class Job:
    id: str
    owner: str
    media: dict
    option: dict
    created_at: float = field(default_factory=time.time)
    state: str = 'queued'
    progress: float | None = 0
    downloaded: int = 0
    total: int | None = None
    speed: float | None = None
    eta: float | None = None
    eta_scope: str = 'download'
    track: str = ''
    error: str | None = None
    error_code: str | None = None
    expires_at: float | None = None
    path: Path | None = None
    actual: dict | None = None
    task: asyncio.Task | None = None
    serving: int = 0
    account_owner: str = ''
    requires_account: bool = False
    stop_reason: str = 'cancelled'
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def public(self) -> dict:
        return {'id': self.id, 'title': self.media['title'], 'platform': self.media['platform'],
                'thumbnail': self.media.get('thumbnail'), 'is_demo': self.media.get('is_demo', False),
                'quality': self.option['label'], 'container': (self.actual or {}).get('container', self.option['container']),
                'state': self.state, 'progress': self.progress, 'downloaded': self.downloaded,
                'total': self.total, 'speed': self.speed, 'eta': self.eta, 'eta_scope': self.eta_scope, 'track': self.track,
                'created_at': self.created_at, 'expires_at': self.expires_at,
                'error': self.error, 'error_code': self.error_code, 'actual': self.actual,
                'needs_merge': self.option.get('needs_merge', False),
                'file_url': f'/api/downloads/{self.id}/file' if self.state == 'ready' else None}


class State:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.sessions: dict[str, Session] = {}
        self.analyses: dict[str, dict] = {}
        self.jobs: dict[str, Job] = {}
        self.rates: dict[str, deque] = defaultdict(deque)
        self.analysis_slots = asyncio.Semaphore(2)
        self.download_slots = asyncio.Semaphore(cfg.max_downloads)
        self.jobs_dir = cfg.data_dir / 'jobs'
        self.dependencies = dependency_status()
        self.accounts = Accounts(cfg.proxy)

    def rate(self, key: str, limit: int, window: int = 60):
        now = time.monotonic()
        times = self.rates[key]
        while times and times[0] < now - window:
            times.popleft()
        if len(times) >= limit:
            raise UserError('请求过于频繁，请稍后重试。', 'RATE_LIMITED', 429)
        times.append(now)

    def create_session(self, token: str = '') -> Session:
        now = time.time()
        self.sessions = {k: v for k, v in self.sessions.items() if v.expires > now}
        if len(self.sessions) >= 1000:
            raise UserError('当前会话过多，请稍后重试。', 'SERVER_BUSY', 503)
        # Reuse the browser's random credential only after normal instance authentication.
        # This recovers its hashed job ownership after a restart without saving secrets.
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            token = secrets.token_urlsafe(32)
        session = Session(token, secrets.token_urlsafe(24), now + SESSION_TTL)
        self.sessions[session.token] = session
        return session

    def get_session(self, request: Request) -> Session:
        session = self.sessions.get(request.cookies.get(COOKIE, ''))
        if not session or session.expires < time.time():
            raise UserError('会话已过期，请重新连接网站。', 'UNAUTHORIZED', 401)
        return session

    def check_space(self):
        if shutil.disk_usage(self.jobs_dir).free < self.cfg.min_free_mb * 1024 * 1024:
            raise UserError('服务器剩余磁盘空间不足，任务已停止。', 'DISK_FULL', 507)

    def save_job(self, job: Job):
        directory = self.jobs_dir / job.id
        directory.mkdir(parents=True, exist_ok=True)
        data = {key: getattr(job, key) for key in (
            'id', 'owner', 'option', 'created_at', 'state', 'progress', 'downloaded',
            'total', 'track', 'error', 'error_code', 'actual', 'requires_account')}
        data['media'] = {key: job.media.get(key) for key in (
            'title', 'platform', 'url', 'is_demo', 'duration')}
        data['filename'] = job.path.name if job.path else None
        temporary = directory / 'job.json.tmp'
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        temporary.replace(directory / 'job.json')

    def load_jobs(self):
        for directory in self.jobs_dir.iterdir():
            if not re.fullmatch(r'[a-f0-9]{32}', directory.name) or directory.is_symlink() or not directory.is_dir():
                continue
            try:
                data = json.loads((directory / 'job.json').read_text(encoding='utf-8'))
                filename = data.pop('filename', None)
                if data['id'] != directory.name or not re.fullmatch(r'[a-f0-9]{64}', data['owner']):
                    raise ValueError('Invalid job identity')
                job = Job(**data)
                if filename:
                    candidate = (directory / filename).resolve()
                    if candidate.parent != directory.resolve() or candidate.is_symlink():
                        raise ValueError('Invalid file path')
                    job.path = candidate
                if job.state in ACTIVE:
                    job.state = 'paused'
                if job.state == 'ready' and (not job.path or not job.path.is_file()):
                    job.state, job.error_code = 'error', 'FILE_EXPIRED'
                self.jobs[job.id] = job
            except (OSError, ValueError, TypeError, KeyError):
                # Preserve unreadable files for recovery rather than deleting them at startup.
                logger.warning('Could not restore job %s', directory.name)

    async def download(self, job: Job):
        directory = self.jobs_dir / job.id
        last_saved = 0.0
        try:
            async with self.download_slots:
                self.check_space()
                directory.mkdir(parents=True, exist_ok=True)
                job.state = 'downloading'
                self.save_job(job)

                def progress(event):
                    nonlocal last_saved
                    for key in ('state', 'progress', 'downloaded', 'total', 'speed', 'eta', 'eta_scope', 'track'):
                        if key in event:
                            setattr(job, key, event[key])
                    if time.monotonic() - last_saved >= 1:
                        self.save_job(job)
                        last_saved = time.monotonic()

                payload = {'mode': 'demo' if job.media.get('is_demo') else 'download',
                           'height': job.option['height'], 'url': job.media['url'], 'option': job.option,
                           'directory': str(directory), 'proxy': self.cfg.proxy}
                if job.media.get('_account_version'):
                    account = self.accounts.current(job.account_owner, job.media['_account_version'])
                    payload['account_cookies'] = account.cookies
                    payload['account_platform'] = 'bilibili'
                result = await run_worker(payload, None, progress, self.check_space)
                if job.media.get('_account_version'):
                    self.accounts.current(job.account_owner, job.media['_account_version'])
                path = Path(result['path']).resolve()
                if not path.is_relative_to(directory.resolve()) or not path.is_file() or path.is_symlink():
                    raise UserError('下载结果未通过路径校验。', 'INVALID_FILE', 500)
                job.path, job.actual = path, result['actual']
                job.state, job.progress = 'ready', 100
                job.speed, job.eta = None, None
        except asyncio.CancelledError:
            job.state = job.stop_reason
            job.error = None if job.state == 'paused' else '任务已取消。'
            raise
        except UserError as exc:
            job.state, job.error, job.error_code = 'error', exc.message, exc.code
            logger.info('job %s stopped: %s (%s)', job.id, exc.code, job.media.get('platform'))
        except Exception:
            job.state, job.error, job.error_code = 'error', '服务器处理失败，请检查运行日志。', 'SERVER_ERROR'
            # No URL or title here; those may identify the user's content.
            logger.exception('job %s failed unexpectedly (%s)', job.id, job.media.get('platform'))
        finally:
            job.speed, job.eta = None, None
            if job.state == 'cancelled':
                shutil.rmtree(directory, ignore_errors=True)
            self.save_job(job)

    async def sweep(self):
        while True:
            await asyncio.sleep(30)
            try:
                self.sweep_once()
            except Exception:
                # One bad iteration must not silently stop expiry cleanup for the rest of the process.
                logger.exception('periodic cleanup failed; will retry')

    def sweep_once(self):
        now = time.time()
        self.analyses = {k: v for k, v in self.analyses.items() if v['_expires'] > now}
        self.sessions = {k: v for k, v in self.sessions.items() if v.expires > now}
        self.accounts.sweep(self.sessions)
        for job in self.jobs.values():
            if job.media.get('_account_version') and job.state in ACTIVE:
                try:
                    self.accounts.current(job.account_owner, job.media['_account_version'])
                except UserError:
                    if job.task:
                        job.task.cancel()
        cutoff = time.monotonic() - 300
        self.rates = defaultdict(deque, {k: v for k, v in self.rates.items() if v and v[-1] > cutoff})


class AnalyzeBody(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
    use_account: bool = False


class QRBody(BaseModel):
    flow_id: str = Field(min_length=16, max_length=100)


class DownloadBody(BaseModel):
    analysis_id: str = Field(min_length=10, max_length=100)
    option_id: str = Field(min_length=1, max_length=100)
    rights_confirmed: bool = False
    download_confirmed: bool = False


class LoginBody(BaseModel):
    key: str = Field(min_length=1, max_length=256)


class LeasedFileResponse(FileResponse):
    def __init__(self, job: Job, **kwargs):
        super().__init__(job.path, **kwargs)
        self.job = job

    async def __call__(self, scope, receive, send):
        self.job.serving += 1
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.job.serving -= 1


def create_app(cfg: Settings = settings) -> FastAPI:
    state = State(cfg)

    @asynccontextmanager
    async def lifespan(app):
        cfg.validate()
        level = getattr(logging, cfg.log_level.upper())
        # Uvicorn configures only its own loggers; give the application logger a handler.
        logging.basicConfig(level=level, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
        logger.setLevel(level)
        logger.info('ClipNest %s starting; debug_worker=%s', VERSION, cfg.debug_worker)
        state.jobs_dir.mkdir(parents=True, exist_ok=True)
        state.load_jobs()
        cleaner = asyncio.create_task(state.sweep())
        yield
        cleaner.cancel()
        tasks = [j.task for j in state.jobs.values() if j.task and not j.task.done()]
        for job in state.jobs.values():
            if job.state in ACTIVE:
                job.stop_reason = 'paused'
                job.state = 'paused'
                state.save_job(job)
        for task in tasks:
            task.cancel()
        await asyncio.gather(cleaner, *tasks, return_exceptions=True)
        for owner in list(state.sessions):
            state.accounts.clear(owner)

    app = FastAPI(title='ClipNest / 留影 API', version=VERSION, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = state
    environment_lock = asyncio.Lock()
    environment_cache = None
    environment_checked = 0.0

    @app.exception_handler(UserError)
    async def user_error(request, exc):
        return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)

    @app.middleware('http')
    async def protection(request: Request, call_next):
        try:
            path = request.url.path
            if cfg.local_device or (cfg.member_login and not cfg.public_origin):
                # Reject DNS rebinding and remote clients before issuing a session.
                require_local(request)
            if path.startswith('/api/'):
                length = request.headers.get('content-length', '0')
                if not length.isdigit() or int(length) > 8192:
                    raise UserError('请求内容过大。', 'REQUEST_TOO_LARGE', 413)
                # Reject chunked bodies; API requests here are small JSON documents.
                if request.headers.get('transfer-encoding'):
                    raise UserError('不接受流式请求体。', 'INVALID_BODY', 400)
                if request.method in ('POST', 'DELETE', 'PUT', 'PATCH'):
                    origin = request.headers.get('origin')
                    expected = cfg.public_origin or f'{request.url.scheme}://{request.headers.get("host", "")}'
                    if origin and origin.rstrip('/') != expected:
                        raise UserError('拒绝跨站请求。', 'CROSS_ORIGIN', 403)
                    if request.headers.get('sec-fetch-site') == 'cross-site':
                        raise UserError('拒绝跨站请求。', 'CROSS_ORIGIN', 403)
                public_routes = ('/api/health', '/api/session', '/api/login')
                if path not in public_routes:
                    session = state.get_session(request)
                    request.state.session = session
                    if request.method in ('POST', 'DELETE', 'PUT', 'PATCH'):
                        supplied = request.headers.get('x-csrf-token', '')
                        if not same_secret(supplied, session.csrf):
                            raise UserError('安全令牌已失效，请刷新网页后重试。', 'CSRF_FAILED', 403)
                # Limit public session/login attempts independently of cookies.
                if path in public_routes and path != '/api/health':
                    host = request.client.host if request.client else 'unknown'
                    state.rate('public:' + host, 30)
            response = await call_next(request)
        except UserError as exc:
            response = JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)
        response.headers.update({
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
            'X-Frame-Options': 'DENY',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; media-src 'self' blob:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'",
        })
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store, private'
        return response

    def session_response(session: Session) -> JSONResponse:
        response = JSONResponse({'authenticated': True, 'csrf_token': session.csrf,
                                 'access_key_required': bool(cfg.access_key)})
        response.set_cookie(COOKIE, session.token, max_age=365 * 86400,
                            httponly=True, samesite='strict', secure=cfg.secure_cookie, path='/')
        return response

    def require_local(request: Request):
        host = request.url.hostname
        peer = request.client.host if request.client else ''
        try:
            allowed_peer = ipaddress.ip_address(peer).is_loopback
        except ValueError:
            allowed_peer = False
        if host not in ('127.0.0.1', 'localhost', '::1') or not allowed_peer:
            raise UserError('会员版仅允许从本机地址访问。局域网、Docker 或公网部署请在 .env 设置 '
                            'ENABLE_MEMBER_LOGIN=false 后重启服务（该模式不提供平台账号功能）。', 'LOCAL_ONLY', 403)

    def account_owner(request: Request):
        if not cfg.member_login or cfg.public_origin:
            raise UserError('此实例未启用本机会员登录。', 'ACCOUNT_DISABLED', 403)
        require_local(request)
        return request.state.session.token

    @app.api_route('/local/environment', methods=['GET', 'OPTIONS'])
    async def local_environment(request: Request):
        # This is the only cross-origin route. Never expose a session, tasks,
        # account state, file paths or an API proxy to the public website.
        nonlocal environment_cache, environment_checked
        if not cfg.local_device:
            raise UserError('Not found.', 'NOT_FOUND', 404)
        require_local(request)
        origin = request.headers.get('origin', '')
        parsed = urlsplit(origin)
        local_origin = (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
                        and not parsed.username and not parsed.password and not parsed.path
                        and not parsed.query and not parsed.fragment)
        if origin and origin != cfg.local_site_origin and not local_origin:
            raise UserError('Origin not allowed.', 'CROSS_ORIGIN', 403)
        headers = {'Cache-Control': 'no-store', 'Vary': 'Origin'}
        if origin:
            headers['Access-Control-Allow-Origin'] = origin
        if request.method == 'OPTIONS':
            if (request.headers.get('access-control-request-method') != 'GET'
                    or request.headers.get('access-control-request-headers')):
                raise UserError('Only a read-only check is allowed.', 'CROSS_ORIGIN', 403)
            headers['Access-Control-Allow-Methods'] = 'GET'
            headers['Access-Control-Allow-Private-Network'] = 'true'
            return JSONResponse({}, headers=headers)
        state.rate('local-environment', 60)
        async with environment_lock:
            if environment_cache is None or time.monotonic() - environment_checked > 5:
                result = await asyncio.to_thread(local_environment_report)
                tools = {item['name']: item['ready'] for item in result['checks']}
                deps = dependency_status()
                checks = [
                    {'id': 'python', 'ready': bool(tools.get('Python'))},
                    {'id': 'ffmpeg', 'ready': bool(tools.get('ffmpeg') and tools.get('ffprobe'))},
                    {'id': 'javascript', 'ready': bool(tools.get('deno') or tools.get('node'))},
                    {'id': 'extractor', 'ready': bool(deps['yt_dlp'] and deps['ejs'])},
                ]
                environment_cache = {'product': 'clipnest', 'protocol': 1,
                                     'ready': all(item['ready'] for item in checks), 'checks': checks}
                environment_checked = time.monotonic()
        return JSONResponse(environment_cache, headers=headers)

    @app.get('/api/accounts/bilibili')
    async def account_status(request: Request):
        return state.accounts.status(account_owner(request))

    @app.post('/api/accounts/bilibili/qr')
    async def account_qr(request: Request):
        owner = account_owner(request)
        state.rate('qr:' + owner, 5)
        return await state.accounts.begin(owner)

    @app.post('/api/accounts/bilibili/poll')
    async def account_poll(body: QRBody, request: Request):
        owner = account_owner(request)
        state.rate('qr-poll:' + owner, 25)
        return await state.accounts.poll(owner, body.flow_id)

    @app.delete('/api/accounts/bilibili/qr')
    async def cancel_qr(request: Request):
        owner = account_owner(request)
        state.accounts.pending.pop(owner, None)
        state.accounts.begin_versions.pop(owner, None)
        return {'ok': True}

    @app.post('/api/accounts/bilibili/verify')
    async def account_verify(request: Request):
        owner = account_owner(request)
        state.rate('account-check:' + owner, 10)
        await state.accounts.verify(owner)
        return state.accounts.status(owner)

    @app.delete('/api/accounts/bilibili')
    async def disconnect_account(request: Request):
        owner = account_owner(request)
        state.accounts.clear(owner)
        state.analyses = {k: v for k, v in state.analyses.items()
                          if not (v['_owner'] == owner and v.get('_account_version'))}
        tasks = [j.task for j in state.jobs.values() if j.account_owner == owner and
                 j.media.get('_account_version') and j.task and not j.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return {'ok': True}

    @app.get('/api/health')
    async def health():
        # Re-detect on every health call so "重新检查" notices FFmpeg/Deno installed after startup.
        state.dependencies = deps = dependency_status()
        return {'status': 'ready' if all((deps['yt_dlp'], deps['ffmpeg'], deps['ffprobe'])) else 'setup_needed',
                'dependencies': deps, 'platforms': list(PLATFORMS),
                'download_confirmation_required': True,
                'file_ttl_seconds': None, 'resumable_downloads': True,
                'max_concurrent_downloads': cfg.max_downloads,
                'access_key_required': bool(cfg.access_key), 'demo_enabled': cfg.enable_demo,
                'member_login': cfg.member_login and not cfg.public_origin,
                'version': VERSION}

    @app.get('/api/session')
    async def session(request: Request):
        with suppress(UserError):
            return session_response(state.get_session(request))
        if cfg.access_key:
            return JSONResponse({'authenticated': False, 'access_key_required': True}, status_code=401)
        return session_response(state.create_session(request.cookies.get(COOKIE, '')))

    @app.post('/api/login')
    async def login(body: LoginBody, request: Request):
        ip = request.client.host if request.client else 'unknown'
        state.rate('login:' + ip, 5)
        if not cfg.access_key or not same_secret(body.key, cfg.access_key):
            raise UserError('访问口令不正确。', 'UNAUTHORIZED', 401)
        return session_response(state.create_session(request.cookies.get(COOKIE, '')))

    @app.post('/api/logout')
    async def logout(request: Request):
        session = request.state.session
        state.accounts.clear(session.token)
        # Cancel jobs before invalidating the owner session.
        tasks = [j.task for j in state.jobs.values() if j.owner == session.owner and j.task and not j.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        state.sessions.pop(session.token, None)
        response = JSONResponse({'ok': True})
        # The HttpOnly cookie retains job ownership; access-key authentication is revoked above.
        return response

    def cache_analysis(media: dict, owner: str) -> dict:
        now = time.time()
        for key, value in list(state.analyses.items()):
            if value['_expires'] < now:
                state.analyses.pop(key, None)
        owned = sorted((v for v in state.analyses.values() if v['_owner'] == owner), key=lambda x: x['_expires'])
        while len(owned) >= 10:
            state.analyses.pop(owned.pop(0)['id'], None)
        if len(state.analyses) >= 500:
            raise UserError('解析缓存已满，请稍后重试。', 'SERVER_BUSY', 503)
        media.update({'id': secrets.token_urlsafe(18), '_owner': owner, '_expires': now + ANALYSIS_TTL,
                      'expires_at': now + ANALYSIS_TTL})
        state.analyses[media['id']] = media
        return public_media(media)

    @app.post('/api/analyze')
    async def analyze(body: AnalyzeBody, request: Request):
        owner = request.state.session.token
        state.rate('analyze:' + owner, 10)
        ip = request.client.host if request.client else 'unknown'
        state.rate('analyze-ip:' + ip, 20)
        url, platform = normalize_url(body.url)
        account = None
        if body.use_account and platform == '哔哩哔哩':
            account_owner(request)
            account = await state.accounts.verify(owner)
        if not state.dependencies['yt_dlp']:
            raise UserError('服务端缺少 yt-dlp。请运行启动脚本或安装 requirements.txt 后重启服务。',
                            'MISSING_DEPENDENCY', 503)
        try:
            await asyncio.wait_for(state.analysis_slots.acquire(), timeout=3)
        except TimeoutError:
            raise UserError('当前解析任务较多，请稍后重试。', 'SERVER_BUSY', 429)
        try:
            payload = {'mode': 'analyze', 'url': url, 'proxy': cfg.proxy, 'probe_seconds': cfg.probe_seconds}
            if account:
                payload.update(account_cookies=account.cookies, account_platform='bilibili')
            media = await run_worker(payload, cfg.analyze_timeout)
            state.get_session(request)
            if account:
                state.accounts.current(owner, account.version)
                media['_account_version'] = account.version
            media['access_mode'] = 'member_session' if account else 'anonymous'
            return cache_analysis(media, owner)
        finally:
            state.analysis_slots.release()

    @app.post('/api/demo')
    async def demo(request: Request):
        if not cfg.enable_demo:
            raise UserError('管理员已关闭演示素材。', 'DEMO_DISABLED', 404)
        state.rate('demo:' + request.state.session.token, 10)
        options = []
        for h in (1080, 720, 480):
            path = ROOT / 'web' / 'assets' / f'demo-{h}.mp4'
            if path.is_file():
                options.append({'id': f'demo-{h}', 'label': f'{h}p', 'height': h,
                                'source_height': h, 'width': ((round(h * 16 / 9) + 1) // 2) * 2, 'fps': 24,
                                'container': 'mp4', 'codec': 'h264', 'has_audio': True,
                                'needs_merge': False, 'filesize': path.stat().st_size,
                                'approximate': False, 'dynamic_range': 'SDR'})
        if not options:
            raise UserError('演示素材缺失，请运行 scripts/make_demo.py。', 'DEMO_MISSING', 503)
        return cache_analysis({'title': '片刻之间 · A little motion', 'uploader': 'ClipNest 原创演示素材',
                               'duration': 6, 'platform': '演示素材', 'url': 'demo://clipnest',
                               'thumbnail': '/assets/demo-cover.svg', 'description': '程序生成的抽象动画，随项目以 CC0 方式提供，可自由下载测试。',
                               'upload_date': '', 'is_demo': True, 'options': options}, request.state.session.token)

    @app.post('/api/downloads', status_code=202)
    async def download(body: DownloadBody, request: Request):
        owner = request.state.session.token
        state.rate('download:' + owner, 10)
        if not body.rights_confirmed:
            raise UserError('请先确认你拥有该视频的下载或使用授权。', 'CONSENT_REQUIRED')
        if not body.download_confirmed:
            raise UserError('请查看文件大小和时长，再确认下载。', 'DOWNLOAD_CONFIRMATION_REQUIRED')
        media = state.analyses.get(body.analysis_id)
        if not media or media['_owner'] != owner or media['_expires'] < time.time():
            raise UserError('解析结果已失效，请重新解析链接。', 'ANALYSIS_EXPIRED', 410)
        if media.get('_account_version'):
            account_owner(request)
            state.accounts.current(owner, media['_account_version'])
        option = next((o for o in media['options'] if o['id'] == body.option_id), None)
        if not option:
            raise UserError('清晰度选项无效，请重新解析。', 'INVALID_FORMAT')
        if not all(state.dependencies[k] for k in ('ffmpeg', 'ffprobe')):
            raise UserError('服务端缺少 FFmpeg / FFprobe，请完成安装后重启服务。', 'MISSING_FFMPEG', 503)
        active = [j for j in state.jobs.values() if j.state in ACTIVE]
        if len(active) >= cfg.max_queue or sum(j.owner == request.state.session.owner for j in active) >= 3:
            raise UserError('下载队列已满，请等待已有任务完成。', 'QUEUE_FULL', 429)
        state.check_space()
        job = Job(uuid.uuid4().hex, request.state.session.owner, media, option,
                  account_owner=owner, requires_account=bool(media.get('_account_version')))
        state.save_job(job)
        state.jobs[job.id] = job
        job.task = asyncio.create_task(state.download(job))
        return job.public()

    @app.get('/api/downloads')
    async def jobs(request: Request):
        owner = request.state.session.owner
        return {'items': [j.public() for j in sorted(state.jobs.values(), key=lambda j: -j.created_at)
                          if j.owner == owner]}

    def owned_job(job_id: str, request: Request) -> Job:
        job = state.jobs.get(job_id)
        if not job or job.owner != request.state.session.owner:
            raise UserError('任务不存在或已经过期。', 'NOT_FOUND', 404)
        return job

    @app.get('/api/downloads/{job_id}')
    async def job_status(job_id: str, request: Request):
        return owned_job(job_id, request).public()

    @app.post('/api/downloads/{job_id}/pause')
    async def pause_job(job_id: str, request: Request):
        job = owned_job(job_id, request)
        async with job.lock:
            if job.state == 'paused':
                return job.public()
            if job.state not in ('queued', 'downloading'):
                raise UserError('当前阶段不能暂停，请等待合并完成或取消任务。', 'JOB_NOT_PAUSABLE', 409)
            job.stop_reason = 'paused'
            if job.task and not job.task.done():
                job.task.cancel()
                await asyncio.gather(job.task, return_exceptions=True)
            job.state, job.speed, job.eta = 'paused', None, None
            state.save_job(job)
            return job.public()

    @app.post('/api/downloads/{job_id}/resume', status_code=202)
    async def resume_job(job_id: str, request: Request):
        job = owned_job(job_id, request)
        async with job.lock:
            if job.state not in ('paused', 'error'):
                raise UserError('只有暂停或失败的下载可以继续。', 'JOB_NOT_RESUMABLE', 409)
            active = [j for j in state.jobs.values() if j.state in ACTIVE]
            if len(active) >= cfg.max_queue or sum(j.owner == job.owner for j in active) >= 3:
                raise UserError('下载队列已满，请等待已有任务完成。', 'QUEUE_FULL', 429)
            state.check_space()
            if job.requires_account:
                account_owner(request)
                account = state.accounts.current(request.state.session.token)
                job.account_owner = request.state.session.token
                job.media['_account_version'] = account.version
            job.state, job.error, job.error_code = 'queued', None, None
            job.stop_reason = 'cancelled'
            state.save_job(job)
            job.task = asyncio.create_task(state.download(job))
            return job.public()

    @app.delete('/api/downloads/{job_id}')
    async def remove_job(job_id: str, request: Request):
        job = owned_job(job_id, request)
        async with job.lock:
            if job.serving:
                raise UserError('文件正在传输中，请完成保存后再删除。', 'FILE_IN_USE', 409)
            job.stop_reason = 'cancelled'
            if job.task and not job.task.done():
                job.task.cancel()
                await asyncio.gather(job.task, return_exceptions=True)
            directory = state.jobs_dir / job.id
            try:
                if directory.exists():
                    shutil.rmtree(directory)
            except OSError:
                raise UserError('缓存仍被占用，请稍后再次取消或删除。', 'CLEANUP_FAILED', 409)
            state.jobs.pop(job.id, None)
        return {'ok': True}

    @app.get('/api/downloads/{job_id}/file')
    async def file(job_id: str, request: Request):
        job = owned_job(job_id, request)
        if job.state != 'ready' or not job.path:
            raise UserError('文件尚未就绪。', 'FILE_NOT_READY', 409)
        if not job.path.is_file():
            raise UserError('文件已过期，请重新解析并下载。', 'FILE_EXPIRED', 410)
        title = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', job.media['title']).strip(' .')[:90] or 'video'
        filename = f'{title}_{job.option["label"]}{job.path.suffix}'
        mime = {'mp4': 'video/mp4', 'm4v': 'video/mp4', 'webm': 'video/webm',
                'mkv': 'video/x-matroska', 'mov': 'video/quicktime'}.get(job.path.suffix[1:], 'application/octet-stream')
        return LeasedFileResponse(job, filename=filename, media_type=mime, content_disposition_type='attachment')

    app.mount('/assets', StaticFiles(directory=ROOT / 'web' / 'assets'), name='assets')

    @app.get('/')
    async def index():
        return FileResponse(ROOT / 'web' / 'index.html', media_type='text/html')

    @app.get('/{name}')
    async def static(name: str):
        if name not in ('app.js', 'style.css', 'member.css', 'favicon.svg'):
            raise UserError('页面不存在。', 'NOT_FOUND', 404)
        return FileResponse(ROOT / 'web' / name)

    return app


app = create_app()
