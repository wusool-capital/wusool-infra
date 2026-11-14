//! Notes typed before the meeting row exists. Kept as a draft file in the
//! recording folder, which exists from recording start, so it survives a
//! crash and the transcript-recovery path, and is attached to the meeting
//! when `api_save_transcript` creates it.

use std::path::{Path, PathBuf};
use std::sync::Mutex;

use log::{info, warn};
use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;

use crate::audio::recording_commands::get_meeting_folder_path;
use crate::database::repositories::meeting_notes::MeetingNotesRepository;

const DRAFT_FILE: &str = "notes.draft.json";

// The folder path is gone once stop takes the recording manager, but a save
// debounced just before stop must still land in this recording's folder.
static LAST_FOLDER: Mutex<Option<PathBuf>> = Mutex::new(None);

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LiveNotes {
    pub notes_markdown: Option<String>,
    pub notes_json: Option<String>,
}

async fn draft_folder() -> Option<PathBuf> {
    if let Ok(Some(path)) = get_meeting_folder_path().await {
        let path = PathBuf::from(path);
        *LAST_FOLDER.lock().unwrap() = Some(path.clone());
        return Some(path);
    }
    LAST_FOLDER.lock().unwrap().clone()
}

fn read_draft(folder: &Path) -> Option<LiveNotes> {
    let raw = std::fs::read_to_string(folder.join(DRAFT_FILE)).ok()?;
    serde_json::from_str(&raw)
        .map_err(|e| warn!("Ignoring unreadable notes draft in {}: {}", folder.display(), e))
        .ok()
}

fn write_draft(folder: &Path, notes: &LiveNotes) -> Result<(), String> {
    let json = serde_json::to_string(notes).map_err(|e| e.to_string())?;
    // Write-then-rename so a crash mid-write never leaves a truncated draft.
    let tmp = folder.join(format!("{DRAFT_FILE}.tmp"));
    std::fs::write(&tmp, json).map_err(|e| format!("Failed to write notes draft: {}", e))?;
    std::fs::rename(&tmp, folder.join(DRAFT_FILE))
        .map_err(|e| format!("Failed to save notes draft: {}", e))
}

#[tauri::command]
pub async fn get_live_notes() -> Result<Option<LiveNotes>, String> {
    Ok(draft_folder().await.and_then(|folder| read_draft(&folder)))
}

#[tauri::command]
pub async fn save_live_notes(
    notes_markdown: Option<String>,
    notes_json: Option<String>,
) -> Result<(), String> {
    let folder = draft_folder()
        .await
        .ok_or_else(|| "No recording folder, so notes can't be saved.".to_string())?;
    write_draft(&folder, &LiveNotes { notes_markdown, notes_json })
}

/// Moves a recording's draft into `meeting_notes` for the newly created meeting.
pub async fn attach_draft(pool: &SqlitePool, folder: &Path, meeting_id: &str) {
    let Some(draft) = read_draft(folder) else { return };
    if let Err(e) = MeetingNotesRepository::upsert(
        pool,
        meeting_id,
        draft.notes_markdown.as_deref(),
        draft.notes_json.as_deref(),
    )
    .await
    {
        // Leave the draft on disk so nothing typed is lost.
        warn!("Failed to attach notes draft to {}: {}", meeting_id, e);
        return;
    }
    if let Err(e) = std::fs::remove_file(folder.join(DRAFT_FILE)) {
        warn!("Attached notes draft but couldn't remove it: {}", e);
    }
    let mut last = LAST_FOLDER.lock().unwrap();
    if last.as_deref() == Some(folder) {
        *last = None;
    }
    info!("Attached live notes draft to meeting {}", meeting_id);
}

#[cfg(test)]
mod tests {
    use super::*;
    use sqlx::sqlite::SqlitePoolOptions;

    #[tokio::test]
    async fn attach_moves_draft_into_meeting_notes() {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::migrate!("./migrations").run(&pool).await.unwrap();
        sqlx::query("INSERT INTO meetings (id, title, created_at, updated_at) VALUES ('m1', 't', 'now', 'now')")
            .execute(&pool)
            .await
            .unwrap();
        let dir = tempfile::tempdir().unwrap();
        let draft = LiveNotes { notes_markdown: Some("- SOC2".into()), notes_json: Some("[]".into()) };
        write_draft(dir.path(), &draft).unwrap();

        attach_draft(&pool, dir.path(), "m1").await;

        let stored = MeetingNotesRepository::get(&pool, "m1").await.unwrap().unwrap();
        assert_eq!(stored.notes_markdown.as_deref(), Some("- SOC2"));
        assert!(!dir.path().join(DRAFT_FILE).exists());
    }

    #[tokio::test]
    async fn attach_without_draft_is_a_no_op() {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::migrate!("./migrations").run(&pool).await.unwrap();
        let dir = tempfile::tempdir().unwrap();

        attach_draft(&pool, dir.path(), "m1").await;

        assert!(MeetingNotesRepository::get(&pool, "m1").await.unwrap().is_none());
    }
}
