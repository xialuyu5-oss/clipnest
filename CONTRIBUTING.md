# Contributing

ClipNest is a user-directed project developed with **OpenAI Vibe Coding (ChatGPT and Codex)**. Contributions should preserve observable behavior, clear evidence, and the distinction between implemented features and verified platform support.

## Local workflow

1. Read [README](README.md), [requirements](docs/REQUIREMENTS.md), and the relevant component in `app/` or `web/`.
2. Use a dedicated `.venv` with `requirements-dev.txt`. Install FFmpeg/FFprobe and the required JavaScript runtime separately.
3. Keep changes focused and run checks appropriate to the changed behavior. The baseline commands are in [TESTING.md](docs/TESTING.md).
4. For UI changes, inspect desktop, narrow/mobile layouts, long translated text and Arabic RTL.
5. Update documentation when behavior or verification scope changes. Never claim universal platform support from a mocked test or a demo download.

## Localization

- Translation catalogs are `web/assets/locales/*.json`, with English source strings as keys.
- HTML uses `data-i18n`; dynamic text uses `ClipNestI18n.t()`.
- Run `python scripts/build_i18n.py` after changing catalogs, then `node tests/test_i18n.mjs`.
- A new language also needs an entry in `web/assets/i18n.js`.
- Preserve placeholders and keep original media titles, authors and descriptions untranslated.
- Backend error codes must be mapped in the frontend; the test suite checks coverage.
- Run `python scripts/build_preview.py` to generate the ignored standalone preview after frontend changes.

## Release packaging

Run `python scripts/build_release.py` to create Web deployment archives and checksums under the ignored `dist/` directory. The builder uses a file allowlist rather than archiving the working directory. Native app binaries and platform signing material must not be committed. See [release conventions](docs/RELEASING.md); the current release builder does not create Android, iOS or WeChat applications.

## Reports and examples

Describe the version, operating system, deployment mode, steps, expected behavior and actual result. Use the original demo or a source you are authorized to share. Remove cookies, access keys, signed URLs, private media and personal paths from reports. Do not post real `.env`, `data/` or diagnostic logs without reviewing them.

The project has no dedicated private security-reporting channel configured. Avoid posting exploit details or secrets in public issues; arrange a private maintainer contact first if the report requires it.
