//! M.U.S.E. desktop shell (Tauri v2).
//!
//! This is a thin native shell around the bundled Singularity UI (../ui/dist).
//! It does **not** bundle or spawn the Python backend — the web UI talks to a
//! locally-running MUSE gateway over HTTP (default http://127.0.0.1:8765,
//! configurable in-app and via the `MUSE_GATEWAY_URL` build/runtime env). The
//! shell's only jobs are: load the UI, provide a native window + menu + system
//! tray, and enforce a single running instance.

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    tray::{TrayIconBuilder, TrayIconEvent},
    Manager, WindowEvent,
};

/// Default gateway base URL. Mirrors the UI's `DEFAULT_GATEWAY_BASE`. The UI is
/// the source of truth at runtime (it stores an override in localStorage); this
/// constant only feeds the menu's informational item and any future native
/// deep-link handling.
const DEFAULT_GATEWAY_URL: &str = "http://127.0.0.1:8765";

/// Resolve the configured gateway URL for display. Honors `MUSE_GATEWAY_URL`.
fn gateway_url() -> String {
    std::env::var("MUSE_GATEWAY_URL").unwrap_or_else(|_| DEFAULT_GATEWAY_URL.to_string())
}

/// Show and focus the main window (used by the tray and second-instance hook).
fn focus_main(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.show();
        let _ = win.unminimize();
        let _ = win.set_focus();
    }
}

/// Build the application menu: an app/file submenu (Quit), a standard Edit
/// submenu (so copy/paste/select-all work in the webview), and a Help submenu
/// that surfaces the configured gateway URL.
fn build_menu(app: &tauri::AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let quit = PredefinedMenuItem::quit(app, Some("Quit M.U.S.E."))?;
    let app_menu = Submenu::with_items(app, "M.U.S.E.", true, &[&quit])?;

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

    // A disabled, informational item showing where the UI will look for the
    // gateway. `with_id` gives it a stable id; it's non-interactive.
    let gateway_item = MenuItem::with_id(
        app,
        "gateway-url",
        format!("Gateway: {}", gateway_url()),
        false,
        None::<&str>,
    )?;
    let help_menu = Submenu::with_items(app, "Help", true, &[&gateway_item])?;

    Menu::with_items(app, &[&app_menu, &edit_menu, &help_menu])
}

/// Build the system tray icon with a Show / Hide / Quit menu.
fn build_tray(app: &tauri::AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "tray-show", "Show M.U.S.E.", true, None::<&str>)?;
    let hide = MenuItem::with_id(app, "tray-hide", "Hide", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "tray-quit", "Quit", true, None::<&str>)?;
    let tray_menu = Menu::with_items(app, &[&show, &hide, &PredefinedMenuItem::separator(app)?, &quit])?;

    TrayIconBuilder::with_id("muse-tray")
        .icon(app.default_window_icon().cloned().expect("default window icon"))
        .tooltip("M.U.S.E.")
        .menu(&tray_menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "tray-show" => focus_main(app),
            "tray-hide" => {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.hide();
                }
            }
            "tray-quit" => app.exit(0),
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
    tauri::Builder::default()
        // Enforce a single instance: a second launch focuses the existing
        // window instead of opening another.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            focus_main(app);
        }))
        .setup(|app| {
            // Clone the handle so the menu/tray builders own an `AppHandle`
            // independent of the `&mut App` borrow that `set_menu` needs.
            let handle = app.handle().clone();
            let menu = build_menu(&handle)?;
            app.set_menu(menu)?;
            build_tray(&handle)?;
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
        })
        .run(tauri::generate_context!())
        .expect("error while running M.U.S.E. desktop");
}
