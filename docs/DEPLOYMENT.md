# Deployment and configuration

Validated environment: Windows local service. Docker, macOS startup, ordinary phone/LAN access, and public hosting have not been end-to-end validated. The repository is public source code, not a hosted download endpoint.

## Local use

Install the prerequisites in [README](../README.md), then run `python start.py`. The default address is `http://127.0.0.1:8000`. Use one server process and one Uvicorn worker. Do not share `DATA_DIR` between live instances.

Copy `.env.example` to `.env` only when you need configuration. The launcher installs Python packages in `.venv`; it does not install system tools. Updating with `python start.py --update` may change dependencies within the ranges in `requirements.txt`.

## LAN access from a phone

The default `ENABLE_MEMBER_LOGIN=true` mode only accepts actual loopback clients and a loopback Host. A phone is a separate device, even if it uses the same Wi-Fi. To serve the non-member interface over a trusted LAN:

1. Set `ENABLE_MEMBER_LOGIN=false` in `.env`.
2. Generate an instance access key with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and assign the result to `ACCESS_KEY` locally.
3. Run `python start.py --host 0.0.0.0 --no-browser`.
4. If needed, allow the chosen port only on the intended trusted network, then browse to the server computer's LAN address and port.

The instance key is not a platform account password. Bilibili member login is unavailable in this mode. Use HTTPS on untrusted networks. These are configuration steps, not a claim of completed phone-network acceptance testing.

## Docker

```sh
cp .env.example .env
docker compose up -d --build
docker compose logs --tail=100 -f
```

PowerShell uses `Copy-Item .env.example .env`. Compose publishes `127.0.0.1:8000`, stores task data in a named volume and forces `ENABLE_MEMBER_LOGIN=false`, because Docker bridge peers do not satisfy loopback member mode. A direct `docker run` must also set that variable. The Dockerfile installs Python, FFmpeg and Deno; builds require upstream network access.

```sh
docker compose down                 # stop while retaining the named data volume
docker compose build --pull --no-cache
docker compose up -d
```

The image has not been build-validated. Dependencies and base images are not pinned by immutable digest; `requirements-tested.txt` is an environment record, not a complete production lockfile.

## Public hosting

Keep the app behind HTTPS and instance access control. Set `ENABLE_MEMBER_LOGIN=false`, a generated `ACCESS_KEY`, the exact `PUBLIC_ORIGIN` (for example `https://clips.example.com`), and `COOKIE_SECURE=true`. `PUBLIC_ORIGIN` contains an origin, not a URL path. Leave Secure cookies off for local HTTP.

The application is a single-process personal/small-group service, not an audited anonymous public download platform. Public operation needs appropriate ingress rate/bandwidth controls, storage management, and OS/container outbound isolation. Application address checks are not a complete network sandbox. A configured proxy must enforce appropriate destination restrictions too.

The app does not trust arbitrary forwarded-client headers; clients behind a reverse proxy may share an application rate-limit bucket. A shared public service needs a deliberate trusted-proxy and identity design. Static hosts such as GitHub Pages cannot run the Python/FFmpeg backend.

## Configuration reference

| Variable | Default | Meaning |
| --- | --- | --- |
| `ACCESS_KEY` | empty | Optional locally; required by the launcher for non-loopback binding. At least 16 printable ASCII characters when set |
| `PUBLIC_ORIGIN` | empty | Exact external HTTP(S) origin; requires an access key |
| `COOKIE_SECURE` | false | Use true with HTTPS |
| `ENABLE_MEMBER_LOGIN` | true | Loopback-only Bilibili member mode; false for LAN, Docker or public hosting |
| `MAX_CONCURRENT_DOWNLOADS` | 2 | Active download workers |
| `MAX_QUEUE` | 20 | Global unfinished-task admission bound; there is also a per-session bound |
| `MIN_FREE_DISK_MB` | 512 | Actual remaining-disk reserve, measured in MiB |
| `ANALYZE_TIMEOUT_SECONDS` | 90 | Analysis timeout, not a total download-time limit |
| `ENABLE_DEMO` | true | Enable the original demo endpoints |
| `YTDLP_PROXY` | empty | Administrator-configured outbound proxy used by the server |
| `LOG_LEVEL` | warning | `debug`, `info`, `warning`, or `error` |
| `DEBUG_WORKER` | false | Forward detailed worker diagnostics; these may contain source URLs |
| `DATA_DIR` | project `data/` | Dedicated task metadata, partial files and finished files |

No fixed size, duration or total-download-time limit is configured. Historical `MAX_FILE_MB`, `MAX_STORAGE_MB`, `MAX_DURATION_SECONDS`, `DOWNLOAD_TIMEOUT_SECONDS` and `FILE_TTL_SECONDS` values no longer apply. The free-space reserve is checked periodically, not enforced as a filesystem quota.

## Storage and restart behavior

Ready and partial files remain until the user cancels or deletes a task. Back up the dedicated data directory if needed; it can contain source URLs and downloaded media. Do not commit it.

After restart, interrupted jobs are paused. Resume from the same browser with its original site cookie. Re-enter the instance key if configured and reconnect a platform account when required. Account cookies are not persisted. Deleting browser data does not delete server files and also removes the browser's ability to recover its old tasks.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Offline preview / backend disconnected | Start `start.py` and open its HTTP URL instead of the standalone preview |
| Every request returns `LOCAL_ONLY` | For LAN, Docker or a reverse proxy, disable member mode and restart |
| Ready file absent from device downloads | Click **Save file** and check the browser download manager |
| No FFmpeg / FFprobe | Install both commands, make them available on PATH, restart the terminal/service |
| YouTube formats missing | Check supported Deno/Node and EJS; update dependencies; source restrictions may still apply |
| 403 / 429 / login required | Check source access, server network and rate limits; ClipNest does not bypass challenges or permissions |
| Browser can reach a platform, server cannot | The server has a separate network path. Configure `YTDLP_PROXY` with the actual permitted endpoint if needed |
| Proxy fails inside Docker | Container `127.0.0.1` is the container itself; use an appropriately restricted reachable endpoint |
| Tasks missing after restart | Use the original browser cookie and reauthenticate when needed; there is no cross-browser recovery UI |
| Need diagnostic detail | Temporarily enable `LOG_LEVEL=debug` and `DEBUG_WORKER=true`; review locally and redact before sharing |

Before operating a new deployment, validate an authorized real video from each intended platform, including a separate-audio/video format, plus cancellation, restart recovery, storage exhaustion, ownership isolation and final-file playback. Local fixture success does not replace these checks.
