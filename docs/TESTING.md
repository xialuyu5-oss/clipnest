# Validation and reproduction

Recorded baseline: **v1.3.0, 2026-09-17**. This document distinguishes code checks, local real-engine tests and live-platform acceptance.

## Local platform update — 2026-09-20 (unreleased)

- Publication presentation checks: the 12-language product preview passed desktop
  and 320px layout checks for every locale, English default, Arabic RTL, image
  decoding and Chinese language handoff into the standalone interface. Saving its
  original 480p demo produced bytes identical to the bundled fixture. No browser
  page errors or external requests were observed. Three current interface images
  were captured from that original-demo flow, without account or platform media.
- `python -m pytest tests -q`: **226 passed**, with the two existing third-party
  deprecation warnings. New checks cover dedicated extractor routing, short links,
  access query parameters, full Ixigua IDs, domain lookalikes, thumbnail hosts,
  Web/Android policy consistency and byte-preserving logo packaging. Local proxy
  checks cover loopback-only validation, explicit launcher propagation, stale
  hosting-setting isolation, Fake-IP error mapping and private-address rejection
  outside the single configured proxy endpoint.
- Frontend and shared-client regressions passed. Internationalization checks passed
  for all 12 Web locales and 330 keys per locale.
- `scripts/build_preview.py` and `scripts/check_preview.py` passed: 19 decoded local
  brand icons, desktop/light/dark, 320px modal minimum sizes, Chinese names, Arabic
  RTL and the existing original-demo save/delete flow. No browser page errors.
- Public metadata checks did **not** establish live compatibility for the nine new
  platforms. Douyin requested fresh cookies; the other eight checks were stopped
  by the existing network guard in this environment. [Exact scope](PLATFORMS.md).
- A subsequent local VPN fix was verified through the running service's session
  and `/api/analyze` routes: the public Captain America X video
  `719944021058060289` returned HTTP 200, duration 3.17 seconds, and 720p/360p/180p
  options with frame rates and audio codecs. This used the existing local HTTP
  proxy with the address guard enabled. No full video download was started; the
  user's screenshot URL and the nine added platforms were not revalidated by
  this check. An older Star Wars sample returned unavailable.
- No new Android APK/device acceptance, WeChat platform parsing, iOS implementation
  or GitHub/Pages/Release publication is claimed for this update.

## Earlier recorded results

| Check | Result and scope |
| --- | --- |
| Python suite | **114 passed**; core behavior, access/session handling, account flow, probing, lifecycle/persistence and real-engine tests. Some cases mock platform responses |
| Frontend regression | Passed; request/state behavior, audio labels, login/cancellation handling, ETA scope and pause/resume controls |
| Internationalization | Passed; 12 locales, 311 keys per locale, placeholders, language persistence and RTL behavior |
| Real HTTP resume | Actual yt-dlp worker stopped mid-transfer, then resumed the same local fixture at the retained byte offset; final bytes matched |
| Real HLS resume | Actual yt-dlp reused completed fragments; final FFprobe check confirmed 480p, audio and approximately 6 seconds |
| Full-service browser demo | Original 1080p demo became ready with 1920×1080 / 24 fps / audio; task deletion verified |
| Responsive browser | 860px split-pane English, 320px German, approximately 390px Arabic RTL; no horizontal overflow or observed input/action-label clipping |
| Publication preview | Real browser checked English default, Chinese/Arabic switching, demo quality selection, save/delete, dark theme, 390px and 320px layout; no page errors |
| Web release archives | ZIP and tar.gz contained the same 31 payload files; hashes and repeat-build byte equality passed. Extracted ZIP started on Windows, served UI/translation assets, and completed a 480p original-demo download and task deletion using the existing Python environment |

Two third-party deprecation warnings were present in the recorded Python run. A previous anonymous X sample completed analysis and a 720p file with audio, but that is a historical sample, not a current multi-platform compatibility guarantee.

## Run the checks

Use Python 3.11+, FFmpeg/FFprobe and Node.js. Create/activate a virtual environment and install `requirements-dev.txt`.

```sh
python -m pytest tests -q
node tests/test_frontend.mjs
node tests/test_i18n.mjs
```

Use the explicit `tests` path. The real-engine tests create throttled loopback HTTP/HLS fixtures from the original bundled demo and launch actual worker/FFmpeg subprocesses. They need local sockets and process creation; they do not require a platform account or a live source video.

For a browser preview check, install Playwright's Chromium or point `CHROMIUM_EXECUTABLE` at an existing compatible Chrome/Edge binary:

```sh
python -m playwright install chromium
python scripts/build_preview.py
python scripts/check_preview.py
```

The check opens the standalone preview, saves a bundled original demo in the test output directory and captures screenshots. It does not test live platform extraction. `CLIPNEST_TEST_OUTPUT` can select an output directory. Generated output is excluded from Git.

`requirements-tested.txt` records Python package versions from the local validation environment. It is not an immutable cross-platform lock, and external FFmpeg/JS runtimes are separate prerequisites.

## Still unverified

- Current real URLs on all 19 integrated platforms, including separate-track downloads on each.
- Completed Bilibili member authorization, actual member-only HD, and official app album recognition.
- Real-platform pause/resume across expired source links and all source-specific protocols.
- Ordinary phone/LAN network access and public deployment.
- Docker image build/run and macOS machine startup.
- Fresh dependency installation from the release archive on a clean machine; archive startup used the already validated Python environment.
- Android physical-device/live-platform acceptance and WeChat Developer Tools/phone behavior; the new implementations are described below. iOS remains unimplemented.
- Production concurrency, long-term storage operation and independent security audit.

Before claiming support for a specific scenario, test a video the operator is authorized to download, inspect final dimensions/audio/duration, and record the platform, mode and date. Do not publish cookies, signed media links, private videos or unredacted account logs as evidence.

## Mobile preview 1.4.0-alpha.1

Validation on 2026-09-17:

| Check | Executed evidence |
| --- | --- |
| Android builds | ARM64 and x86_64 development APKs compiled; lint reported 0 errors and 2 warnings (bundled-view JavaScript review and a newer-Gradle advisory) |
| Android 16 x86_64 emulator | Three instrumentation tests passed: native bridge/demo/language switching without horizontal overflow; consent rejection, ready-file validation and deletion; bundled Python/yt-dlp real loopback HTTP download with matching hash and FFmpeg split/remux with audio/video validation |
| Shared client logic | URL boundaries, actual format interpretation, audio states, portrait quality, confirmation estimates and task actions passed |
| Mobile languages | 12 catalogs, 321 keys each, matching placeholders and interface/state label coverage passed; German, Arabic and Chinese switching also exercised on Android |
| Mini Program adapter | Real HTTP fixture proved metadata Range sampling, pause/reload/resume offsets, identical output bytes, changed source rejection, ignored Range handling and cancellation cleanup. A mocked native full-file transfer exercised restart fallback and album-save deletion protection |
| MP4 parser | Actual original 480p/720p/1080p fixtures: duration, dimensions, 24 fps, AVC/AAC; malformed input passed |

Run portable checks with Node.js:

```sh
node tests/test_client_core.cjs
node tests/test_client_i18n.cjs
node tests/test_mp4_metadata.cjs
node tests/test_wechat_downloads.cjs
```

Build/test Android as documented in [its README](../clients/android/README.md). Tests use a dedicated debug application and original local media; they do not prove live-site extraction, physical ARM64 compatibility, battery/background behavior, real-source pause/resume or every system document provider. The emulator screenshot is an actual UI capture. WeChat adapters have not been compiled in Developer Tools or run inside WeChat; wx API mocks are not a substitute for that acceptance. No iOS validation is claimed.
