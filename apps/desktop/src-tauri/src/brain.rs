//! Brain (gateway process) management.
//!
//! "The brain" is the locally-running muse gateway (`muse cockpit serve`,
//! default http://127.0.0.1:8765). This module makes the desktop app a true
//! one-installable: on launch it probes the gateway's `/v1/health`, and — if
//! the gateway is down AND autostart is enabled in a small persisted config —
//! locates a `muse` binary (PATH plus common install locations) and spawns
//! `muse cockpit serve` as a managed child via tauri-plugin-shell.
//!
//! Ground rules:
//!   - Never spawn over a running gateway (probe first, every time) and never
//!     spawn twice (the managed child handle is tracked in `BrainState`).
//!   - `gateway_stop` / app exit only ever kill the child *we* spawned; an
//!     externally-started gateway is never touched.
//!   - Hide-to-tray is NOT an exit: the child is killed only on real app exit
//!     (`RunEvent::Exit` in lib.rs), so the brain keeps serving while the
//!     window is hidden.
//!   - The health probe is a dependency-free blocking HTTP GET over
//!     `std::net::TcpStream` (loopback only, sub-second timeouts) so we don't
//!     pull a full HTTP client into the shell.

use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Tracked handle to the gateway child *this app* spawned (None when the
/// gateway is external or not running). Managed via `app.manage()`.
#[derive(Default)]
pub struct BrainState {
    child: Mutex<Option<CommandChild>>,
}

/// What the UI's "Brain (gateway)" card and the Observatory fallback render.
#[derive(Serialize, Clone)]
pub struct BrainStatus {
    /// GET /v1/health answered OK right now.
    pub reachable: bool,
    /// This app spawned (and still tracks) the gateway process.
    pub managed: bool,
    /// Detected `muse` binary path, if any.
    pub binary: Option<String>,
    /// Persisted autostart preference.
    pub autostart: bool,
    /// The gateway base URL the shell probes.
    pub base: String,
}

// ---- persisted config -------------------------------------------------------

/// Small persisted app config (app_config_dir/brain.json). Autostart defaults
/// to ON — the one-installable story is "install the app, the brain follows" —
/// and the Settings toggle turns it off.
#[derive(Serialize, Deserialize, Clone, Copy)]
pub struct BrainConfig {
    pub autostart: bool,
}

impl Default for BrainConfig {
    fn default() -> Self {
        Self { autostart: true }
    }
}

fn config_path(app: &AppHandle) -> Option<PathBuf> {
    app.path().app_config_dir().ok().map(|d| d.join("brain.json"))
}

fn load_config(app: &AppHandle) -> BrainConfig {
    config_path(app)
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

fn save_config(app: &AppHandle, cfg: &BrainConfig) {
    let Some(path) = config_path(app) else { return };
    if let Some(dir) = path.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    if let Ok(json) = serde_json::to_string_pretty(cfg) {
        let _ = std::fs::write(path, json);
    }
}

// ---- health probe (dependency-free loopback HTTP GET) -----------------------

/// Split "http://host:port[/...]" into (host, port). Only http is expected —
/// the gateway is loopback — but a https scheme still parses (port 443).
fn host_port(base: &str) -> Option<(String, u16)> {
    let (default_port, rest) = if let Some(r) = base.strip_prefix("http://") {
        (80u16, r)
    } else if let Some(r) = base.strip_prefix("https://") {
        (443u16, r)
    } else {
        (80u16, base)
    };
    let authority = rest.split('/').next()?;
    if authority.is_empty() {
        return None;
    }
    match authority.rsplit_once(':') {
        Some((host, port)) => Some((host.to_string(), port.parse().ok()?)),
        None => Some((authority.to_string(), default_port)),
    }
}

/// Blocking GET /v1/health against `base`; true iff an HTTP 200 comes back.
/// Sub-second timeouts keep startup snappy when the gateway is down.
fn probe_health_blocking(base: &str) -> bool {
    let Some((host, port)) = host_port(base) else {
        return false;
    };
    let Ok(mut addrs) = (host.as_str(), port).to_socket_addrs() else {
        return false;
    };
    let Some(addr) = addrs.next() else {
        return false;
    };
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(800)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(800)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(800)));
    let req = format!(
        "GET /v1/health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 64];
    let Ok(n) = stream.read(&mut buf) else {
        return false;
    };
    // Status line: "HTTP/1.1 200 OK". Checking the head of the response is
    // enough; we never need the body.
    String::from_utf8_lossy(&buf[..n]).starts_with("HTTP/1.1 200")
        || String::from_utf8_lossy(&buf[..n]).starts_with("HTTP/1.0 200")
}

async fn probe_health(base: String) -> bool {
    tauri::async_runtime::spawn_blocking(move || probe_health_blocking(&base))
        .await
        .unwrap_or(false)
}

// ---- binary discovery --------------------------------------------------------

#[cfg(windows)]
const BINARY_NAMES: &[&str] = &[
    "muse.exe", "muse.cmd", "muse.bat", "hermes.exe", "hermes.cmd", "hermes.bat",
];
// `muse` is canonical; `hermes` is the pre-rename alias of the same entry point.
#[cfg(not(windows))]
const BINARY_NAMES: &[&str] = &["muse", "hermes"];

#[cfg(unix)]
fn is_executable(p: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    p.is_file()
        && p.metadata()
            .map(|m| m.permissions().mode() & 0o111 != 0)
            .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_executable(p: &Path) -> bool {
    p.is_file()
}

/// Directories to search: every PATH entry first (≈ `which muse`), then the
/// common install locations a GUI-launched app may not have on PATH (macOS
/// Finder/Dock launches get a minimal PATH, so pipx/homebrew dirs matter).
fn search_dirs(app: &AppHandle) -> Vec<PathBuf> {
    let mut dirs: Vec<PathBuf> = std::env::var_os("PATH")
        .map(|p| std::env::split_paths(&p).collect())
        .unwrap_or_default();
    if let Ok(home) = app.path().home_dir() {
        dirs.push(home.join(".local").join("bin")); // pipx / uv tool default
        dirs.push(home.join(".cargo").join("bin"));
    }
    dirs.push(PathBuf::from("/usr/local/bin"));
    dirs.push(PathBuf::from("/opt/homebrew/bin"));
    #[cfg(windows)]
    if let Some(local) = std::env::var_os("LOCALAPPDATA") {
        let local = PathBuf::from(local);
        dirs.push(local.join("Programs").join("muse"));
        dirs.push(local.join("Programs").join("Python").join("Scripts"));
    }
    dirs
}

/// Locate a runnable `muse` (or `hermes`) binary, or None.
pub fn find_muse_binary(app: &AppHandle) -> Option<PathBuf> {
    for dir in search_dirs(app) {
        for name in BINARY_NAMES {
            let candidate = dir.join(name);
            if is_executable(&candidate) {
                return Some(candidate);
            }
        }
    }
    None
}

// ---- start / stop ------------------------------------------------------------

async fn status_for(app: &AppHandle) -> BrainStatus {
    // Hint-aware: honors the UI's Settings override, not just env/default.
    let base = crate::effective_gateway_url(app);
    let reachable = probe_health(base.clone()).await;
    let managed = app
        .state::<BrainState>()
        .child
        .lock()
        .map(|g| g.is_some())
        .unwrap_or(false);
    BrainStatus {
        reachable,
        managed,
        binary: find_muse_binary(app).map(|p| p.display().to_string()),
        autostart: load_config(app).autostart,
        base,
    }
}

/// Spawn `muse cockpit serve` if (and only if) the gateway is unreachable and
/// we haven't already spawned one. Idempotent by construction: probe first,
/// then check the tracked child handle, only then spawn.
async fn start_if_needed(app: &AppHandle) -> Result<(), String> {
    // Hint-aware: honors the UI's Settings override, not just env/default.
    let base = crate::effective_gateway_url(app);
    if probe_health(base).await {
        return Ok(()); // already running (ours or external) — never double-serve
    }
    {
        let state = app.state::<BrainState>();
        let guard = state.child.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            // We already spawned a child that is presumably still booting;
            // spawning a second would race it for the port.
            return Ok(());
        }
    }
    let bin = find_muse_binary(app).ok_or_else(|| {
        "muse binary not found on PATH or in common install locations — \
         install the muse CLI first (see Settings → Brain)"
            .to_string()
    })?;
    let (mut rx, child) = app
        .shell()
        .command(&bin)
        .args(["cockpit", "serve", "--agent", "full"])
        .spawn()
        .map_err(|e| format!("failed to spawn {}: {e}", bin.display()))?;
    let pid = child.pid();
    {
        let state = app.state::<BrainState>();
        let mut guard = state.child.lock().map_err(|e| e.to_string())?;
        guard.replace(child);
    }
    // Drain the child's event stream; when it terminates on its own, drop the
    // tracked handle (guarded by pid so a newer child is never cleared).
    let app2 = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            if matches!(event, CommandEvent::Terminated(_)) {
                break;
            }
        }
        if let Some(state) = app2.try_state::<BrainState>() {
            if let Ok(mut guard) = state.child.lock() {
                if guard.as_ref().map(|c| c.pid()) == Some(pid) {
                    guard.take();
                }
            }
        }
    });
    Ok(())
}

/// Called once from setup(). Best-effort: a failed autostart is surfaced by
/// the Settings card's status row, not a dialog.
pub fn autostart_on_boot(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        if !load_config(&app).autostart {
            return;
        }
        let _ = start_if_needed(&app).await;
    });
}

/// Kill the managed child, if any. Called on real app exit (RunEvent::Exit) —
/// NOT on hide-to-tray — and by the `gateway_stop` command.
pub fn shutdown(app: &AppHandle) {
    if let Some(state) = app.try_state::<BrainState>() {
        if let Ok(mut guard) = state.child.lock() {
            if let Some(child) = guard.take() {
                let _ = child.kill();
            }
        }
    }
}

// ---- commands (the UI's native surface) ---------------------------------------

#[tauri::command]
pub async fn gateway_status(app: AppHandle) -> BrainStatus {
    status_for(&app).await
}

#[tauri::command]
pub async fn gateway_start(app: AppHandle) -> Result<BrainStatus, String> {
    start_if_needed(&app).await?;
    Ok(status_for(&app).await)
}

#[tauri::command]
pub async fn gateway_stop(app: AppHandle) -> Result<BrainStatus, String> {
    shutdown(&app);
    Ok(status_for(&app).await)
}

#[tauri::command]
pub fn autostart_get(app: AppHandle) -> bool {
    load_config(&app).autostart
}

#[tauri::command]
pub fn autostart_set(app: AppHandle, enabled: bool) -> bool {
    save_config(&app, &BrainConfig { autostart: enabled });
    enabled
}
