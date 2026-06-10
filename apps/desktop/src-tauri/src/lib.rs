//! M.U.S.E. desktop shell (Tauri v2).
//!
//! This is a thin native shell around the bundled Singularity UI (../ui/dist).
//! It does **not** bundle the Python backend — the web UI talks to a
//! locally-running MUSE gateway over HTTP (default http://127.0.0.1:8765,
//! configurable in-app and via the `MUSE_GATEWAY_URL` build/runtime env). The
//! shell's jobs are: load the UI, provide a native window + menu + system
//! tray, enforce a single running instance, and (the one-installable story)
//! keep the gateway alive — if `/v1/health` is down and autostart is enabled,
//! it spawns an installed `muse cockpit serve` as a managed child (src/brain.rs)
//! and kills it only on real exit, never on hide-to-tray.

mod brain;

use tauri::{
    menu::{AboutMetadata, Menu, MenuItem, PredefinedMenuItem, Submenu},
    tray::{TrayIconBuilder, TrayIconEvent},
    Manager, RunEvent, WindowEvent,
};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_window_state::{AppHandleExt, StateFlags};

/// Default gateway base URL. Mirrors the UI's `DEFAULT_GATEWAY_BASE`. The UI is
/// the source of truth at runtime (it stores an override in localStorage); this
/// constant only feeds the menu's informational item and any future native
/// deep-link handling.
const DEFAULT_GATEWAY_URL: &str = "http://127.0.0.1:8765";

/// Resolve the configured gateway URL for display. Honors `MUSE_GATEWAY_URL`.
pub(crate) fn gateway_url() -> String {
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

/// Build the application menu: an app/file submenu (About + Quit), a standard
/// Edit submenu (so copy/paste/select-all work in the webview), and a Help
/// submenu with a "Copy Gateway URL" action.
fn build_menu(app: &tauri::AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let about = PredefinedMenuItem::about(
        app,
        Some("About M.U.S.E."),
        Some(AboutMetadata {
            name: Some("M.U.S.E.".into()),
            version: Some(app.package_info().version.to_string()),
            comments: Some("Multi-Use Synaptic Entity — One mind, many pathways.".into()),
            ..Default::default()
        }),
    )?;
    let quit = PredefinedMenuItem::quit(app, Some("Quit M.U.S.E."))?;
    let app_menu = Submenu::with_items(
        app,
        "M.U.S.E.",
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

    // An actionable item that copies the configured gateway URL to the
    // clipboard (handled in the builder's `on_menu_event`). `with_id` gives it
    // a stable id the handler matches on.
    let gateway_item = MenuItem::with_id(
        app,
        "copy-gateway-url",
        format!("Copy Gateway URL ({})", gateway_url()),
        true,
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
        .invoke_handler(tauri::generate_handler![
            brain::gateway_status,
            brain::gateway_start,
            brain::gateway_stop,
            brain::autostart_get,
            brain::autostart_set,
        ])
        // Application menu actions (menu items declared in `build_menu`).
        .on_menu_event(|app, event| {
            if event.id().as_ref() == "copy-gateway-url" {
                let _ = app.clipboard().write_text(gateway_url());
            }
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
        .expect("error while building M.U.S.E. desktop")
        .run(|app, event| {
            // Real exit (tray Quit / app menu Quit) — window close only hides.
            // This is the one place the managed gateway child is reaped.
            if let RunEvent::Exit = event {
                brain::shutdown(app);
            }
        });
}
