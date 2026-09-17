# Android dependency and distribution notes

The Android app is GPL-3.0-only. This applies to the Android subtree; the Web service and independently reusable MIT modules retain their licenses.

| Dependency | Pinned declaration | Role |
| --- | --- | --- |
| youtubedl-android | `io.github.junkfood02.youtubedl-android:library:0.18.1` | Bundled yt-dlp/Python/QuickJS initialization; GPL-3.0 project |
| youtubedl-android FFmpeg | `io.github.junkfood02.youtubedl-android:ffmpeg:0.18.1` | Android FFmpeg/FFprobe binaries and supporting libraries |
| AndroidX WebKit | `androidx.webkit:webkit:1.14.0` | Asset origin and message bridge; Apache-2.0 project |
| Gradle wrapper | 8.13 | Build bootstrap; Apache-2.0 project |

Upstream: [youtubedl-android](https://github.com/yausername/youtubedl-android/tree/0.18.1), [AndroidX](https://android.googlesource.com/platform/frameworks/support/), [Gradle](https://github.com/gradle/gradle/tree/v8.13.0), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [FFmpeg](https://ffmpeg.org/legal.html).

The wrapper's license does not replace the notices/obligations of bundled Python, yt-dlp, QuickJS, FFmpeg codecs and transitive components. Before publicly distributing any binary, including a preview, audit the actual AAR/native payload, retain applicable notices, provide corresponding source and build information required by its licenses, and record exact artifact checksums. A versioned dependency URL alone is not a claim that this distribution-source audit has been completed. The locally built APKs are currently for owner testing; public binary distribution remains pending this audit.

The [native distribution report](NATIVE_DISTRIBUTION.md) and [payload inventory](native-payload-inventory.json) document the inspected binaries and the missing matching-source/build records. Public release attachments exclude these APKs until that work is complete.

This preview does not auto-update its engine or fetch remote JavaScript components at runtime. No private developer signing material belongs in this repository or in a Release source archive.
