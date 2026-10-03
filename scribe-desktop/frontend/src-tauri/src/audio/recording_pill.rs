// Floating pill with recording controls (timer, pause/resume, stop). It also
// hosts the "meeting ended" countdown that precedes an auto-stop.

use super::overlay_window::{close_overlay, show_overlay, OverlaySpec};
use super::recording_commands;
use serde::Serialize;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Emitter, Listener, Manager, Runtime};

const PILL_LABEL: &str = "recording-pill";
const PILL_SPEC: OverlaySpec = OverlaySpec {
    label: PILL_LABEL,
    url: "recording-pill",
    width: 320.0,
    height: 72.0,
    corner_radius: 16.0,
};

pub const COUNTDOWN_SECS: u64 = 15;

#[derive(Debug, Clone, Copy, Serialize)]
pub struct MeetingEndCountdown {
    pub ends_at_ms: u64,
    pub auto_stop: bool,
}

static COUNTDOWN: Mutex<Option<MeetingEndCountdown>> = Mutex::new(None);
// Bumped on every start/cancel so a stale countdown task can tell it was superseded.
static COUNTDOWN_GEN: AtomicU64 = AtomicU64::new(0);
static KEEP_REQUESTED: AtomicBool = AtomicBool::new(false);

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

/// Shows the pill while recording, unless the user is already looking at
/// Scribe's own window (which has its own controls). Always shown during a
/// countdown so the stop can't happen unannounced.
pub async fn sync<R: Runtime>(app: &AppHandle<R>) {
    let recording = recording_commands::is_recording().await;
    let counting = COUNTDOWN.lock().unwrap().is_some();
    let main_focused = app
        .get_webview_window("main")
        .map(|w| w.is_focused().unwrap_or(false) && w.is_visible().unwrap_or(false))
        .unwrap_or(false);

    if recording && (counting || !main_focused) {
        show_overlay(app, &PILL_SPEC);
    } else {
        close_overlay(app, PILL_LABEL);
    }
}

fn spawn_sync<R: Runtime>(app: &AppHandle<R>) {
    let app = app.clone();
    tauri::async_runtime::spawn(async move { sync(&app).await });
}

/// Keeps the pill in step with recording lifecycle events from any start/stop path.
pub fn init<R: Runtime>(app: &AppHandle<R>) {
    for event in ["recording-started", "recording-stopped", "recording-stop-complete"] {
        let app_for_event = app.clone();
        app.listen(event, move |_| spawn_sync(&app_for_event));
    }
}

pub fn start_meeting_end_countdown<R: Runtime>(app: &AppHandle<R>, auto_stop: bool) {
    let generation = COUNTDOWN_GEN.fetch_add(1, Ordering::SeqCst) + 1;
    let countdown = MeetingEndCountdown {
        ends_at_ms: now_ms() + COUNTDOWN_SECS * 1000,
        auto_stop,
    };
    *COUNTDOWN.lock().unwrap() = Some(countdown);
    let _ = app.emit("meeting-end-countdown", countdown);
    spawn_sync(app);

    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(Duration::from_secs(COUNTDOWN_SECS)).await;

        // Checked and cleared under one lock so a concurrent "Keep recording"
        // either cancels us here or sees nothing left to cancel.
        let expired = {
            let mut countdown = COUNTDOWN.lock().unwrap();
            if COUNTDOWN_GEN.load(Ordering::SeqCst) != generation {
                false
            } else {
                *countdown = None;
                true
            }
        };
        if !expired {
            return;
        }
        let _ = app.emit("meeting-end-countdown-cleared", ());
        spawn_sync(&app);

        // The user may have already stopped it from the main window or tray.
        if auto_stop && recording_commands::is_recording().await {
            crate::tray::focus_main_window(&app);
            crate::tray::stop_and_finalize(&app).await;
        }
    });
}

/// Returns whether a pending countdown was actually cancelled.
pub fn cancel_countdown<R: Runtime>(app: &AppHandle<R>) -> bool {
    {
        let mut countdown = COUNTDOWN.lock().unwrap();
        if countdown.is_none() {
            return false;
        }
        COUNTDOWN_GEN.fetch_add(1, Ordering::SeqCst);
        *countdown = None;
    }
    let _ = app.emit("meeting-end-countdown-cleared", ());
    spawn_sync(app);
    true
}

/// True once if the user pressed "Keep recording" since the last check.
pub fn take_keep_requested() -> bool {
    KEEP_REQUESTED.swap(false, Ordering::SeqCst)
}

/// Current countdown, so a pill that opens mid-countdown can render it.
#[tauri::command]
pub async fn recording_pill_state() -> Option<MeetingEndCountdown> {
    *COUNTDOWN.lock().unwrap()
}

#[tauri::command]
pub async fn recording_pill_stop<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    cancel_countdown(&app);
    crate::tray::focus_main_window(&app);
    crate::tray::stop_and_finalize(&app).await;
    Ok(())
}

#[tauri::command]
pub async fn recording_pill_keep_recording<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    // Only re-arm the tracker if the click beat the countdown's expiry.
    if cancel_countdown(&app) {
        KEEP_REQUESTED.store(true, Ordering::SeqCst);
    }
    Ok(())
}
