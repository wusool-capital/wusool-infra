//! Floating, always-on-top notepad shown during a recording. Built on the
//! shared overlay panel, so it floats over full-screen meeting apps and stays
//! out of screen shares.

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{AppHandle, Emitter, Runtime};

use crate::audio::overlay_window::{close_overlay, show_overlay, OverlaySpec};
use crate::audio::recording_commands;

const NOTEPAD_LABEL: &str = "notepad";
const NOTEPAD_SPEC: OverlaySpec = OverlaySpec {
    label: NOTEPAD_LABEL,
    url: "notepad",
    width: 360.0,
    height: 480.0,
    resizable: true,
};

static OPEN: AtomicBool = AtomicBool::new(false);

fn set_open<R: Runtime>(app: &AppHandle<R>, open: bool) {
    if OPEN.swap(open, Ordering::SeqCst) != open {
        // The main window and the notepad take turns editing the draft.
        let _ = app.emit("notepad-visibility", open);
    }
}

pub fn open<R: Runtime>(app: &AppHandle<R>) {
    show_overlay(app, &NOTEPAD_SPEC);
    set_open(app, true);
}

/// Hides (never destroys) the panel; see `overlay_window`'s hide.
pub fn hide<R: Runtime>(app: &AppHandle<R>) {
    close_overlay(app, NOTEPAD_LABEL);
    set_open(app, false);
}

#[tauri::command]
pub async fn open_notepad<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    if !recording_commands::is_recording().await {
        return Err("The notepad is available only while a meeting is recording.".to_string());
    }
    open(&app);
    Ok(())
}

#[tauri::command]
pub async fn close_notepad<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    hide(&app);
    Ok(())
}

#[tauri::command]
pub fn is_notepad_open() -> bool {
    OPEN.load(Ordering::SeqCst)
}
