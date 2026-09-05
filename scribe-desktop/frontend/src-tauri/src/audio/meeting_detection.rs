// Lightweight, zero-install "is the user in a meeting" signal + a small
// always-on-top popup that suggests recording.
//
// Detection uses per-process CoreAudio mic attribution
// (kAudioHardwarePropertyProcessObjectList / Process::is_running_input) rather
// than the device-wide kAudioDevicePropertyDeviceIsRunningSomewhere flag --
// that flag is an OR across every process on the machine, so once anything
// (including our own permission-check stream) touches the mic it pins `true`
// forever and a real meeting produces no edge. Per-process attribution tells
// us *who* has the mic open, which is what self-exclusion and browser-based
// meetings (Meet/etc. show up as the browser's own audio-input process) both
// need.
//
// Implemented as a cheap poll (every few seconds) rather than a property
// listener: process objects can appear/disappear as apps start/stop using
// audio, and following that churn with dynamic per-object listeners is a lot
// of bookkeeping for what a few property reads every few seconds does just
// as well, at negligible CPU next to actually capturing audio.
//
// macOS only, requires macOS 14.4+ (kAudioHardwarePropertyProcessObjectList).

use log::info;
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::{AppHandle, Emitter, Manager, Runtime};

/// Set when the user dismisses the popup for the meeting currently in
/// progress, so it doesn't immediately reappear next poll. Cleared once the
/// mic-activity signal drops (the "meeting" this dismissal applied to ended).
static POPUP_DISMISSED: AtomicBool = AtomicBool::new(false);

const POPUP_LABEL: &str = "meeting-popup";
const POPUP_WIDTH: f64 = 320.0;
const POPUP_HEIGHT: f64 = 78.0;
const POPUP_MARGIN: f64 = 12.0;
const POPUP_CORNER_RADIUS: f64 = 16.0;

fn show_popup<R: Runtime>(app: &AppHandle<R>) {
    if app.get_webview_window(POPUP_LABEL).is_some() {
        return;
    }

    // Window creation and window-vibrancy both require the main thread on
    // macOS (apply_vibrancy panics/errors otherwise) -- this fires from the
    // detection loop's background task, so dispatch it explicitly.
    let app_clone = app.clone();
    let _ = app.run_on_main_thread(move || {
        if app_clone.get_webview_window(POPUP_LABEL).is_some() {
            return;
        }

        let window = match tauri::WebviewWindowBuilder::new(
            &app_clone,
            POPUP_LABEL,
            tauri::WebviewUrl::App("meeting-popup".into()),
        )
        .title("")
        .inner_size(POPUP_WIDTH, POPUP_HEIGHT)
        .resizable(false)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .transparent(true)
        .focused(false)
        .build()
        {
            Ok(window) => window,
            Err(err) => {
                log::warn!("[MeetingDetection] failed to create popup window: {err:?}");
                return;
            }
        };

        if let Ok(Some(monitor)) = window.current_monitor() {
            let scale = monitor.scale_factor();
            let screen = monitor.size().to_logical::<f64>(scale);
            let x = (screen.width - POPUP_WIDTH - POPUP_MARGIN).max(0.0);
            let _ = window.set_position(tauri::Position::Logical(tauri::LogicalPosition::new(
                x,
                POPUP_MARGIN,
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
                Some(POPUP_CORNER_RADIUS),
            ) {
                log::warn!("[MeetingDetection] failed to apply popup vibrancy: {err:?}");
            }
        }

        let _ = window.show();
        info!("[MeetingDetection] showing meeting-detected popup");
    });
}

fn close_popup<R: Runtime>(app: &AppHandle<R>) {
    let app_clone = app.clone();
    let _ = app.run_on_main_thread(move || {
        if let Some(window) = app_clone.get_webview_window(POPUP_LABEL) {
            let _ = window.close();
            info!("[MeetingDetection] closed meeting-detected popup");
        }
    });
}

/// Invoked by the popup's "Start Recording" button.
#[tauri::command]
pub async fn meeting_popup_start_recording<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    POPUP_DISMISSED.store(false, Ordering::Relaxed);
    close_popup(&app);

    if let Some(main) = app.get_webview_window("main") {
        let _ = main.show();
        let _ = main.set_focus();
    }

    // Reuse the same event the tray icon uses to toggle recording from the
    // main window's existing listener (src/app/layout.tsx).
    let _ = app.emit("request-recording-toggle", ());
    Ok(())
}

/// Invoked by the popup's dismiss (X) button.
#[tauri::command]
pub async fn meeting_popup_dismiss<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    POPUP_DISMISSED.store(true, Ordering::Relaxed);
    close_popup(&app);
    Ok(())
}

#[cfg(target_os = "macos")]
mod macos {
    use super::*;
    use crate::audio::recording_commands;
    use cidre::core_audio as ca;
    use std::collections::HashSet;
    use std::time::Duration;

    const POLL_INTERVAL: Duration = Duration::from_secs(3);
    // Consecutive polls the signal must hold before we act, so a momentary
    // blip doesn't pop a window open or snap it shut.
    const ACTIVE_THRESHOLD: u32 = 2;
    const INACTIVE_THRESHOLD: u32 = 2;

    // Apps whose mic use plausibly means "in a meeting" -- dedicated calling
    // apps plus browsers, since browser-based meetings (Meet, Teams-web, ...)
    // show up as the browser's own audio-input process, not a distinct app.
    const MEETING_BUNDLE_IDS: &[&str] = &[
        "us.zoom.xos",
        "com.microsoft.teams2",
        "com.microsoft.teams",
        "com.webex.meetingmanager",
        "com.cisco.webexmeetingsapp",
        "com.skype.skype",
        "com.hnc.Discord",
        "com.tinyspeck.slackmacgap",
        "com.apple.FaceTime",
        "com.google.Chrome",
        "com.google.Chrome.beta",
        "org.mozilla.firefox",
        "com.apple.Safari",
        "com.microsoft.edgemac",
        "company.thebrowser.browser",
        "com.brave.Browser",
        "com.operasoftware.Opera",
        "com.vivaldi.Vivaldi",
    ];

    fn active_meeting_processes(own_pid: i32) -> Vec<(i32, String)> {
        let Ok(processes) = ca::System::processes() else {
            return Vec::new();
        };

        processes
            .iter()
            .filter_map(|process| {
                let pid = process.pid().ok()?;
                if pid == own_pid {
                    return None;
                }
                if !process.is_running_input().unwrap_or(false) {
                    return None;
                }
                let bundle_id = process.bundle_id().map(|s| s.to_string()).ok()?;
                // Chromium-based browsers route audio through a helper
                // sub-process (e.g. "company.thebrowser.browser.helper"),
                // not the main app bundle id -- prefix-match to catch those.
                MEETING_BUNDLE_IDS
                    .iter()
                    .any(|prefix| bundle_id.starts_with(prefix))
                    .then_some((pid, bundle_id))
            })
            .collect()
    }

    pub fn start_probe<R: Runtime>(app: AppHandle<R>) {
        let own_pid = std::process::id() as i32;

        tauri::async_runtime::spawn(async move {
            let mut consecutive_active: u32 = 0;
            let mut consecutive_inactive: u32 = 0;
            let mut last_logged: HashSet<i32> = HashSet::new();

            loop {
                if recording_commands::is_recording().await {
                    close_popup(&app);
                    // Suppress re-prompting once this meeting has already been
                    // recorded, even after the user stops -- otherwise the
                    // same still-open call (mic still active) immediately
                    // re-triggers the prompt. Cleared once mic activity
                    // actually drops (INACTIVE_THRESHOLD below), i.e. the
                    // call itself ends.
                    POPUP_DISMISSED.store(true, Ordering::Relaxed);
                    consecutive_active = 0;
                    consecutive_inactive = 0;
                    tokio::time::sleep(POLL_INTERVAL).await;
                    continue;
                }

                let active = active_meeting_processes(own_pid);
                let current_pids: HashSet<i32> = active.iter().map(|(pid, _)| *pid).collect();

                if current_pids != last_logged {
                    if active.is_empty() {
                        info!("[MeetingDetection] no meeting-app/browser mic activity");
                    } else {
                        info!("[MeetingDetection] meeting-app mic activity: {active:?}");
                    }
                    last_logged = current_pids;
                }

                if active.is_empty() {
                    consecutive_inactive += 1;
                    consecutive_active = 0;
                } else {
                    consecutive_active += 1;
                    consecutive_inactive = 0;
                }

                if consecutive_active == ACTIVE_THRESHOLD && !POPUP_DISMISSED.load(Ordering::Relaxed)
                {
                    show_popup(&app);
                }

                if consecutive_inactive == INACTIVE_THRESHOLD {
                    close_popup(&app);
                    POPUP_DISMISSED.store(false, Ordering::Relaxed);
                }

                tokio::time::sleep(POLL_INTERVAL).await;
            }
        });

        info!("[MeetingDetection] per-process mic probe started (own_pid={own_pid})");
    }
}

#[cfg(target_os = "macos")]
pub use macos::start_probe;

#[cfg(not(target_os = "macos"))]
pub fn start_probe<R: Runtime>(_app: AppHandle<R>) {
    log::info!("[MeetingDetection] probe is macOS-only, skipping on this platform");
}
