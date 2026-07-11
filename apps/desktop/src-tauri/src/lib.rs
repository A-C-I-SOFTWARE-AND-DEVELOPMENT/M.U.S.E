//! muse desktop shell (Tauri v2).
//!
//! This is a thin native shell around the bundled Singularity UI (../ui/dist).
//! It does **not** bundle the Python backend — the web UI talks to a
//! locally-running muse gateway over HTTP (default http://127.0.0.1:8765,
//! configurable in-app and via the `MUSE_GATEWAY_URL` build/runtime env). The
//! shell's jobs are: load the UI, provide a native window + menu + system
//! tray, enforce a single running instance, and (the one-installable story)
//! keep the gateway alive — if `/v1/health` is down and autostart is enabled,
//! it spawns an installed `muse cockpit serve` as a managed child (src/brain.rs)
//! and kills it only on real exit, never on hide-to-tray.

mod brain;

use std::sync::Mutex;

use tauri::{
    menu::{AboutMetadata, Menu, MenuItem, PredefinedMenuItem, Submenu},
    tray::{TrayIconBuilder, TrayIconEvent},
    Manager, RunEvent, WindowEvent,
};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_window_state::{AppHandleExt, StateFlags};

/// A simple HTTP proxy command for the webview — does an authenticated
/// request to the gateway from Rust (bypassing WebView2's cross-origin
/// fetch restriction) and returns {status, body} to the JS caller.
/// Used by gateway.ts when running inside Tauri.
#[derive(serde::Serialize)]
struct ProxyResponse {
    ok: bool,
    status: u16,
    body: String,
}

#[tauri::command]
async fn gateway_proxy(
    state: tauri::State<'_, UiGatewayHint>,
    method: String,
    path: String,
    body: Option<String>,
    auth_token: Option<String>,
) -> Result<ProxyResponse, String> {
    let base = {
        let guard = state.0.lock();
        guard
            .ok()
            .and_then(|s| s.clone())
            .unwrap_or_else(gateway_url)
    };
    let url = format!("{}{}", base, path);

    // Use a minimal blocking HTTP client (std::net::TcpStream) to avoid
    // pulling reqwest/hyper into the desktop shell.
    let result = tauri::async_runtime::spawn_blocking(move || {
        proxy_http_request(&url, &method, body.as_deref(), auth_token.as_deref())
    })
    .await
    .map_err(|e| e.to_string())?;

    Ok(result)
}

/// Minimal HTTP client over TcpStream — just enough for the gateway API.
fn proxy_http_request(
    url: &str,
    method: &str,
    body: Option<&str>,
    auth_token: Option<&str>,
) -> ProxyResponse {
    let (host, port, path) = parse_url(url).unwrap_or(("127.0.0.1", 8765, "/"));
    let addr = format!("{}:{}", host, port);

    use std::io::{Read, Write};
    use std::net::TcpStream;
    use std::time::Duration;

    let Ok(mut addrs) = addr.to_socket_addrs() else {
        return ProxyResponse { ok: false, status: 0, body: "DNS resolution failed".into() };
    };
    let Some(socket_addr) = addrs.next() else {
        return ProxyResponse { ok: false, status: 0, body: "No address found".into() };
    };

    let Ok(mut stream) = TcpStream::connect_timeout(&socket_addr, Duration::from_secs(3)) else {
        return ProxyResponse { ok: false, status: 0, body: "Connection refused".into() };
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(30)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(10)));

    let body_bytes = body.unwrap_or("").as_bytes();
    let mut req = format!(
        "{} {} HTTP/1.1\r\nHost: {}:{}\r\nConnection: close\r\nContent-Type: application/json\r\nContent-Length: {}\r\n",
        method, path, host, port, body_bytes.len()
    );
    if let Some(token) = auth_token {
        if !token.is_empty() {
            req.push_str(&format!("Authorization: Bearer {}\r\n", token));
        }
    }
    req.push_str("\r\n");

    if stream.write_all(req.as_bytes()).is_err() {
        return ProxyResponse { ok: false, status: 0, body: "Write failed".into() };
    }
    if !body_bytes.is_empty() {
        if stream.write_all(body_bytes).is_err() {
            return ProxyResponse { ok: false, status: 0, body: "Body write failed".into() };
        }
    }

    let mut response = Vec::new();
    let _ = stream.read_to_end(&mut response);
    let response_str = String::from_utf8_lossy(&response).to_string();

    // Parse status line and split headers from body
    let (status, body_text) = parse_http_response(&response_str);
    ProxyResponse {
        ok: status >= 200 && status < 300,
        status,
        body: body_text,
    }
}

fn parse_url(url: &str) -> Option<(&str, u16, &str)> {
    let rest = url.strip_prefix("http://").or_else(|| url.strip_prefix("https://"))?;
    let (authority, path) = rest.split_once('/').unwrap_or((rest, ""));
    let (host, port) = match authority.rsplit_once(':') {
        Some((h, p)) => (h, p.parse().ok()?),
        None => (authority, 80),
    };
    let path = if path.is_empty() { "/" } else { path };
    // Re-borrow with lifetime — we need the path from the original string
    let path_start = rest.len() - path.len();
    Some((host, port, &rest[path_start..]))
}

fn parse_http_response(response: &str) -> (u16, String) {
    // Find the first \r\n\r\n to split headers from body
    let header_end = response.find("\r\n\r\n").or_else(|| response.find("\n\n"));
    let (headers, body) = match header_end {
        Some(idx) => {
            let sep_len = if response[idx..].starts_with("\r\n\r\n") { 4 } else { 2 };
            (&response[..idx], &response[idx + sep_len..])
        }
        None => (response, ""),
    };

    // Parse status from first line: "HTTP/1.1 200 OK"
    let status = headers
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|s| s.parse::<u16>().ok())
        .unwrap_or(0);

    (status, body.to_string())
}

use std::net::ToSocketAddrs;

/// Default gateway base URL. Mirrors the UI's `DEFAULT_GATEWAY_BASE`. The UI is
/// the source of truth at runtime (it stores an override in localStorage); this
/// constant only feeds the menu's informational item and any future native
/// deep-link handling.
const DEFAULT_GATEWAY_URL: &str = "http://127.0.0.1:8765";

/// Resolve the configured gateway URL for display. Honors `MUSE_GATEWAY_URL`.
pub(crate) fn gateway_url() -> String {
    std::env::var("MUSE_GATEWAY_URL").unwrap_or_else(|_| DEFAULT_GATEWAY_URL.to_string())
}

/// The gateway base the UI is *actually* using. The Settings override lives in
/// the webview's localStorage where Rust cannot see it, so the UI reports it
/// here (`gateway_url_hint_set`, on load and on every change) and native
/// surfaces — Help → Copy Gateway URL — stay truthful instead of advertising
/// the env/default value.
#[derive(Default)]
pub(crate) struct UiGatewayHint(Mutex<Option<String>>);

#[tauri::command]
fn gateway_url_hint_set(state: tauri::State<UiGatewayHint>, url: String) {
    let trimmed = url.trim();
    // Bound + sanity-check the hint — it feeds the clipboard, nothing else.
    let value = (!trimmed.is_empty()
        && trimmed.len() <= 2048
        && (trimmed.starts_with("http://") || trimmed.starts_with("https://")))
    .then(|| trimmed.trim_end_matches('/').to_string());
    if let Ok(mut slot) = state.0.lock() {
        *slot = value;
    }
}

/// The gateway base the shell should treat as authoritative: the UI-reported
/// hint when present, else the env/default. Feeds the Copy Gateway URL menu
/// action AND the brain health probe (brain.rs), so a Settings override is
/// what the shell actually probes/spawns against.
pub(crate) fn effective_gateway_url(app: &tauri::AppHandle) -> String {
    app.state::<UiGatewayHint>()
        .0
        .lock()
        .ok()
        .and_then(|slot| slot.clone())
        .unwrap_or_else(gateway_url)
}

/// Show and focus the main window (used by the tray and second-instance hook).
fn focus_main(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.show();
        let _ = win.unminimize();
        let _ = win.set_focus();
    }
}

/// Build the application menu: an app/file submenu (About + Quit), a standard
/// Edit submenu (so copy/paste/select-all work in the webview), and a Help
/// submenu with a "Copy Gateway URL" action.
fn build_menu(app: &tauri::AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let about = PredefinedMenuItem::about(
        app,
        Some("About muse"),
        Some(AboutMetadata {
            name: Some("muse".into()),
            version: Some(app.package_info().version.to_string()),
            comments: Some("Multi-Use Synaptic Entity — One mind, many pathways.".into()),
            ..Default::default()
        }),
    )?;
    let quit = PredefinedMenuItem::quit(app, Some("Quit muse"))?;
    let app_menu = Submenu::with_items(
        app,
        "muse",
        true,
        &[&about, &PredefinedMenuItem::separator(app)?, &quit],
    )?;

    let edit_menu = Submenu::with_items(
        app,
        "Edit",
        true,
        &[
            &PredefinedMenuItem::undo(app, None)?,
            &PredefinedMenuItem::redo(app, None)?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::cut(app, None)?,
            &PredefinedMenuItem::copy(app, None)?,
            &PredefinedMenuItem::paste(app, None)?,
            &PredefinedMenuItem::select_all(app, None)?,
        ],
    )?;

    // An actionable item that copies the *effective* gateway URL to the
    // clipboard (handled in the builder's `on_menu_event`). The label carries
    // no URL on purpose: the UI's Settings override can change at runtime and
    // a static label would go stale / disagree with what gets copied.
    let gateway_item = MenuItem::with_id(
        app,
        "copy-gateway-url",
        "Copy Gateway URL",
        true,
        None::<&str>,
    )?;
    let help_menu = Submenu::with_items(app, "Help", true, &[&gateway_item])?;

    Menu::with_items(app, &[&app_menu, &edit_menu, &help_menu])
}

/// Build the system tray icon with a Show / Hide / Quit menu.
fn build_tray(app: &tauri::AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "tray-show", "Show muse", true, None::<&str>)?;
    let hide = MenuItem::with_id(app, "tray-hide", "Hide", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "tray-quit", "Quit", true, None::<&str>)?;
    let tray_menu = Menu::with_items(app, &[&show, &hide, &PredefinedMenuItem::separator(app)?, &quit])?;

    TrayIconBuilder::with_id("muse-tray")
        .icon(app.default_window_icon().cloned().expect("default window icon"))
        .tooltip("muse")
        .menu(&tray_menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "tray-show" => focus_main(app),
            "tray-hide" => {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.hide();
                }
            }
            "tray-quit" => {
                // Persist window geometry before the explicit exit — with the
                // hide-to-tray model this is the canonical shutdown path.
                let _ = app.save_window_state(StateFlags::all());
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            // Left-click the tray icon → bring the window forward.
            if let TrayIconEvent::Click { .. } = event {
                focus_main(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}

/// The shared entry point. `main.rs` (desktop) and the mobile entry points all
/// call this so the setup lives in one place.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let context = tauri::generate_context!();

    #[allow(unused_mut)]
    let mut builder = tauri::Builder::default()
        // Enforce a single instance: a second launch focuses the existing
        // window instead of opening another.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            focus_main(app);
        }))
        // Shell plugin: used Rust-side only (brain.rs spawns the gateway); no
        // shell:* capability is granted to the webview (capabilities/default.json).
        .plugin(tauri_plugin_shell::init())
        // Persist window size/position across restarts. With the hide-to-tray
        // close model the window is rarely destroyed, so the explicit save on
        // tray Quit (below) is the main persistence point.
        .plugin(tauri_plugin_window_state::Builder::default().build())
        // Native clipboard access for the "Copy Gateway URL" menu item.
        .plugin(tauri_plugin_clipboard_manager::init())
        .manage(brain::BrainState::default())
        .manage(UiGatewayHint::default())
        .invoke_handler(tauri::generate_handler![
            brain::gateway_status,
            brain::gateway_start,
            brain::gateway_stop,
            brain::autostart_get,
            brain::autostart_set,
            gateway_url_hint_set,
            gateway_proxy,
        ])
        // Application menu actions (menu items declared in `build_menu`).
        // Clipboard write happens HERE, Rust-side — the webview holds no
        // clipboard capability (capabilities/default.json).
        .on_menu_event(|app, event| {
            if event.id().as_ref() == "copy-gateway-url" {
                let _ = app.clipboard().write_text(effective_gateway_url(app));
            }
        })
        // Native updates must never be shadowed by an old PWA service worker.
        // This hook runs even when a legacy cached JavaScript bundle controls
        // the first page load, unregisters it from Rust, clears CacheStorage,
        // and reloads once into the assets bundled with this executable.
        .on_page_load(|webview, _payload| {
            let _ = webview.eval(
                r#"(async()=>{
                    if(!('serviceWorker' in navigator)) return;
                    const regs=await navigator.serviceWorker.getRegistrations();
                    if(!regs.length) return;
                    await Promise.all(regs.map(r=>r.unregister()));
                    if('caches' in window){
                      const keys=await caches.keys();
                      await Promise.all(keys.map(k=>caches.delete(k)));
                    }
                    location.reload();
                })().catch(()=>{});"#,
            );
        })
        .setup(|app| {
            // Clone the handle so the menu/tray builders own an `AppHandle`
            // independent of the `&mut App` borrow that `set_menu` needs.
            let handle = app.handle().clone();
            let menu = build_menu(&handle)?;
            app.set_menu(menu)?;
            build_tray(&handle)?;
            // One-installable: if the gateway is down and autostart is enabled,
            // spawn `muse cockpit serve` as a managed child (best-effort).
            brain::autostart_on_boot(handle);
            Ok(())
        })
        // Hide-to-tray on window close rather than quitting outright; the tray
        // Quit item is the explicit exit. (Keeps the local agent companion app
        // available without re-launching.)
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        });

    // Auto-update scaffold: register tauri-plugin-updater ONLY when a pubkey is
    // actually configured (plugins.updater.pubkey in tauri.conf.json). With the
    // placeholder empty pubkey the plugin is never initialized, so the app can
    // never error on the unsigned/inert configuration. Provisioning the keypair
    // is owner-gated — see RELEASE.md.
    #[cfg(desktop)]
    {
        let updater_configured = context
            .config()
            .plugins
            .0
            .get("updater")
            .and_then(|cfg| cfg.get("pubkey"))
            .and_then(|v| v.as_str())
            .is_some_and(|s| !s.trim().is_empty());
        if updater_configured {
            builder = builder.plugin(tauri_plugin_updater::Builder::new().build());
        }
    }

    builder
        .build(context)
        .expect("error while building muse desktop")
        .run(|app, event| {
            // Real exit (tray Quit / app menu Quit) — window close only hides.
            // This is the one place the managed gateway child is reaped.
            if let RunEvent::Exit = event {
                brain::shutdown(app);
            }
        });
}
