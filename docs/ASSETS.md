# Code, assets and third-party credits

The Web service, independently reusable interface/shared modules and Mini Program use the root [MIT license](../LICENSE). The Android application subtree uses [GPL-3.0-only](../clients/android/LICENSE), as approved for its native engine integration. That application license does not relicense the independent modules.

**Development attribution:** the project code was developed through **OpenAI Vibe Coding**, using OpenAI ChatGPT and Codex with user-provided requirements, feedback and revision decisions. This independent project is not an official OpenAI product or endorsement.

## Original demo media

`web/assets/demo-cover.svg`, `demo-1080.mp4`, `demo-720.mp4` and `demo-480.mp4` were generated for this project. They are abstract demo assets, not videos downloaded from a source platform. The videos are approximately 6 seconds at 24 fps, with audio and actual dimensions of 1920×1080, 1280×720 and 854×480 respectively.

These listed original demo assets are contributed under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/legalcode). This applies only to those assets, not to content obtained from third-party platforms. `scripts/make_demo.py` can regenerate the media with its documented local prerequisites.

`docs/images/desktop.png` and `docs/images/mobile.png` show this project's interface using only its bundled original demo. They were captured from the offline preview for documentation and contain no user account, private video or conversation UI. They follow the project documentation's MIT license.

The interface uses system fonts and project SVGs; system font binaries are not bundled. The demo generator may render text using fonts installed on the generation machine.

`docs/images/android.png` is an actual screenshot of the Android preview on the project's isolated emulator. It shows the bundled interface and no platform account or third-party video. It is documentation under MIT, not evidence of a live-platform download. There is no fabricated WeChat screenshot: its developer-tool/device appearance is still unverified.

## Dependencies and platform names

FastAPI, Uvicorn, yt-dlp, FFmpeg, Deno, Node.js, Playwright and other dependencies retain their own licenses. Project MIT licensing does not replace those licenses or determine obligations for a separately distributed container image.

Platform names identify compatible source integrations and do not imply affiliation, certification or endorsement. The repository includes no platform account cookies, private keys or downloaded third-party media. Downloaded media remains subject to its own rights and permissions.
