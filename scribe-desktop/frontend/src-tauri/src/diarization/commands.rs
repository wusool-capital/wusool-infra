// diarization/commands.rs
//
// Tauri commands for the voice library, speaker naming, the user's own name and the diarization backend.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tauri_plugin_store::StoreExt;

use super::engine::{self, DiarizationBackend, DownloadProgress};
use super::overview::{build_overview, SpeakerOverview};
use super::service::{diarize_and_notify, system_track_path, DiarizationOutcome};
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

const MODELS_PROGRESS_EVENT: &str = "diarization-models-progress";
const PROGRESS_EVERY: Duration = Duration::from_millis(150);
static CANCEL_DOWNLOAD: AtomicBool = AtomicBool::new(false);

#[derive(Debug, Clone, Serialize)]
pub struct DiarizationModelsStatus {
    pub cpu_ready: bool,
    pub coreml_ready: bool,
}

fn models_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    let app_data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    Ok(engine::models_dir(&app_data_dir))
}

#[tauri::command]
pub async fn get_diarization_models_status<R: Runtime>(app: AppHandle<R>) -> Result<DiarizationModelsStatus, String> {
    let dir = models_dir(&app)?;
    Ok(DiarizationModelsStatus {
        cpu_ready: engine::models_ready(&dir, DiarizationBackend::Cpu),
        coreml_ready: engine::models_ready(&dir, DiarizationBackend::CoreMl),
    })
}

/// Downloads a backend's models now, emitting progress, so the first meeting never waits on them.
#[tauri::command]
pub async fn download_diarization_models<R: Runtime>(
    app: AppHandle<R>,
    backend: DiarizationBackend,
) -> Result<(), String> {
    let dir = models_dir(&app)?;
    CANCEL_DOWNLOAD.store(false, Ordering::SeqCst);
    let mut last_emit: Option<Instant> = None;
    engine::download_models(&dir, backend, &CANCEL_DOWNLOAD, |progress: DownloadProgress| {
        let done = progress.downloaded >= progress.total;
        if done || last_emit.is_none_or(|at| at.elapsed() >= PROGRESS_EVERY) {
            last_emit = Some(Instant::now());
            let _ = app.emit(MODELS_PROGRESS_EVENT, progress);
        }
    })
    .await
    .map_err(|e| format!("{e:#}"))
}

#[tauri::command]
pub async fn cancel_diarization_model_download() -> Result<(), String> {
    CANCEL_DOWNLOAD.store(true, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
pub async fn delete_coreml_models<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    let dir = models_dir(&app)?;
    engine::delete_coreml_models(&dir).await.map_err(|e| format!("{e:#}"))
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
pub async fn get_speaker_overview(
    state: tauri::State<'_, AppState>,
    meeting_id: String,
) -> Result<Vec<SpeakerOverview>, String> {
    let pool = state.db_manager.pool();
    let voices = SpeakerRepository::voice_overview(pool, &meeting_id).await.map_err(|e| e.to_string())?;
    let profiles = SpeakerRepository::named_profiles(pool).await.map_err(|e| e.to_string())?;
    Ok(build_overview(voices, &profiles))
}

// Long enough to recognise a voice; capped at the sample line so it never runs into the next speaker.
const VOICE_CLIP_MAX_SECS: f64 = 6.0;

/// A few seconds of a voice from the meeting audio, as WAV bytes the transcript can play.
#[tauri::command]
pub async fn speaker_voice_clip(
    state: tauri::State<'_, AppState>,
    meeting_id: String,
    label: SpeakerLabel,
) -> Result<tauri::ipc::Response, String> {
    let pool = state.db_manager.pool();
    let voices = SpeakerRepository::voice_overview(pool, &meeting_id).await.map_err(|e| e.to_string())?;
    let sample = voices
        .into_iter()
        .find(|v| v.label == label)
        .and_then(|v| v.sample)
        .ok_or_else(|| format!("{label} has no lines in this meeting"))?;
    let track = system_track_path(pool, &meeting_id)
        .await
        .map_err(|e| e.to_string())?
        .ok_or_else(|| "The meeting audio for this recording is missing".to_string())?;

    let duration = (sample.end - sample.start).clamp(0.5, VOICE_CLIP_MAX_SECS);
    let wav = tokio::task::spawn_blocking(move || {
        super::audio::decode_16k_mono_clip(&track, sample.start, duration).map(|samples| super::audio::wav_16k_mono(&samples))
    })
    .await
    .map_err(|e| e.to_string())?
    .map_err(|e| format!("{e:#}"))?;
    Ok(tauri::ipc::Response::new(wav))
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
