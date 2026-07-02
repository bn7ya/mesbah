# src-tauri/ — desktop shell (Tauri 2)

A thin native window: spawn the local FastAPI backend (`python -m uvicorn`,
port 8077), wait for it, navigate to `http://127.0.0.1:8077` where the backend
serves the built SPA same-origin. Python + the ML stack are the **user's** —
nothing is frozen into the bundle.

## What the bundle ships (`bundle.resources` in tauri.conf.json)

`backend/app`, `backend/scripts`, `backend/requirements*.txt`, and the built SPA
at `frontend/dist/frontend/browser` — laid out in the resource dir exactly as the
backend expects (`_frontend_dist()` globs `../frontend/dist/*/browser`). Map-form
resources only: **directory sources, never globs** (map globs flatten to file
names), and single files must map to the full target *file* path. There are no
exclude patterns, so a local build sweeps any `backend/app/**/__pycache__` into
the bundle — release installers come from CI's clean checkout.

## Backend resolution order (`resolve_backend_dir` in src/main.rs)

1. `MISBAH_BACKEND_DIR` env var
2. debug builds only: the repo checkout — **tauri-build copies
   `bundle.resources` into `target/debug/` on every build**, so without this the
   stale snapshot at `<exe>/backend` would shadow the live repo during `tauri dev`
3. `<resource_dir>/backend` (Windows install dir, `/usr/lib/Misbah` in the .deb,
   `$APPDIR/usr/lib/Misbah` in an AppImage)
4. `<exe>/backend` and up to 6 parent dirs, then the compile-time repo path

When the chosen backend is the bundled one, the shell sets `MISBAH_DATA_DIR` to
`app_local_data_dir()/data` (e.g. `%LOCALAPPDATA%\com.misbah.studio\data`) so the
DB/HF cache/models never live in the install dir; dev runs keep `backend/data`.

## Windows notes

Release builds are GUI-subsystem: every spawned child needs
`creation_flags(CREATE_NO_WINDOW)` or it pops a console. Python discovery falls
back to the `py -3` launcher; candidates are probed with `--version` because the
Windows Store `python.exe` alias stub spawns "successfully". Installers are built
by `.github/workflows/desktop.yml` (Windows-only cross-compile is not possible).
