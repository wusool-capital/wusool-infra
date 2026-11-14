//! Per-meeting user notes (AZM-173): typed live during a recording (in the
//! main window or the floating notepad), stored per meeting in SQLite, sent
//! with the first push and re-synced to the server on later edits.

pub mod live;
pub mod notepad;

use std::collections::HashSet;
use std::sync::Mutex;

use log::warn;
use once_cell::sync::Lazy;
use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, Runtime};

use crate::database::repositories::meeting_notes::{MeetingNotes, MeetingNotesRepository};
use crate::database::repositories::transcript::TranscriptsRepository;
use crate::state::AppState;

// Typing saves every ~500ms; batch those into one server call per window.
const SYNC_DELAY: std::time::Duration = std::time::Duration::from_secs(3);

static SCHEDULED_SYNCS: Lazy<Mutex<HashSet<String>>> = Lazy::new(|| Mutex::new(HashSet::new()));

#[derive(Debug, Clone, Serialize)]
pub struct NotesSyncEvent {
    pub meeting_id: String,
    pub synced: bool,
}

#[tauri::command]
pub async fn get_meeting_notes(
    state: tauri::State<'_, AppState>,
    meeting_id: String,
) -> Result<Option<MeetingNotes>, String> {
    MeetingNotesRepository::get(state.db_manager.pool(), &meeting_id)
        .await
        .map_err(|e| format!("Failed to load notes for {}: {}", meeting_id, e))
}

/// Not gated by the transcript's push lock: notes stay editable after a push.
#[tauri::command]
pub async fn save_meeting_notes<R: Runtime>(
    app: AppHandle<R>,
    state: tauri::State<'_, AppState>,
    meeting_id: String,
    notes_markdown: Option<String>,
    notes_json: Option<String>,
) -> Result<(), String> {
    MeetingNotesRepository::upsert(
        state.db_manager.pool(),
        &meeting_id,
        notes_markdown.as_deref(),
        notes_json.as_deref(),
    )
    .await
    .map_err(|e| format!("Failed to save notes for {}: {}", meeting_id, e))?;
    schedule_sync(&app, meeting_id);
    Ok(())
}

fn schedule_sync<R: Runtime>(app: &AppHandle<R>, meeting_id: String) {
    if !SCHEDULED_SYNCS.lock().unwrap().insert(meeting_id.clone()) {
        return;
    }
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(SYNC_DELAY).await;
        SCHEDULED_SYNCS.lock().unwrap().remove(&meeting_id);

        let Some(state) = app.try_state::<AppState>() else { return };
        let pool = state.db_manager.pool();
        match TranscriptsRepository::is_meeting_pushed(pool, &meeting_id).await {
            Ok(true) => {}
            Ok(false) => return,
            Err(e) => {
                warn!("Notes sync: couldn't read push state for {}: {}", meeting_id, e);
                return;
            }
        }
        let synced = match crate::push::sync_meeting_notes(&app, pool, &meeting_id).await {
            Ok(()) => true,
            Err(e) => {
                warn!("Notes sync failed for {} (retried by the background loop): {}", meeting_id, e);
                false
            }
        };
        let _ = app.emit("meeting-notes-sync", NotesSyncEvent { meeting_id, synced });
    });
}
