// Small always-on-top notification shown only when a meeting has ended: it
// counts down to the auto-stop and offers "Keep recording" / "Stop now".
// Pause and stop for normal recording live in the tray menu.

use super::overlay_window::{close_overlay, show_overlay, OverlaySpec};
use super::recording_commands;
use serde::Serialize;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Emitter, Runtime};

const PILL_LABEL: &str = "recording-pill";
const PILL_SPEC: OverlaySpec = OverlaySpec {
    label: PILL_LABEL,
    url: "recording-pill",
    width: 360.0,
    height: 76.0,
};

pub const COUNTDOWN_SECS: u64 = 15;

#[derive(Debug, Clone, Copy, Serialize)]
pub struct MeetingEndCountdown {
    pub ends_at_ms: u64,
    pub duration_secs: u64,
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

/// Shows the notification only while a countdown is pending on a live recording.
pub async fn sync<R: Runtime>(app: &AppHandle<R>) {
    let counting = COUNTDOWN.lock().unwrap().is_some();
    if counting && recording_commands::is_recording().await {
        show_overlay(app, &PILL_SPEC);
    } else {
        close_overlay(app, PILL_LABEL);
    }
}

fn spawn_sync<R: Runtime>(app: &AppHandle<R>) {
    let app = app.clone();
    tauri::async_runtime::spawn(async move { sync(&app).await });
}

pub fn start_meeting_end_countdown<R: Runtime>(app: &AppHandle<R>, auto_stop: bool) {
    let generation = COUNTDOWN_GEN.fetch_add(1, Ordering::SeqCst) + 1;
    let countdown = MeetingEndCountdown {
        ends_at_ms: now_ms() + COUNTDOWN_SECS * 1000,
        duration_secs: COUNTDOWN_SECS,
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
