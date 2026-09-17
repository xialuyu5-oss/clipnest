# Source and release conventions

## Repository scope

Keep application source, editable language catalogs, requirements/feature history, tests and maintenance tools, environment/build configuration, licenses and documentation. Screenshots live in `docs/images/` as documentation. The original demo media is needed by the demo and real-engine tests.

Generated previews, duplicate launch shortcuts, release archives, installed runtimes, downloaded user media and signing secrets are not source assets. Dockerfile/Compose are environment recipes and remain source-controlled; a built image is a separate artifact.

## Platform matrix

| Target | Intended deliverable | Current state |
| --- | --- | --- |
| Web | `clipnest-v<version>-web.zip`, `.tar.gz`, installation guide, checksums | Builder implemented for the Python service plus browser UI; Windows local app validated |
| Docker | Rebuild recipe; versioned image only after a successful build/runtime check | Recipe only; no validated or published image |
| Android | Release-signed APK for direct installation; signed AAB for Google Play when applicable | On-device source project and local development APKs; public APK attachments held pending matching native source/notices; production signing/store acceptance pending |
| iOS | Tested signed build distributed by an applicable Apple channel; Release notes link to TestFlight/App Store when available | Requested **on-device** analysis/download; app not implemented, no signed build |
| WeChat Mini Program | Source/build package for its developer workflow; version and actual approved access entry when available | Entirely on-device direct-MP4 development project; no share-page extraction, real AppID, device verification or published entry |

Development-signed APKs may be clearly labeled preview/testing artifacts; never present them as production-signed finished releases. Unsigned binaries are not ready-to-install releases. A source ZIP or responsive webpage is not an Android/iOS app. GitHub provides source archives from the release tag automatically; custom assets are separately built deliverables.

The independent-mobile requirement and acceptance criteria are recorded in [MOBILE_TARGETS.md](MOBILE_TARGETS.md). The [v1.4.0-alpha.1 prerelease notes](releases/v1.4.0-alpha.1.md) describe a common source snapshot, the unchanged [Web v1.3.0 deployment](releases/v1.3.0.md) and the Mini Program developer package. No separate v1.3.0 tag is implied; local notes do not establish publication. The Android binary's third-party notices/corresponding-source audit remains a gate before public distribution, including preview binaries.

Android APK installation requires signing; AAB is a publishing format used by Google Play to generate installable APKs. Keep release signing keys outside Git and retain key continuity for updates. See [Android signing](https://developer.android.com/studio/publish/app-signing) and [App Bundles](https://developer.android.com/guide/app-bundle).

iOS distribution requires the appropriate signing/provisioning and channel. A generic IPA attachment is not universally installable. TestFlight and App Store distribution require the relevant Apple developer setup and validation. See [Apple distribution](https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases). App Store review also has specific third-party media download authorization requirements in [section 5.2.3](https://developer.apple.com/cn/app-store/review/guidelines/); a user consent checkbox alone does not establish source-platform authorization.

Current WeChat rules were not verified in this review because access to the official documentation was blocked. Do not promise a file-size allowance, domain policy, download behavior, approval or a release QR code until the current official rules and actual project have been checked. GitHub attachments alone do not establish that a Mini Program is live.

## Build the Web assets

```sh
python scripts/build_release.py
```

The builder reads the version from `app/main.py`, assembles an explicit allowlist and writes to `dist/v<version>/`. It produces both archive formats, `SHA256SUMS.txt`, and `release-manifest.json` with payload and archive hashes. It does not upload, create a tag, run a cloud build or sign mobile apps. It refuses to overwrite an existing output file.

The archives contain the runtime UI bundle, not the editable translation catalogs or developer tests. Those remain in the source repository. Prerequisites are installed separately according to the included guide. Reproducible archive metadata is useful for comparing builds, but the dependency ranges/base-image tags do not make the whole installed environment reproducible.

## Release procedure

1. Choose a version/tag and a specific source commit. Record the supported runtime and tested device/OS scope.
2. Run relevant backend/frontend/i18n checks. Build artifacts from that reviewed source; verify extraction and startup of the archive.
3. Inspect the allowlisted payload, checksums, secrets exclusions, installation/upgrade steps and known limits.
4. Write release notes naming only actual assets. Missing platforms remain explicitly unavailable, with no fake download links or QR codes.
5. Confirm repository owner, public visibility, source contents and release attachments with the project owner before external publication.
6. Create the approved tag/release, attach the verified assets and hashes, then download/read back the published result. A checksum is not a cryptographic publisher signature.

When a new platform is unfinished, it must not block honest naming of existing artifacts or be implied to ship in the same version. Use separate platform versions/prerelease labels if the implementations diverge, and document compatibility.

Reference: [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

## Current prerelease attachment set

For `v1.4.0-alpha.1`, keep the reviewed Web ZIP/tar.gz unchanged and include the WeChat developer-source ZIP. `publication-manifest.json` records their checksums and embeds the two builders' payload inventories; `SHA256SUMS.txt` covers all three packages and that manifest. Android application source is in the tag, but the local APKs are excluded pending the [native distribution work](../clients/android/NATIVE_DISTRIBUTION.md). Do not substitute the owner-testing mobile manifest for this public attachment inventory.
