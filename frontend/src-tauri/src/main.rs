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
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent};

const BACKEND_URL: &str = "http://127.0.0.1:8077";
const BACKEND_ADDR: &str = "127.0.0.1:8077";

/// The spawned uvicorn process, killed when the app exits.
struct BackendProc(Mutex<Option<Child>>);

fn has_backend(dir: &PathBuf) -> bool {
    dir.join("app").join("main.py").exists()
}

/// Find the `backend/` dir: an explicit env var, then a few locations relative to
/// the executable, then (dev convenience) the repo path baked in at compile time.
fn resolve_backend_dir() -> Option<PathBuf> {
    if let Ok(d) = std::env::var("MISBAH_BACKEND_DIR") {
        let p = PathBuf::from(d);
        if has_backend(&p) {
            return Some(p);
        }
    }
    let mut candidates: Vec<PathBuf> = Vec::new();
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

fn spawn_backend() -> Option<Child> {
    let dir = resolve_backend_dir()?;
    let python = std::env::var("MISBAH_PYTHON").unwrap_or_else(|_| "python".into());
    Command::new(python)
        .args(["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8077"])
        .current_dir(dir)
        .spawn()
        .ok()
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
    let app = tauri::Builder::default()
        .manage(BackendProc(Mutex::new(None)))
        .setup(|app| {
            // Reuse a backend that's already running (e.g. started from a terminal);
            // otherwise spawn one from the local Python env.
            let child = if backend_up() { None } else { spawn_backend() };
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
