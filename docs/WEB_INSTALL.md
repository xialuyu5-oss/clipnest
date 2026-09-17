# ClipNest Web deployment package

**Code developed with OpenAI Vibe Coding, using ChatGPT and Codex.** Independent project; not an official OpenAI product.

This package contains the Python backend and the browser interface. It is not a standalone executable and cannot run on static-only hosting. Android/iOS native apps and a WeChat Mini Program are not included.

## Environment

| Component | Requirement |
| --- | --- |
| Python | 3.11 or later |
| FFmpeg | Both `ffmpeg` and `ffprobe` on PATH |
| YouTube JavaScript runtime | Deno 2.3+ preferred, or Node.js 22+ |
| Network | The server must be able to reach the chosen source platform; first installation needs the Python package index |
| Storage | Dedicated writable data directory; download tracks may use more space than the finished file |

The package does not bundle system runtimes, a virtual environment, credentials or downloaded third-party media. `requirements.txt` declares installable dependencies; `requirements-tested.txt` records the development validation environment and is not a portable binary environment.

## Install and start

Extract the complete archive into its own directory. On Windows, double-click `start.bat` or run:

```powershell
python start.py
```

On macOS/Linux, run `python3 start.py` or `bash start.sh`. Open `http://127.0.0.1:8000`. For a different port, add `--port 8001`. Keep the service running while using the site.

The launcher creates `.venv` and installs Python dependencies on the first run. It does not install Python, FFmpeg, Deno or Node. Use only one service process / Uvicorn worker.

Windows local operation is validated. Linux/macOS native launch and the Docker image have not been end-to-end validated; the `.tar.gz` extension describes the archive format, not a claim of Linux/macOS certification.

## Configuration

Local personal use needs no `.env`. To customize, copy `.env.example` to `.env`; the example lists all current settings. Never share the populated `.env` or the data directory.

- Default member mode accepts local loopback browsers only. For LAN, Docker or reverse-proxy use set `ENABLE_MEMBER_LOGIN=false`.
- Before LAN binding, generate an instance key with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and set `ACCESS_KEY`. Start with `python start.py --host 0.0.0.0 --no-browser` only on the intended network.
- For public hosting configure HTTPS, `PUBLIC_ORIGIN`, `COOKIE_SECURE=true`, access control, ingress limits and appropriate outbound isolation. Public source availability does not make this an audited anonymous hosting service.
- `YTDLP_PROXY` configures server egress; browser proxy settings are not automatically inherited.
- Jobs and media persist in `data/` by default. Keep the original browser's site cookie for task recovery. After restart, unfinished jobs are paused; instance/platform authentication may need renewal.
- No fixed media-size, temporary-file-size, duration or total-transfer-time limit is imposed. Actual free-space protection remains; default reserve is 512 MiB. Cancel/delete removes task cache, while ready files have no timed expiry.

## Optional Docker recipe

The package includes Dockerfile/Compose configuration for rebuilding the service environment. It does not include a built Docker image. Image build/run is unverified.

```sh
cp .env.example .env
docker compose up -d --build
```

PowerShell: `Copy-Item .env.example .env`. Compose publishes localhost port 8000 and disables member mode. Its named volume keeps task data across container restarts. `docker compose down` stops the service while retaining that volume. Dependencies and base-image tags are not immutable pins.

## Verify the package and result

Compare the downloaded archive's SHA-256 with `SHA256SUMS.txt`. This detects corruption; an unsigned checksum is not a publisher identity signature.

```powershell
Get-FileHash .\clipnest-v1.3.0-web.zip -Algorithm SHA256
```

On Linux use `sha256sum -c SHA256SUMS.txt` when all listed assets are present; on macOS use `shasum -a 256` for the selected file.

After starting, check the connection status and try the original demo. Real platform support needs a separate authorized live-video test. Choose quality, confirm duration/size/time, wait until ready, then click **Save file**. Page pause/resume controls platform-to-server transfer; final server-to-device transfer uses the browser's download manager.

## Update and rollback

Stop the service before replacing application files. Keep a separate backup of the previous application and the dedicated data directory. Use `python start.py --update` to update Python dependencies; test relevant live sources after upgrades. Avoid running old/new instances against the same data directory. Keep the previous release and its environment available for rollback; future data-format compatibility must be checked per release.

## Licenses

Code and original UI use the included MIT `LICENSE`. Original `web/assets/demo-cover.svg` and `demo-1080.mp4`, `demo-720.mp4`, `demo-480.mp4` are CC0 1.0 project test media, not third-party downloaded videos. Dependencies retain their own licenses. Only download content you own or are authorized to use.
