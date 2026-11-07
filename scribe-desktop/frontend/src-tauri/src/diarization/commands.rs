// diarization/commands.rs
//
// Tauri commands for speaker names: the voice library, per-meeting naming, the local
// user's own display name, and which backend diarization runs on.

use serde::Serialize;
use tauri::{AppHandle, Runtime};
use tauri_plugin_store::StoreExt;

use super::engine::DiarizationBackend;
use super::service::{diarize_and_notify, DiarizationOutcome};
use super::SpeakerLabel;
use crate::database::repositories::speaker::{MeetingSpeaker, SpeakerProfileSummary, SpeakerRepository};
use crate::state::AppState;

const SETTINGS_STORE: &str = "diarization.json";
const SELF_NAME_KEY: &str = "self_name";
const BACKEND_KEY: &str = "backend";

#[derive(Debug, Clone, Serialize)]
pub struct DiarizationBackendSettings {
    pub backend: DiarizationBackend,
    /// False off macOS, where the CoreML option is hidden.
    pub coreml_available: bool,
}

pub fn load_backend<R: Runtime>(app: &AppHandle<R>) -> DiarizationBackend {
    app.store(SETTINGS_STORE)
        .ok()
        .and_then(|store| store.get(BACKEND_KEY))
        .and_then(|value| serde_json::from_value(value).ok())
        .unwrap_or_default()
}

#[tauri::command]
pub async fn get_diarization_backend<R: Runtime>(app: AppHandle<R>) -> Result<DiarizationBackendSettings, String> {
    Ok(DiarizationBackendSettings {
        backend: load_backend(&app),
        coreml_available: DiarizationBackend::coreml_available(),
    })
}

#[tauri::command]
pub async fn set_diarization_backend<R: Runtime>(app: AppHandle<R>, backend: DiarizationBackend) -> Result<(), String> {
    let store = app.store(SETTINGS_STORE).map_err(|e| e.to_string())?;
    store.set(BACKEND_KEY, serde_json::to_value(backend).map_err(|e| e.to_string())?);
    store.save().map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn diarize_meeting<R: Runtime>(
    app: AppHandle<R>,
    state: tauri::State<'_, AppState>,
    meeting_id: String,
) -> Result<DiarizationOutcome, String> {
    Ok(diarize_and_notify(&app, state.db_manager.pool(), &meeting_id).await)
}

#[tauri::command]
pub async fn get_meeting_speakers(
    state: tauri::State<'_, AppState>,
    meeting_id: String,
) -> Result<Vec<MeetingSpeaker>, String> {
    SpeakerRepository::meeting_speakers(state.db_manager.pool(), &meeting_id)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn name_meeting_speaker(
    state: tauri::State<'_, AppState>,
    meeting_id: String,
    label: SpeakerLabel,
    name: String,
) -> Result<(), String> {
    let name = name.trim();
    if name.is_empty() {
        return Err("Speaker name cannot be empty".to_string());
    }
    SpeakerRepository::name_meeting_speaker(state.db_manager.pool(), &meeting_id, label, name)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn list_speaker_profiles(
    state: tauri::State<'_, AppState>,
) -> Result<Vec<SpeakerProfileSummary>, String> {
    SpeakerRepository::list_profiles(state.db_manager.pool())
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_speaker_profile(
    state: tauri::State<'_, AppState>,
    profile_id: String,
) -> Result<(), String> {
    SpeakerRepository::delete_profile(state.db_manager.pool(), &profile_id)
        .await
        .map_err(|e| e.to_string())
}

pub fn load_self_name<R: Runtime>(app: &AppHandle<R>) -> Option<String> {
    app.store(SETTINGS_STORE)
        .ok()?
        .get(SELF_NAME_KEY)?
        .as_str()
        .map(str::to_string)
        .filter(|name| !name.trim().is_empty())
}

#[tauri::command]
pub async fn get_self_speaker_name<R: Runtime>(app: AppHandle<R>) -> Result<Option<String>, String> {
    Ok(load_self_name(&app))
}

#[tauri::command]
pub async fn set_self_speaker_name<R: Runtime>(app: AppHandle<R>, name: Option<String>) -> Result<(), String> {
    let store = app.store(SETTINGS_STORE).map_err(|e| e.to_string())?;
    match name.map(|n| n.trim().to_string()).filter(|n| !n.is_empty()) {
        Some(name) => store.set(SELF_NAME_KEY, name),
        None => {
            store.delete(SELF_NAME_KEY);
        }
    }
    store.save().map_err(|e| e.to_string())
}
