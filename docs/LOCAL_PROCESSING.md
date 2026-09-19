# Local processing: PC and Android

[Executed checks and remaining limits](LOCAL_DEVICE_VALIDATION.md)

The public website is an entry point and distribution channel. Video-platform
requests, extraction, media downloads, merging and task files belong on the
user's device. A missing local engine must never silently fall back to a hosted
ClipNest downloader.

## PC

Open the website first. It checks the local component automatically:

- **Ready:** this tab automatically opens the complete existing downloader at
  `http://127.0.0.1:8000/`, preserving the chosen language. The address changes to
  this computer; analysis, accounts, downloads and files use its same-origin API.
- **Missing components:** show only verified missing/incompatible items, their
  official download links and the Windows installer. Restart the local component
  after installation; automatic retry or returning to the tab detects readiness.
- **Unreachable:** report that the component may be stopped, absent or blocked.
  Do not label any runtime as missing without evidence. Start an installed
  component, or download/extract the local package on first use. The package
  includes `install-missing.bat` and `start-local.bat`.

A browser cannot inventory installed desktop programs on its own. The local
component must be running. Installation and initial startup require the user;
this iteration does not register a background startup service. The website probes
only the default port 8000. Custom ports can still use the printed local URL.

Deploy the website over HTTPS. Browsers may require local-network/loopback access
permission; if denied, the page offers retry and a direct local-interface link.
This permission path has not been validated on a public HTTPS deployment.
The read-only `/local/environment` route returns only product/protocol identifiers
and four readiness flags (Python, FFmpeg/ffprobe, Deno or Node, yt-dlp/EJS).
It does not return paths, versions, accounts, cookies, tasks or video links.
Only local-device mode exposes it, with loopback peer/Host validation and CORS
limited to `LOCAL_SITE_ORIGIN` (default `https://xialuyu5-oss.github.io`) and
loopback HTTP origins for development. For another website domain, set its exact
HTTPS origin in the local package's `.env`. Other API routes retain their original
same-origin/session/CSRF protections; this is not a cross-origin download proxy.

The existing Web package already runs its engine on the computer that starts it.
Run `check-environment.bat` on Windows, or
`python3 scripts/check_environment.py` on macOS/Linux. The check is read-only and
works offline. It reports Python, FFmpeg/ffprobe and compatible Deno/Node versions.

Windows users can run `install-missing.bat` after checking. This opens the
prerequisite helper, lists missing/incompatible components and asks before each
WinGet installation. It uses exact package IDs and does not accept publisher
agreements automatically or reinstall working components. This is an **online
setup kit**, not an offline bundle. No installer is launched by the checker.

Alternatively, install missing prerequisites using their publishers' instructions:

- Python 3.11+: https://www.python.org/downloads/
- FFmpeg and ffprobe: https://ffmpeg.org/download.html
- Deno 2.3+: https://docs.deno.com/runtime/getting_started/installation/
- Alternatively, Node.js 22+: https://nodejs.org/en/download

Deno and Node are alternatives; both are not required. Reopen the terminal after
installation so PATH changes are visible, then repeat the check. This repository
does not redistribute third-party runtime binaries.

Start `start-local.bat` / `start-local.sh` and use the printed localhost URL. This
mode only accepts loopback binding, uses `data/local-device/`, and overrides old
hosting origin/cookie/access-key/proxy settings without modifying `.env`. Older
tasks remain in their original data directory and can be opened with the original
launcher. On first run,
the launcher installs project Python dependencies into `.venv`. Media is fetched
directly by that computer and saved through the local browser interface. Keep
the launcher open during downloads. A website cannot start a missing local
service merely by linking to localhost.

## Android

The App bundles its extraction and media-processing engines; users do not install
Python or FFmpeg separately. Share a text video link to ClipNest or paste it into
the App. Shared text is inserted for review only: it does not trigger a network
request or start a download. Tap Analyze, select a format and confirm normally.

Task storage, pause/resume checkpoints and cancellation cleanup remain on the
phone. Exported files are separate from the App's task cache. Resume remains
dependent on the source; Android background restrictions still apply.

The APK is currently a local development preview. Physical-device/live-platform
acceptance, production signing and matching native dependency source/notices
remain required before public binary distribution. See
[Android distribution status](https://github.com/xialuyu5-oss/clipnest/blob/main/clients/android/NATIVE_DISTRIBUTION.md).

## Deferred

WeChat Mini Program work follows PC/Android. Existing direct-MP4 support is not
full platform extraction. iOS still requires its own native engine adapter and
build/signing environment. Neither edition uses a hidden server fallback.

The static `site/` entry point checks local readiness and opens the complete local
Web interface automatically. It never sends a video link to the website host or
proxies media. The secondary Android `clipnest://open` link remains available;
browser-to-App handoff still needs real-device/browser acceptance.
Build the local website and PC packages with `python scripts/build_local_site.py`.
No GitHub Pages deployment is included in these local changes.
