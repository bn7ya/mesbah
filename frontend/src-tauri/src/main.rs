// Misbah desktop shell.
//
// Tauri only WRAPS the studio: on launch it starts the local FastAPI backend
// (uvicorn) using the Python environment already on the machine, waits for it to
// answer, then points the window at http://127.0.0.1:8077 — where the backend
// serves the built Angular UI same-origin (so `/api` stays relative, no CORS).
// The heavy ML stack (torch/CUDA/unsloth) is NOT bundled; it must match the user's
// GPU drivers and is installed via requirements-ml.txt.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent};

/// The release binary is a GUI-subsystem app (`windows_subsystem = "windows"`),
/// so spawned children would otherwise pop a fresh visible console window.
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

const BACKEND_URL: &str = "http://127.0.0.1:8077";
const BACKEND_ADDR: &str = "127.0.0.1:8077";

/// When packaged as an AppImage, the runtime injects LD_LIBRARY_PATH / PYTHONHOME /
/// APPDIR etc. into our environment. Those would be inherited by any spawned Python
/// and break it ("Failed to import encodings", wrong shared libs), so strip them so
/// the backend (and the interpreter probes) run in the user's normal environment.
const HOST_ENV_OVERRIDES: [&str; 9] = ["LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONHOME",
    "PYTHONPATH", "APPDIR", "APPIMAGE", "ARGV0", "GTK_PATH", "GIO_MODULE_DIR"];

/// The spawned uvicorn process, killed when the app exits.
struct BackendProc(Mutex<Option<Child>>);

fn has_backend(dir: &PathBuf) -> bool {
    dir.join("app").join("main.py").exists()
}

/// Find the `backend/` dir: an explicit env var, then (dev builds) the repo
/// checkout, then the copy bundled into the app's resource dir, then a few
/// locations relative to the executable, then the repo path baked in at
/// compile time.
fn resolve_backend_dir(resource_dir: Option<&Path>) -> Option<PathBuf> {
    if let Ok(d) = std::env::var("MISBAH_BACKEND_DIR") {
        let p = PathBuf::from(d);
        if has_backend(&p) {
            return Some(p);
        }
    }
    let mut candidates: Vec<PathBuf> = Vec::new();
    // Dev builds: the live repo checkout must win — tauri-build copies
    // bundle.resources into target/debug/ on every build, so <exe>/backend
    // would otherwise shadow the repo backend with a stale snapshot.
    #[cfg(debug_assertions)]
    candidates.push(PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../../backend")));
    // The copy bundled via `bundle.resources`: the install dir on Windows
    // (== exe dir), /usr/lib/Misbah in the .deb, $APPDIR/usr/lib/Misbah in an
    // AppImage.
    if let Some(res) = resource_dir {
        candidates.push(res.join("backend"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join("backend"));
            let mut up = dir.to_path_buf();
            for _ in 0..6 {
                if let Some(parent) = up.parent() {
                    up = parent.to_path_buf();
                    candidates.push(up.join("backend"));
                }
            }
        }
    }
    candidates.push(PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../../backend")));
    candidates.into_iter().find(has_backend)
}

/// `true` when `<program> [pre_args] --version` runs and exits successfully.
/// The exit-status check filters out the Windows Store `python.exe` alias stub,
/// whose spawn() "succeeds" but which only opens the Store and exits non-zero.
fn python_ok(program: &str, pre_args: &[&str]) -> bool {
    let mut cmd = Command::new(program);
    cmd.args(pre_args).arg("--version").stdout(Stdio::null()).stderr(Stdio::null());
    for var in HOST_ENV_OVERRIDES {
        cmd.env_remove(var);
    }
    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);
    cmd.status().map(|s| s.success()).unwrap_or(false)
}

/// Pick the Python for the backend: MISBAH_PYTHON wins unprobed, then `python`,
/// then `python3` (Linux/macOS) or the `py -3` launcher (Windows — installed by
/// python.org even when "Add python.exe to PATH" was left unchecked).
fn resolve_python() -> (String, Vec<&'static str>) {
    if let Ok(p) = std::env::var("MISBAH_PYTHON") {
        return (p, vec![]);
    }
    if python_ok("python", &[]) {
        return ("python".into(), vec![]);
    }
    #[cfg(not(windows))]
    if python_ok("python3", &[]) {
        return ("python3".into(), vec![]);
    }
    #[cfg(windows)]
    if python_ok("py", &["-3"]) {
        return ("py".into(), vec!["-3"]);
    }
    ("python".into(), vec![]) // let the spawn fail into the splash error path
}

fn spawn_backend(resource_dir: Option<&Path>, data_root: Option<&Path>) -> Option<Child> {
    let dir = resolve_backend_dir(resource_dir)?;
    let (python, pre_args) = resolve_python();
    let mut cmd = Command::new(python);
    cmd.args(pre_args)
        .args(["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8077"])
        .current_dir(&dir);
    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);
    // Bundled install → keep the SQLite DB / HF cache / models out of the install
    // dir: Program Files isn't user-writable, the AppImage is read-only, and an
    // uninstall or update must never touch trained adapters. Dev runs resolve the
    // repo backend (outside the resource dir), so their data stays in backend/data.
    let bundled = resource_dir.is_some_and(|r| dir.starts_with(r));
    if bundled && std::env::var_os("MISBAH_DATA_DIR").is_none() {
        if let Some(root) = data_root {
            cmd.env("MISBAH_DATA_DIR", root.join("data"));
        }
    }
    for var in HOST_ENV_OVERRIDES {
        cmd.env_remove(var);
    }
    cmd.spawn().ok()
}

fn backend_up() -> bool {
    TcpStream::connect(BACKEND_ADDR).is_ok()
}

fn wait_for_backend(timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if backend_up() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(400));
    }
    false
}

/// Swap the splash to its error message (no backend reachable).
fn show_error(win: &tauri::WebviewWindow) {
    let _ = win.eval(
        "var s=document.getElementById('spin'); if(s)s.style.display='none';\
         var t=document.getElementById('status'); if(t)t.style.display='none';\
         var e=document.getElementById('err'); if(e)e.style.display='block';",
    );
}

fn main() {
    // WebKitGTK renders a blank white page on some Linux GPU/driver combos (notably
    // NVIDIA + Wayland) unless the DMABUF renderer is disabled. Set it before the
    // webview initializes; an explicit value from the environment still wins.
    #[cfg(target_os = "linux")]
    if std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }

    let app = tauri::Builder::default()
        .manage(BackendProc(Mutex::new(None)))
        .setup(|app| {
            // Reuse a backend that's already running (e.g. started from a terminal);
            // otherwise spawn one from the local Python env.
            let resource_dir = app.path().resource_dir().ok();
            let data_root = app.path().app_local_data_dir().ok();
            let child = if backend_up() {
                None
            } else {
                spawn_backend(resource_dir.as_deref(), data_root.as_deref())
            };
            if !backend_up() && child.is_none() {
                if let Some(win) = app.get_webview_window("main") {
                    show_error(&win);
                }
            }
            *app.state::<BackendProc>().0.lock().unwrap() = child;

            // Poll for readiness off the UI thread, then load the studio.
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                if wait_for_backend(Duration::from_secs(90)) {
                    if let Some(win) = handle.get_webview_window("main") {
                        if let Ok(url) = BACKEND_URL.parse() {
                            let _ = win.navigate(url);
                        }
                    }
                } else if let Some(win) = handle.get_webview_window("main") {
                    show_error(&win);
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the Misbah desktop shell");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            if let Some(mut child) = app_handle.state::<BackendProc>().0.lock().unwrap().take() {
                let _ = child.kill();
            }
        }
    });
}
