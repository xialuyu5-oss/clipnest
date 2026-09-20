# Changelog

This repository starts from the consolidated v1.3.0 source. The entries below describe the local development history; they do not imply that older versions exist as Git tags or GitHub releases.

## Unreleased — 2026-09-20

- Added 12-language project introductions, current interface screenshots and a
  static product preview with an installation-free original-demo interface.
- Added an explicit local-device proxy startup option for VPNs using virtual DNS
  addresses. Private-address checks remain enabled, and the translated error now
  identifies this configuration issue instead of a generic unsafe-target failure.
- Added dedicated extractor routing for Douyin, Xiaohongshu, Weibo, Ixigua,
  AcFun, Xinpianchang, TED, Pinterest and Niconico in Web and Android source.
- Shared the guarded short-link expansion policy between both workers, retained
  access query parameters, and fixed an upstream Ixigua URL-pattern issue that
  could truncate the video ID.
- Replaced the platform modal's character symbols and homepage chips with 19
  locally bundled official website icons, with provenance and separate brand rights.
- Added responsive cards with fixed minimum icon sizes, translated platform names,
  and image-preserving offline/PC/Web packaging.
- [Validation and remaining platform restrictions](docs/PLATFORMS.md).
  Existing Release attachments remain earlier builds; the website builder includes
  the current PC package and product preview from its selected source commit.

## 1.4.0-alpha.2 / Web 1.3.1 — 2026-09-19

- Website-first environment detection: automatically enter the complete local
  downloader when ready, show verified missing components, and keep unreachable
  environments explicitly unknown.
- Added user-confirmed Windows prerequisite installation, local-only launchers,
  minimal read-only discovery and language-preserving handoff.
- Android accepts shared links and supports opening the installed App; receipt
  never automatically analyzes or downloads a video.
- Added static website packaging and an explicitly triggered Pages workflow.
  Android binary distribution remains pending; WeChat and iOS are unchanged.
- [Release contents and limits](docs/releases/v1.4.0-alpha.2.md).

## 1.4.0-alpha.1 mobile preview — 2026-09-17

- Added an Android application with bundled on-device Python/yt-dlp, QuickJS and FFmpeg, a local origin-restricted interface, foreground downloads, persistent tasks and system file export.
- Added explicit download confirmation, indicative duration/size/time, current-track ETA, pause/resume checkpoints and cancellation cleanup to the Android adapter.
- Added separate ARM64 and x86_64 development-signed APK builds. No production signing, store submission or public binary distribution is claimed.
- Added a wholly on-device WeChat development project for direct HTTPS MP4 metadata and downloads, identity-checked HTTP Range resumption, restart fallback and album export. Platform share-page extraction and separate-track merge remain unfinished.
- Extracted common UI, domain logic, 12-language catalogs and a native message contract for future iOS reuse. No iOS app is included.
- Applied the approved GPL-3.0-only license to the Android app; independent Web/shared/Mini Program modules remain MIT.
- Kept the Web runtime at v1.3.0. See [preview notes](docs/releases/v1.4.0-alpha.1.md) for exact validation and missing acceptance gates.

## 1.3.0 — 2026-09-17

- Added minimum control sizes and wrapping for narrow windows and translated labels.
- Added pre-download duration, size, and indicative transfer-time confirmation.
- Added live remaining-time estimates with whole-download/current-track scope.
- Added pause/resume, partial-file reuse, and cancellation that stops the worker before cache deletion.
- Persisted task metadata and files; interrupted tasks reopen as paused after a restart.
- Removed timed file expiry. Ready files and checkpoints stay until cancellation/deletion.
- Verified 114 Python tests, frontend/i18n checks, local real-engine HTTP/HLS resumption, and responsive browser flows.

## 1.2.1 — 2026-09-16

- Distinguished cancelled tasks from failed downloads.
- Completed frontend localization mappings for backend error codes.
- Clarified the local member-mode deployment switch and connection status.
- Updated offline preview checks for the English-default interface.

## 1.2.0 — 2026-09-16

- Made English the default UI language.
- Added 12 selectable languages, remembered choice, and Arabic RTL.
- Localized navigation, download confirmation, jobs, login, help, and errors while preserving source media text.

## 1.1.3 — 2026-09-16

- Fixed non-ASCII access/session input handling and worker environment isolation.
- Added controlled `b23.tv` and `fb.watch` short-link expansion.
- Improved bounded metadata probing, health rechecks, and merge-error classification.
- Added configurable diagnostic logging and disabled member mode in Docker Compose.

## 1.1.2 — 2026-09-16

- Replaced fixed download size/duration/total-time limits with explicit user confirmation.
- Improved estimates for completed HLS replays and incomplete media metadata.

## 1.1.1 — 2026-09-12

- Improved mobile typography, touch controls, QR image saving, and return-to-page login checks.
- Distinguished unknown audio from confirmed absence and improved default quality selection.

## 1.1 — Initial local member edition

- Added local Bilibili QR login and in-memory platform sessions.
- Kept desktop and mobile on one responsive web implementation.

## 1.0 — Initial website

- Added video-link analysis, real quality selection, yt-dlp downloading, FFmpeg merging, and FFprobe checks.
- Added download jobs, original demo media, offline UI preview, themes, and responsive layout.

## Public-source documentation

- Added English and Chinese project introductions, original requirements and changes, architecture, testing boundaries, and app-only screenshots.
- Explicitly credited **OpenAI Vibe Coding (ChatGPT and Codex)** and the user's role in requirements and feedback.
- Kept runtime configuration, credentials, downloaded media, local logs, and raw conversation records out of the publication.
- Separated source contents from generated releases; added an allowlisted Web ZIP/tar.gz builder, environment installation guide, artifact manifest and SHA-256 checksums.
- Documented each platform's actual implementation and validation status separately from responsive Web support.
