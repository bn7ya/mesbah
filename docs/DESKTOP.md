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

The installers **do** ship the backend source and the built SPA
(`bundle.resources`): `backend/app`, `backend/scripts`, `backend/requirements*.txt`
and `frontend/dist/frontend/browser` land in the app's resource dir, so an
installed app finds its backend without any manual copying. Only Python itself
(+ `pip install -r requirements*.txt`) remains the user's job.

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
> Without a Windows machine, use CI: the **Desktop installers (Windows)** workflow
> (`.github/workflows/desktop.yml`) builds both on `windows-latest` — run it from
> the Actions tab (workflow_dispatch) and grab the `misbah-windows-installers`
> artifact, or push a `v*` tag to attach them to a GitHub Release. The NSIS
> `-setup.exe` is the recommended installer (per-user install, Arabic/English
> installer UI); binaries are unsigned, so SmartScreen shows a warning on first run.

> **AppImage on a host without FUSE** (CI, containers, some sandboxes): the bundler's
> `linuxdeploy` step needs FUSE. If it fails, build with extract-and-run:
> `APPIMAGE_EXTRACT_AND_RUN=1 NO_STRIP=1 npm run tauri:build -- --bundles appimage`.
> The `.deb` does not need FUSE.

## Run (development)

```bash
cd frontend
npm run tauri:dev        # opens the window, spawns the backend, loads the studio
```

> `tauri:dev` runs an `ng build` first (`beforeDevCommand`) — the SPA build must
> exist because `bundle.resources` references it at compile time.

## How the backend is located

On launch the shell resolves the `backend/` directory in this order:

1. `MISBAH_BACKEND_DIR` env var (if it contains `app/main.py`),
2. **debug builds only**: the repo checkout (so `tauri dev` never picks the stale
   resource snapshot that tauri-build copies into `target/debug/`),
3. the bundled copy in the app's **resource dir** (the install dir on Windows,
   `/usr/lib/Misbah` for the `.deb`, `$APPDIR/usr/lib/Misbah` in an AppImage),
4. a few locations relative to the executable (`<exe>/backend`, parents…), then
   the repo path baked in at compile time (dev convenience).

The Python interpreter is `MISBAH_PYTHON` if set; otherwise the shell probes
`python`, then `python3` (Linux/macOS) or the `py -3` launcher (Windows). If the
backend can't be found or started, the splash screen shows a setup hint. The
spawned backend is stopped when the window closes.

When the **bundled** backend is used, the shell sets `MISBAH_DATA_DIR` to the
per-user app-data dir — `%LOCALAPPDATA%\com.misbah.studio\data` on Windows,
`~/.local/share/com.misbah.studio/data` on Linux — so the SQLite DB, HF cache,
downloaded models and trained adapters never live in the install dir and survive
uninstall/updates. Dev runs keep using `backend/data`.

## First run on Windows

1. Install **Python 3.11+** from python.org ("Add python.exe to PATH" is optional —
   the shell falls back to the `py` launcher). For a conda env, point
   `MISBAH_PYTHON` at its `python.exe`.
2. `pip install -r requirements.txt` (from the installed `backend/` folder — the
   GUI, projects and authoring work with just this), then `requirements-ml.txt`
   for chat/training (needs a CUDA-matching torch build; native-Windows ML support
   is best-effort).
3. Launch **Misbah** — the splash waits for the backend, then opens the studio.
