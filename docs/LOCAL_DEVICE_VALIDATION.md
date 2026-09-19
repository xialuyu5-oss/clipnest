# Local-device iteration — 2026-09-19

This record describes local validation for changes after v1.4.0-alpha.1, before
publication. GitHub deployment is a separate step; these checks alone do not
establish a live website. APK publication and Mini Program work are not included.

## Implemented

- PC environment checker works before Python is installed (Windows PowerShell).
  The optional online setup kit selects only missing/incompatible Python,
  FFmpeg/ffprobe and JS runtime packages, asking before every WinGet installation.
- `start-local.bat` / `start-local.sh` select loopback-only local mode, independent
  task storage and no configured download proxy. Existing `.env` is not edited.
  A dedicated mode flag enforces settings after dotenv loading even when Windows
  drops inherited empty environment values.
- Android alpha.2 accepts text-share intents into its bundled UI and supports
  `clipnest://open`. Receiving a link does not analyze or download it. A new link
  invalidates an older analysis/confirmation, including in-flight analysis results.
- The 12-language website now checks local readiness first. Ready devices
  automatically open the complete local Web UI in the same tab, keeping language.
  Missing components get precise install links; unreachable services remain
  unknown, without false claims that software is absent. APK status remains pending.

## Website-first correction verification

- Final release preparation: all 134 Python tests passed, including discovery,
  environment and HTTPS-origin validation. The earlier intermediate run passed 130
  tests before the four origin-configuration cases were added.
- Discovery is local-mode-only, loopback-only, read-only and returns four readiness
  flags. Tests check allowed/denied origins, DNS rebinding, remote peers, preflight,
  dependency failures, no session issuance and unchanged task/account API isolation.
- Browser check: real disconnected state; deliberately simulated missing FFmpeg
  with other components ready; then actual host component checks and automatic
  navigation to the complete downloader. Arabic selection survived the handoff.
  Chinese narrow layout had no horizontal overflow at 390px; action buttons were
  about 51px high. The missing-component simulation did not uninstall anything.
- Frontend tests cover all 12 catalogs, inconsistent/invalid discovery responses,
  blocked connections, credential-free checks, fixed local destination and one-time
  language handoff. Full existing Web frontend/i18n checks passed.
- Public HTTPS-to-loopback permission flow and clean-machine installation remain
  unverified. The component must be running; no background service was installed.

## Executed verification

- Earlier PC/Android iteration: 119 Python tests passed using the existing project dependency environment.
  Windows subprocess tests ran outside the filesystem sandbox after it blocked
  overlapped-pipe creation. Two dependency deprecation warnings remain.
- Windows installer-selection tests passed without invoking installers. Current
  machine detection correctly accepts Node 24 with no Deno installed.
- Actual extracted PC package startup passed with a deliberately stale hosting
  `.env`. Confirmed local session, refusal without download confirmation, original
  demo completion, byte-identical file delivery and deletion of the task cache.
  This test reused installed dependencies; it is not a clean-machine installation.
- Existing Web frontend/i18n and shared/native UI checks passed. The static site
  has 12 complete catalogs; desktop and 390px layouts were visually checked,
  including Chinese and Arabic RTL, with no horizontal overflow. Primary buttons
  exceed 50 CSS pixels in height; download links have a 44px minimum touch height.
- Android ARM64 and x86_64 development APKs built; lint: 0 errors, 2 existing
  warnings. Four Android 16 x86_64 instrumentation tests passed, including actual
  bundled yt-dlp loopback transfer and FFmpeg splitting/merging, confirmation/cache
  controls, shared-link prefill without execution, stale confirmation reset and
  script-text rejection. OS resolution of `clipnest://open` returned the ClipNest
  Activity successfully.

## Still unverified / deferred

Clean-machine prerequisite installation, macOS/Linux startup, physical Android
devices, live platform compatibility, mobile-browser-to-App handoff and production
signing remain unverified. The Android native corresponding-source/notice gap
still blocks public APK distribution. Website publication requires a separate
explicit upload request and final scope confirmation. WeChat is deferred; iOS has
no implementation. These checks do not establish all-platform download support.

Reproduction commands are in [local processing](LOCAL_PROCESSING.md) and the
[Android guide](https://github.com/xialuyu5-oss/clipnest/blob/main/clients/android/README.md). `scripts/smoke_local_package.py`
accepts an archive, a new output directory and an existing Python dependency
site-packages directory; it does not install dependencies or contact video sites.
