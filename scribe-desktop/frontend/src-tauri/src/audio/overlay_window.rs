// Shared builder for Scribe's small always-on-top overlays (meeting-detected
// popup, meeting-ended countdown) so they behave identically.
//
// On macOS they are non-activating NSPanels: like a system notification they
// float over the meeting app without pulling focus, yet still get hover, the
// pointer cursor and first-click handling. A plain unfocused window gets none
// of that because macOS only delivers hover/cursor events to the active window.

use log::{info, warn};
use tauri::{AppHandle, Manager, Runtime};

pub(crate) struct OverlaySpec {
    pub label: &'static str,
    pub url: &'static str,
    pub width: f64,
    pub height: f64,
}

const MARGIN: f64 = 12.0;

#[cfg(target_os = "macos")]
mod panel {
    use super::{OverlaySpec, MARGIN};
    use tauri::{AppHandle, LogicalPosition, LogicalSize, Position, Runtime, Size, WebviewUrl};
    use tauri_nspanel::{
        tauri_panel, CollectionBehavior, ManagerExt, PanelBuilder, PanelLevel, StyleMask,
        TrackingAreaOptions,
    };

    tauri_panel! {
        panel!(OverlayPanel {
            config: {
                can_become_key_window: true,
                can_become_main_window: false,
                is_floating_panel: true
            }
            with: {
                tracking_area: {
                    options: TrackingAreaOptions::new()
                        .active_always()
                        .mouse_entered_and_exited()
                        .mouse_moved()
                        .cursor_update(),
                    auto_resize: true
                }
            }
        })

        panel_event!(OverlayPanelEvents {
            window_did_become_key(notification: &NSNotification) -> ()
        })
    }

    // tauri_panel! types are bound to the real window runtime (Wry).
    pub(super) fn create(app: &AppHandle, spec: &'static OverlaySpec) -> bool {
        let x = app
            .primary_monitor()
            .ok()
            .flatten()
            .map(|m| m.size().to_logical::<f64>(m.scale_factor()).width - spec.width - MARGIN)
            .unwrap_or(MARGIN)
            .max(0.0);

        let built = PanelBuilder::<_, OverlayPanel>::new(app, spec.label)
            .url(WebviewUrl::App(spec.url.into()))
            .size(Size::Logical(LogicalSize::new(spec.width, spec.height)))
            .position(Position::Logical(LogicalPosition::new(x, MARGIN)))
            .level(PanelLevel::Status)
            .has_shadow(false)
            .transparent(true)
            // NSPanels hide whenever their app is inactive, which is always the
            // case while the user is in the meeting app.
            .hides_on_deactivate(false)
            .add_style_mask(StyleMask::empty().nonactivating_panel())
            .collection_behavior(
                CollectionBehavior::new()
                    .can_join_all_spaces()
                    .full_screen_auxiliary(),
            )
            .with_window(|window| {
                window
                    .title("")
                    .resizable(false)
                    .decorations(false)
                    // The webview needs this too, or its white background shows
                    // in the card's rounded corners.
                    .transparent(true)
                    .skip_taskbar(true)
                    .focused(false)
                    .accept_first_mouse(true)
                    // Keep overlays out of screen shares.
                    .content_protected(true)
            })
            .build();

        let panel = match built {
            Ok(panel) => panel,
            Err(err) => {
                log::warn!("[Overlay] panel build failed for {}: {err:?}", spec.label);
                return false;
            }
        };

        // WebKit only tracks hover/cursor in the key window. Becoming key here
        // doesn't activate the app, so it only moves keyboard focus while the
        // pointer is over the overlay.
        let handler = OverlayPanelEvents::new();
        let app_for_hover = app.clone();
        let label = spec.label;
        handler.on_mouse_entered(move |_| {
            if let Ok(panel) = app_for_hover.get_webview_panel(label) {
                panel.make_key_window();
            }
        });
        panel.set_event_handler(Some(handler.as_ref()));
        panel.show();
        log::info!("[Overlay] {} panel visible={}", spec.label, panel.is_visible());
        true
    }

    pub(super) fn release<R: Runtime>(app: &AppHandle<R>, label: &str) {
        // tao reports a closed window only from its own delegate. Without
        // restoring it the label stays registered and the overlay never shows again.
        if let Ok(panel) = app.get_webview_panel(label) {
            panel.set_event_handler(None);
        }
        let _ = app.remove_webview_panel(label);
    }
}

/// Fallback for non-macOS platforms, and if the macOS panel can't be built.
fn create_window<R: Runtime>(app: &AppHandle<R>, spec: &'static OverlaySpec) {
    let window = match tauri::WebviewWindowBuilder::new(
        app,
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
    // The native shadow is drawn around the full rectangular window, which
    // shows as a box larger than the rounded card inside it.
    .shadow(false)
    .focused(false)
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

    let _ = window.show();
}

/// Shows the overlay in the top-right corner; no-op if it already exists.
pub(crate) fn show_overlay<R: Runtime>(app: &AppHandle<R>, spec: &'static OverlaySpec) {
    // Window creation requires the main thread on macOS -- callers fire from
    // background tasks, so dispatch it explicitly.
    let app_clone = app.clone();
    let _ = app.run_on_main_thread(move || {
        if app_clone.get_webview_window(spec.label).is_some() {
            return;
        }

        // Panels are Wry-only; any other runtime (e.g. tests) uses the plain window.
        #[cfg(target_os = "macos")]
        let created = (&app_clone as &dyn std::any::Any)
            .downcast_ref::<AppHandle>()
            .is_some_and(|wry| panel::create(wry, spec));
        #[cfg(not(target_os = "macos"))]
        let created = false;

        if !created {
            create_window(&app_clone, spec);
        }
        info!("[Overlay] showing {}", spec.label);
    });
}

pub(crate) fn close_overlay<R: Runtime>(app: &AppHandle<R>, label: &'static str) {
    // Existence is checked on the main thread, after any queued show_overlay
    // has run, so a close can't slip in before the window it should close.
    let app_clone = app.clone();
    let _ = app.run_on_main_thread(move || {
        #[cfg(target_os = "macos")]
        panel::release(&app_clone, label);

        if let Some(window) = app_clone.get_webview_window(label) {
            let _ = window.close();
            info!("[Overlay] closed {label}");
        }
    });
}
