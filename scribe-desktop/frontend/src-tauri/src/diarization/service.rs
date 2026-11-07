// diarization/service.rs
//
// Runs diarization for a saved meeting: decode the meeting-audio track, find the voices,
// attribute "others" segments to them, and auto-name voices found in the voice library.

use std::path::PathBuf;

use anyhow::{Context, Result};
use log::{info, warn};
use serde::Serialize;
use sqlx::SqlitePool;
use tauri::{AppHandle, Emitter, Manager, Runtime};

use super::assign::{attribute_segments, match_profiles, VoiceProfile, PROFILE_MATCH_THRESHOLD};
use super::engine;
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
}

#[derive(Debug, Clone, Serialize)]
struct DiarizationEvent<'a> {
    meeting_id: &'a str,
    #[serde(flatten)]
    outcome: &'a DiarizationOutcome,
}

/// Runs diarization and reports the outcome to the frontend; never returns an error so
/// it can be fired and forgotten after a meeting is saved.
pub async fn diarize_and_notify<R: Runtime>(app: &AppHandle<R>, pool: &SqlitePool, meeting_id: &str) -> DiarizationOutcome {
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
    engine::ensure_models(&models_dir).await.context("fetching diarization models")?;

    let diarization = tokio::task::spawn_blocking(move || -> Result<engine::Diarization> {
        let audio = super::audio::decode_16k_mono(&system_track)?;
        engine::diarize(&models_dir, &audio)
    })
    .await??;

    let spans: Vec<(f64, f64)> = segments.iter().map(|s| (s.audio_start_time, s.audio_end_time)).collect();
    let attribution = attribute_segments(&spans, &diarization.turns);

    let voice_embeddings: Vec<Vec<f32>> = attribution
        .label_clusters
        .iter()
        .map(|&cluster| diarization.centroids.get(cluster as usize).cloned().unwrap_or_default())
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
    // Segments no voice overlaps become "others" rather than being guessed, which also
    // clears labels left by a previous run whose voices are being replaced.
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
