from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# Worker subprocesses inherit the parent's already-loaded environment minus the
# website secrets (see process.worker_environment). They must not read .env again,
# otherwise ACCESS_KEY would silently come back into every yt-dlp/FFmpeg child.
if not os.getenv('CLIPNEST_WORKER'):
    load_dotenv(ROOT / '.env')

LOG_LEVELS = ('debug', 'info', 'warning', 'error')


def integer(name: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(os.getenv(name, str(default)))))
    except ValueError as exc:
        raise RuntimeError(f'{name} must be an integer') from exc


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv('DATA_DIR', str(ROOT / 'data'))).resolve()
    access_key: str = os.getenv('ACCESS_KEY', '')
    public_origin: str = os.getenv('PUBLIC_ORIGIN', '').rstrip('/')
    secure_cookie: bool = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
    proxy: str = os.getenv('YTDLP_PROXY', '')
    max_downloads: int = integer('MAX_CONCURRENT_DOWNLOADS', 2, 1, 8)
    max_queue: int = integer('MAX_QUEUE', 20, 1, 100)
    analyze_timeout: int = integer('ANALYZE_TIMEOUT_SECONDS', 90, 5, 180)
    min_free_mb: int = integer('MIN_FREE_DISK_MB', 512, 50, 16384)
    enable_demo: bool = os.getenv('ENABLE_DEMO', 'true').lower() == 'true'
    member_login: bool = os.getenv('ENABLE_MEMBER_LOGIN', 'true').lower() == 'true'
    log_level: str = os.getenv('LOG_LEVEL', 'warning').strip().lower()
    debug_worker: bool = os.getenv('DEBUG_WORKER', 'false').lower() == 'true'

    def validate(self) -> None:
        if self.access_key and len(self.access_key) < 16:
            raise RuntimeError('ACCESS_KEY must contain at least 16 characters')
        if self.access_key and not (self.access_key.isascii() and self.access_key.isprintable()):
            # Non-ASCII keys are fragile across .env editors/encodings and used to crash
            # the login comparison. Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"
            raise RuntimeError('ACCESS_KEY must contain only printable ASCII characters (letters, digits, - _ etc.)')
        if self.public_origin and not self.access_key:
            raise RuntimeError('Set ACCESS_KEY before setting PUBLIC_ORIGIN / exposing the service')
        if self.public_origin and not self.public_origin.startswith(('https://', 'http://')):
            raise RuntimeError('PUBLIC_ORIGIN must be an HTTP(S) origin')
        if self.log_level not in LOG_LEVELS:
            raise RuntimeError('LOG_LEVEL must be one of: ' + ', '.join(LOG_LEVELS))

    @property
    def probe_seconds(self) -> int:
        """Metadata-probe budget per analysis; never more than a third of the analyze timeout."""
        return max(1, min(25, self.analyze_timeout // 3))


settings = Settings()
