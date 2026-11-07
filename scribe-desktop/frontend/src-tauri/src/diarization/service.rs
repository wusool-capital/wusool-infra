// diarization/service.rs
//
// Diarizes a saved meeting's audio, attributes its "others" lines, and auto-names voices the library knows.

use std::collections::HashSet;
use std::path::PathBuf;
use std::sync::{LazyLock, Mutex};

use anyhow::{Context, Result};
use log::{info, warn};
use serde::Serialize;
use sqlx::SqlitePool;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tokio::sync::Semaphore;

use super::assign::{attribute_segments, match_profiles, VoiceProfile, PROFILE_MATCH_THRESHOLD};
use super::engine::{self, DiarizationBackend};
use super::SpeakerLabel;
use crate::database::repositories::speaker::{DiarizedVoice, SpeakerRepository};

const SYSTEM_TRACK_FILE: &str = "system.mp4";
pub const DIARIZATION_EVENT: &str = "diarization-updated";

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum DiarizationOutcome {
    Completed { speakers: usize, auto_named: usize },
    Skipped { reason: String },
    Failed { error: String },
    /// Another run for this meeting is in progress; its own event reports the result.
    AlreadyRunning,
}

#[derive(Debug, Clone, Serialize)]
struct DiarizationEvent<'a> {
    meeting_id: &'a str,
    #[serde(flatten)]
    outcome: &'a DiarizationOutcome,
}

#[derive(Debug, Clone, Serialize)]
struct DiarizationStarted<'a> {
    meeting_id: &'a str,
    status: &'static str,
}

// One pipeline at a time: a CoreML run alone can peak near 2.7 GB.
static PIPELINE: LazyLock<Semaphore> = LazyLock::new(|| Semaphore::new(1));
static IN_FLIGHT: LazyLock<Mutex<HashSet<String>>> = LazyLock::new(|| Mutex::new(HashSet::new()));

/// Marks a meeting as being diarized until dropped.
struct InFlight(String);

impl InFlight {
    fn claim(meeting_id: &str) -> Option<Self> {
        let mut running = IN_FLIGHT.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        running.insert(meeting_id.to_string()).then(|| Self(meeting_id.to_string()))
    }
}

impl Drop for InFlight {
    fn drop(&mut self) {
        IN_FLIGHT.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).remove(&self.0);
    }
}

/// Runs diarization and reports the outcome to the frontend. Never errors, so callers can fire and forget.
pub async fn diarize_and_notify<R: Runtime>(app: &AppHandle<R>, pool: &SqlitePool, meeting_id: &str) -> DiarizationOutcome {
    let Some(_claim) = InFlight::claim(meeting_id) else {
        return DiarizationOutcome::AlreadyRunning;
    };
    let _ = app.emit(DIARIZATION_EVENT, DiarizationStarted { meeting_id, status: "running" });

    let outcome = match diarize_meeting(app, pool, meeting_id).await {
        Ok(outcome) => outcome,
        Err(e) => {
            warn!("Diarization failed for {}: {:#}", meeting_id, e);
            DiarizationOutcome::Failed { error: format!("{e:#}") }
        }
    };
    info!("Diarization for {}: {:?}", meeting_id, outcome);
    let _ = app.emit(DIARIZATION_EVENT, DiarizationEvent { meeting_id, outcome: &outcome });
    outcome
}

async fn diarize_meeting<R: Runtime>(app: &AppHandle<R>, pool: &SqlitePool, meeting_id: &str) -> Result<DiarizationOutcome> {
    let folder: Option<(Option<String>,)> = sqlx::query_as("SELECT folder_path FROM meetings WHERE id = ?")
        .bind(meeting_id)
        .fetch_optional(pool)
        .await?;
    let Some(system_track) = folder
        .and_then(|(path,)| path)
        .map(|path| PathBuf::from(path).join(SYSTEM_TRACK_FILE))
        .filter(|path| path.exists())
    else {
        return Ok(skipped("no separate meeting-audio track was recorded"));
    };

    let mut segments = SpeakerRepository::attributable_segments(pool, meeting_id).await?;
    if segments.is_empty() {
        return Ok(skipped("no meeting-audio segments to attribute"));
    }
    segments.sort_by(|a, b| a.audio_start_time.total_cmp(&b.audio_start_time));

    let app_data_dir = app.path().app_data_dir().context("resolving app data dir")?;
    let models_dir = engine::models_dir(&app_data_dir);
    let mut backend = super::commands::load_backend(app).effective();
    if let Err(e) = engine::ensure_models(&models_dir, backend).await {
        if backend == DiarizationBackend::Cpu {
            return Err(e.context("fetching diarization models"));
        }
        warn!("CoreML models unavailable, diarizing on CPU: {:#}", e);
        backend = DiarizationBackend::Cpu;
        engine::ensure_models(&models_dir, backend).await.context("fetching diarization models")?;
    }

    let _pipeline = PIPELINE.acquire().await.context("diarization queue closed")?;
    let diarization = tokio::task::spawn_blocking(move || -> Result<engine::Diarization> {
        let audio = super::audio::decode_16k_mono(&system_track)?;
        match engine::diarize(&models_dir, backend, &audio) {
            // CPU files always download with CoreML ones, so this retry has its models.
            Err(e) if backend == DiarizationBackend::CoreMl => {
                warn!("CoreML diarization failed, retrying on CPU: {:#}", e);
                engine::diarize(&models_dir, DiarizationBackend::Cpu, &audio)
            }
            result => result,
        }
    })
    .await??;

    // A voice without a usable embedding could never be recognised or enrolled, so its turns are dropped.
    let has_voiceprint = |cluster: u32| diarization.centroids.get(cluster as usize).is_some_and(|c| !c.is_empty());
    let turns: Vec<_> = diarization.turns.iter().copied().filter(|t| has_voiceprint(t.speaker)).collect();

    let spans: Vec<(f64, f64)> = segments.iter().map(|s| (s.audio_start_time, s.audio_end_time)).collect();
    let attribution = attribute_segments(&spans, &turns);

    let voice_embeddings: Vec<Vec<f32>> = attribution
        .label_clusters
        .iter()
        .map(|&cluster| diarization.centroids[cluster as usize].clone())
        .collect();
    let profiles: Vec<VoiceProfile> = SpeakerRepository::profile_embeddings(pool)
        .await?
        .into_iter()
        .map(|p| VoiceProfile { id: p.id, embedding: p.embedding })
        .collect();
    let matches = match_profiles(&voice_embeddings, &profiles, PROFILE_MATCH_THRESHOLD);

    let auto_named = matches.iter().filter(|m| m.is_some()).count();
    let voices: Vec<DiarizedVoice> = voice_embeddings
        .into_iter()
        .zip(matches)
        .enumerate()
        .map(|(index, (embedding, profile_id))| DiarizedVoice {
            label: SpeakerLabel::Speaker(index as u32),
            profile_id,
            embedding,
        })
        .collect();
    // Unmatched segments become "others", clearing labels from a previous run's replaced voices.
    let segment_labels: Vec<(String, SpeakerLabel)> = segments
        .into_iter()
        .zip(attribution.segment_labels)
        .map(|(segment, label)| (segment.id, label.map_or(SpeakerLabel::Others, SpeakerLabel::Speaker)))
        .collect();

    SpeakerRepository::save_diarization(pool, meeting_id, &voices, &segment_labels).await?;
    Ok(DiarizationOutcome::Completed { speakers: voices.len(), auto_named })
}

fn skipped(reason: &str) -> DiarizationOutcome {
    DiarizationOutcome::Skipped { reason: reason.to_string() }
}
