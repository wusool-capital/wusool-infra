// Shared builder for Scribe's small always-on-top overlays (meeting-detected
// popup, recording pill) so they behave identically.

use log::{info, warn};
use tauri::{AppHandle, Manager, Runtime};

pub(crate) struct OverlaySpec {
    pub label: &'static str,
    pub url: &'static str,
    pub width: f64,
    pub height: f64,
    pub corner_radius: f64,
}

const MARGIN: f64 = 12.0;

/// Shows the overlay in the top-right corner; no-op if it already exists.
pub(crate) fn show_overlay<R: Runtime>(app: &AppHandle<R>, spec: &'static OverlaySpec) {
    if app.get_webview_window(spec.label).is_some() {
        return;
    }

    // Window creation and window-vibrancy both require the main thread on
    // macOS (apply_vibrancy panics/errors otherwise) -- callers fire from
    // background tasks, so dispatch it explicitly.
    let app_clone = app.clone();
    let _ = app.run_on_main_thread(move || {
        if app_clone.get_webview_window(spec.label).is_some() {
            return;
        }

        let window = match tauri::WebviewWindowBuilder::new(
            &app_clone,
            spec.label,
            tauri::WebviewUrl::App(spec.url.into()),
        )
        .title("")
        .inner_size(spec.width, spec.height)
        .resizable(false)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .transparent(true)
        .focused(false)
        // The window never takes focus, so without this macOS spends the first
        // click activating it and swallows the button press.
        .accept_first_mouse(true)
        // Keep overlays out of screen shares and visible on every Space.
        .content_protected(true)
        .visible_on_all_workspaces(true)
        .build()
        {
            Ok(window) => window,
            Err(err) => {
                warn!("[Overlay] failed to create {}: {err:?}", spec.label);
                return;
            }
        };

        if let Ok(Some(monitor)) = window.current_monitor() {
            let scale = monitor.scale_factor();
            let screen = monitor.size().to_logical::<f64>(scale);
            let x = (screen.width - spec.width - MARGIN).max(0.0);
            let _ = window.set_position(tauri::Position::Logical(tauri::LogicalPosition::new(
                x, MARGIN,
            )));
        }

        #[cfg(target_os = "macos")]
        {
            use window_vibrancy::{apply_vibrancy, NSVisualEffectMaterial};
            // HudWindow is the same dark, translucent, blurred material macOS
            // uses for its own notification banners.
            if let Err(err) = apply_vibrancy(
                &window,
                NSVisualEffectMaterial::HudWindow,
                None,
                Some(spec.corner_radius),
            ) {
                warn!("[Overlay] failed to apply vibrancy to {}: {err:?}", spec.label);
            }
        }

        let _ = window.show();
        info!("[Overlay] showing {}", spec.label);
    });
}

pub(crate) fn close_overlay<R: Runtime>(app: &AppHandle<R>, label: &'static str) {
    if app.get_webview_window(label).is_none() {
        return;
    }

    let app_clone = app.clone();
    let _ = app.run_on_main_thread(move || {
        if let Some(window) = app_clone.get_webview_window(label) {
            let _ = window.close();
            info!("[Overlay] closed {label}");
        }
    });
}
