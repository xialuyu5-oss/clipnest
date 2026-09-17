# ClipNest WeChat Mini Program — entirely on-device preview

**No companion parsing/download server is used.** The user explicitly requires operation entirely on the phone. This implementation is an honest, narrower on-device client, not full feature parity with the Web/Android yt-dlp engine.

## Implemented

- Accept a public HTTPS URL ending in `.mp4` (a query string is allowed).
- Read size/range/identity headers directly from the media host.
- When HTTP ranges work, inspect MP4 atom headers and metadata to obtain duration, dimensions, frame rate and codecs where available. Media payload is skipped during analysis; the metadata sample budget does not limit the downloadable file size.
- Confirm rights, duration, size and indicative time before the full download.
- Download directly into Mini Program storage, display progress and an estimated remaining time.
- With source range support and a usable identity validator, persist chunks and resume after pause/relaunch. Compare source identity and length before appending. Reject inconsistent ranges or changed files.
- Without safe range support, use the native download API; continuing after pause restarts that transfer. The interface states this before confirmation.
- Pause on backgrounding. Cancel/delete removes this app's task file. Saving a completed MP4 invokes the user's album permission flow; files already exported are retained.
- Default English, 12 language choices and shared translations.

## Not implemented / not claimed

- YouTube, X, Bilibili and other platform **share-page parsing**.
- HLS/DASH download or combining separate video/audio streams.
- Login to source platforms, DRM decryption, unlimited background execution or universal network-domain access.
- Guaranteed platform storage quotas, maximum download duration, album codec compatibility or approval. These are governed by the actual WeChat runtime and source.
- WeChat Developer Tools compilation, real-phone validation, approved AppID or published production entry. No developer-tool installation or valid AppID was available during local preparation.

The current official documentation could not be accessed in this session. Numerical platform limits are deliberately not asserted. Verify current domain configuration, API/library version requirements, permissions and publishing rules in the official developer console before any real release. Do not turn off URL checks as a production solution.

## Prepare and open

From the repository root:

```sh
python scripts/build_clients.py
```

The output contains a complete developer-import folder and ZIP, including generated shared modules and language catalogs. It contains no hosted-service address, credentials or signing keys. `touristappid` marks a local development placeholder, not a registered/published Mini Program.

Import the generated folder into WeChat Developer Tools, select your actual project/AppID when available, and configure the required request/download domains for media hosts you are authorized to use. The Mini Program's official domain restrictions may prevent arbitrary third-party media hosts; direct-link code does not remove those restrictions. Test on both iPhone and Android WeChat before releasing.

## Local verification

```sh
node tests/test_wechat_downloads.cjs
node tests/test_mp4_metadata.cjs
node tests/test_client_core.cjs
```

The first test supplies a filesystem/request adapter backed by a real local HTTP server. It proves range offsets, byte identity, persistence/reload, cancellation cleanup and source-change handling for that adapter. The metadata test reads actual bundled MP4 files. Neither substitutes for compiling/running WXML/WXSS or validating WeChat-specific API behavior on a device.
