# Android native payload: distribution status

The Android application source is available under GPL-3.0-only. **The locally built APKs are not included in the public release attachment set:** the corresponding-source and notice record for their bundled native dependencies is incomplete. Successful compilation and emulator tests do not resolve that gap.

This is a finding about the evidence assembled for this project's binaries, not a conclusion about an upstream project's compliance.

## What was inspected

The ARM64 and x86_64 development APKs built with `youtubedl-android` library and FFmpeg artifacts **0.18.1** were inspected on 2026-09-17. [The payload inventory](native-payload-inventory.json) records the APK and embedded archive hashes and individual shared-object paths/hashes.

| Embedded archive | ARM64 shared-object paths | x86_64 shared-object paths |
| --- | ---: | ---: |
| `libffmpeg.zip.so` | 113 | 113 |
| `libpython.zip.so` | 148 | 150 |

These are file-path counts, not counts of distinct packages: one dependency can install several libraries or aliases. FFmpeg's recorded configuration enables GPL and version-3 components; `--enable-nonfree` was not found. The payload includes libraries such as x264, x265, FFTW and Rubber Band, as well as Python and its native dependencies.

No license/notice/package-metadata **filenames** were found inside these two embedded archive types by the inventory check. This does not establish the absence of embedded copyright strings or notices elsewhere in the upstream distribution.

## What is missing

The upstream [FFmpeg build guide](https://github.com/yausername/youtubedl-android/blob/0.18.1/BUILD_FFMPEG.md) describes a Termux-based build, but does not identify the exact Termux revision and source versions of every component in these downloaded binaries. The [Python build guide](https://github.com/yausername/youtubedl-android/blob/0.18.1/BUILD_PYTHON.md) is also not an exact build record for this payload.

Linking the wrapper's tagged repository alone therefore does not establish a complete corresponding-source package for all native components. The distribution record still needs component versions, applicable notices/license texts, matching source and patches, and the build material required by their licenses. See [FFmpeg's own licensing guidance](https://ffmpeg.org/legal.html) and the [GPL text](LICENSE).

## Steps before attaching an APK

1. Map the inventory to exact upstream component versions, patches and build recipes, including transitive native dependencies.
2. Assemble and verify the required notices and matching source/build materials for those binaries. If the original build cannot be traced sufficiently, build a replacement from pinned sources and keep its complete build record.
3. Rebuild and retest if the payload changes. Record checksums for the final APKs and the accompanying source/notices bundle.
4. Review the final distribution set. Label development signatures and tested devices accurately; production signing and broader device acceptance are separate work.

The current APKs remain local owner-testing artifacts. Web deployment archives and the WeChat developer-source package do not bundle these Android native archives.
