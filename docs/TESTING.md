# Validation and reproduction

Recorded baseline: **v1.3.0, 2026-09-17**. This document distinguishes code checks, local real-engine tests and live-platform acceptance.

## Recorded results

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

- Current real URLs on all 10 integrated platforms, including separate-track downloads on each.
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
