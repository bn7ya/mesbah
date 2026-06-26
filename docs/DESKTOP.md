# Desktop app (Tauri)

Misbah ships an optional **desktop shell** (`frontend/src-tauri/`) built with
[Tauri 2](https://tauri.app). It is a thin native window that:

1. **launches the local backend** (`uvicorn app.main:app --port 8077`) using the
   Python environment already on the machine,
2. waits for `GET /api/health` to answer, then
3. points the window at `http://127.0.0.1:8077`, where the backend serves the
   built Angular UI **same-origin** (so `/api` and the WebSockets stay relative —
   no CORS, no URL rewrite).

The heavy ML stack (torch / CUDA / Unsloth) is **not** frozen into the installer —
it must match the user's GPU drivers and is installed via `requirements-ml.txt`.
The desktop app is a launcher for the local studio, not a self-contained bundle.

## Build prerequisites

- The Angular + Python prerequisites from the main README.
- **Rust toolchain** (`rustup`, stable) — Tauri compiles a small native binary.
- Platform webview/build libs:
  - **Linux**: `webkit2gtk-4.1`, `libgtk-3-dev`, `librsvg2-dev`, `patchelf`, `build-essential`
    (Debian/Ubuntu: `libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev patchelf`).
  - **Windows**: the WebView2 runtime (preinstalled on Windows 11) + the MSVC build tools.

## Build

```bash
cd frontend
npm install
npm run tauri:build      # runs `ng build` first, then bundles the installers
```

Artifacts land in `frontend/src-tauri/target/release/bundle/`:

| Platform | Targets |
|----------|---------|
| Linux    | `deb/Misbah_*.deb`, `appimage/Misbah_*.AppImage` |
| Windows  | `nsis/Misbah_*-setup.exe`, `msi/Misbah_*.msi` |

> Windows installers must be built **on Windows** (Tauri does not cross-compile the
> webview). The same `npm run tauri:build` command produces the `.exe`/`.msi` there.

> **AppImage on a host without FUSE** (CI, containers, some sandboxes): the bundler's
> `linuxdeploy` step needs FUSE. If it fails, build with extract-and-run:
> `APPIMAGE_EXTRACT_AND_RUN=1 NO_STRIP=1 npm run tauri:build -- --bundles appimage`.
> The `.deb` does not need FUSE.

## Run (development)

```bash
cd frontend
npm run tauri:dev        # opens the window, spawns the backend, loads the studio
```

## How the backend is located

On launch the shell resolves the `backend/` directory in this order:

1. `MISBAH_BACKEND_DIR` env var (if it contains `app/main.py`),
2. a few locations relative to the executable (`<exe>/backend`, parents…),
3. the repo path baked in at compile time (dev convenience).

The Python interpreter is `MISBAH_PYTHON` (default `python`). If the backend can't
be found or started, the splash screen shows a setup hint. The spawned backend is
stopped when the window closes.

For a packaged install, ship the `backend/` folder alongside the app (or set
`MISBAH_BACKEND_DIR`) and ensure the Python env has `requirements-ml.txt`.
