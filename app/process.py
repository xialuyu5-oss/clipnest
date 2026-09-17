import asyncio
import contextlib
import json
import logging
import os
import signal
import subprocess
import sys
from typing import Callable

from .config import ROOT
from .safety import UserError

logger = logging.getLogger('clipnest.worker')
STDERR_TAIL_BYTES = 16 * 1024


def worker_environment() -> dict:
    """Environment for the isolated worker.

    Website credentials are removed and CLIPNEST_WORKER tells app.config not to read
    .env again, so yt-dlp, FFmpeg and JS runtimes never inherit ACCESS_KEY. Workers
    are still not a filesystem sandbox: deployment isolation remains necessary.
    """
    env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8', 'CLIPNEST_WORKER': '1'}
    for key in ('ACCESS_KEY', 'PUBLIC_ORIGIN'):
        env.pop(key, None)
    return env


async def kill_tree(proc: asyncio.subprocess.Process) -> None:
    if os.name == 'nt':
        if proc.returncode is None:
            killer = await asyncio.create_subprocess_exec(
                'taskkill', '/PID', str(proc.pid), '/T', '/F',
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await killer.wait()
    else:
        # Kill the process group, including FFmpeg or a JS runtime child.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(ProcessLookupError):
        if proc.returncode is None:
            proc.kill()
    await proc.wait()


async def run_worker(payload: dict, timeout: int | None,
                     on_progress: Callable[[dict], None] | None = None,
                     disk_check: Callable[[], None] | None = None) -> dict:
    mode = payload.get('mode', '?')
    args = {'start_new_session': True} if os.name != 'nt' else {
        'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    proc = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'app.worker', cwd=str(ROOT), env=worker_environment(),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, limit=1024 * 1024, **args)
    result = None
    error = None
    stderr_tail = bytearray()

    async def consume():
        nonlocal result, error
        async for line in proc.stdout:
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if event.get('type') == 'result':
                result = event['data']
            elif event.get('type') == 'error':
                error = UserError(event.get('message', '处理失败。'), event.get('code', 'WORKER_ERROR'), 422)
            elif event.get('type') == 'progress' and on_progress:
                on_progress(event)

    async def collect_stderr():
        # Keep only the tail. It is logged at DEBUG level because with DEBUG_WORKER=true
        # it may contain source URLs and yt-dlp diagnostics.
        while chunk := await proc.stderr.read(8192):
            stderr_tail.extend(chunk)
            del stderr_tail[:-STDERR_TAIL_BYTES]

    async def monitor():
        while proc.returncode is None:
            if disk_check:
                disk_check()
            await asyncio.sleep(0.4)

    def report(summary: str):
        logger.warning('worker[%s] %s', mode, summary)
        if stderr_tail:
            logger.debug('worker[%s] stderr tail:\n%s', mode, stderr_tail.decode('utf-8', 'replace').strip())

    children = []
    try:
        proc.stdin.write((json.dumps(payload, ensure_ascii=False) + '\n').encode())
        await proc.stdin.drain()
        proc.stdin.close()
        children = [asyncio.create_task(consume()), asyncio.create_task(collect_stderr()),
                    asyncio.create_task(monitor())]
        async with asyncio.timeout(timeout):
            await asyncio.gather(proc.wait(), *children)
        if error:
            report(f'failed: {error.code}')
            raise error
        if proc.returncode != 0 or result is None:
            report(f'exited with code {proc.returncode} without a result')
            raise UserError('处理进程意外结束，请检查服务端依赖后重试。', 'WORKER_ERROR', 502)
        return result
    except TimeoutError:
        report(f'timed out after {timeout}s')
        raise UserError('处理超时，任务已停止并清理。请稍后重试。', 'TIMEOUT', 504)
    finally:
        # Also reap grandchildren if a worker crashed before cleaning them up.
        await kill_tree(proc)
        for task in children:
            if not task.done():
                task.cancel()
        await asyncio.gather(*children, return_exceptions=True)
