# Shared client contract (MIT)

`core.js` is a dependency-free domain module shared by the Android bundled interface and the WeChat Mini Program. It can also be loaded inside a future iOS WKWebView. It contains URL validation, source-format interpretation, quality selection, download confirmation estimates and task controls. This does not make the Android engine compatible with iOS.

Native adapters use asynchronous JSON messages:

```json
{"id":"request-id","method":"analyze","params":{"url":"https://…"}}
```

Responses contain the same `id` and either `result` or `error: {code, message}`. Never accept shell commands, output paths, cookies or arbitrary yt-dlp arguments from the interface. A native adapter owns analyzed formats, validates confirmation and selected IDs, and confines job files to its app directory.

Methods: `capabilities`, `analyze`, `demo`, `downloads`, `start`, `pause`, `resume`, `remove`, `save`.

- `start`: `{analysis_id, option_id, rights_confirmed, download_confirmed}`.
- Controls: `{id}` referring to a native-owned task.
- States: `queued`, `downloading`, `processing`, `paused`, `ready`, `error`.
- Task fields match the Web API: `id`, `title`, `quality`, `container`, `state`, `progress`, `downloaded`, `total`, `speed`, `eta`, `eta_scope`.
- `eta_scope: track` means the current track only, never the whole task.
- `save` launches the platform's save/export picker. Ready in the app sandbox is distinct from exported.
- Capabilities must report where extraction runs, engine availability and platform-specific limitations.

Android implements the adapter locally. WeChat uses its own native page components and an entirely on-device HTTPS MP4 adapter; a companion service was explicitly declined. Platform share-page extraction remains unfinished in that adapter. iOS needs a separate embedded/native engine, background-session integration and file-export adapter. No iOS implementation or build is claimed by this shared module.
