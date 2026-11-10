// diarization/service.rs
//
// Diarizes a saved meeting's audio, attributes its "others" lines, and auto-names voices the library knows.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{LazyLock, Mutex};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use log::{info, warn};
use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tokio::sync::Semaphore;

use super::assign::{attribute_segments, longest_turn, match_profiles, VoiceProfile, PROFILE_MATCH_MARGIN, PROFILE_MATCH_THRESHOLD};
use super::engine::{self, DiarizationBackend};
use super::worker;
use super::SpeakerLabel;
use crate::database::repositories::speaker::{DiarizedVoice, SpeakerRepository};

const SYSTEM_TRACK_FILE: &str = "system.mp4";
const FOLDER_METADATA_FILE: &str = "metadata.json";
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

/// A run in progress; `estimated_seconds` arrives once the run leaves the queue and its backend is known.
#[derive(Debug, Clone, Copy, Default, Serialize)]
pub struct DiarizationRun {
    pub started_at_ms: Option<u64>,
    pub estimated_seconds: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
struct DiarizationStarted<'a> {
    meeting_id: &'a str,
    status: &'static str,
    #[serde(flatten)]
    run: DiarizationRun,
}

// One pipeline at a time: a CoreML run alone can peak near 2.7 GB.
static PIPELINE: LazyLock<Semaphore> = LazyLock::new(|| Semaphore::new(1));
static IN_FLIGHT: LazyLock<Mutex<HashMap<String, DiarizationRun>>> = LazyLock::new(|| Mutex::new(HashMap::new()));

fn in_flight() -> std::sync::MutexGuard<'static, HashMap<String, DiarizationRun>> {
    IN_FLIGHT.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
}

pub fn running_status(meeting_id: &str) -> Option<DiarizationRun> {
    in_flight().get(meeting_id).copied()
}

/// Marks a meeting as being diarized until dropped.
struct InFlight(String);

impl InFlight {
    fn claim(meeting_id: &str) -> Option<Self> {
        let mut running = in_flight();
        if running.contains_key(meeting_id) {
            return None;
        }
        running.insert(meeting_id.to_string(), DiarizationRun::default());
        Some(Self(meeting_id.to_string()))
    }
}

impl Drop for InFlight {
    fn drop(&mut self) {
        in_flight().remove(&self.0);
    }
}

/// Runs diarization and reports the outcome to the frontend. Never errors, so callers can fire and forget.
pub async fn diarize_and_notify<R: Runtime>(app: &AppHandle<R>, pool: &SqlitePool, meeting_id: &str) -> DiarizationOutcome {
    let Some(claim) = InFlight::claim(meeting_id) else {
        return DiarizationOutcome::AlreadyRunning;
    };
    let _ = app.emit(DIARIZATION_EVENT, DiarizationStarted { meeting_id, status: "running", run: DiarizationRun::default() });

    let outcome = match diarize_meeting(app, pool, meeting_id).await {
        Ok(outcome) => outcome,
        Err(e) => {
            warn!("Diarization failed for {}: {:#}", meeting_id, e);
            DiarizationOutcome::Failed { error: format!("{e:#}") }
        }
    };
    info!("Diarization for {}: {:?}", meeting_id, outcome);
    // Released first: the UI re-reads the status on this event and must not see the run still in flight.
    drop(claim);
    let _ = app.emit(DIARIZATION_EVENT, DiarizationEvent { meeting_id, outcome: &outcome });
    outcome
}

/// The fields of a meeting folder's metadata.json that say whether, and from which file, it was imported.
#[derive(Deserialize)]
struct FolderMetadata {
    source: Option<String>,
    audio_file: Option<String>,
}

/// Meeting audio without the user's microphone: a recording's system track, or an imported file.
pub async fn meeting_audio_track(pool: &SqlitePool, meeting_id: &str) -> Result<Option<PathBuf>> {
    let folder: Option<(Option<String>,)> = sqlx::query_as("SELECT folder_path FROM meetings WHERE id = ?")
        .bind(meeting_id)
        .fetch_optional(pool)
        .await?;
    let Some(folder) = folder.and_then(|(path,)| path).map(PathBuf::from) else {
        return Ok(None);
    };
    let system_track = folder.join(SYSTEM_TRACK_FILE);
    if system_track.exists() {
        return Ok(Some(system_track));
    }
    Ok(imported_audio(&folder))
}

// An imported file has no microphone track mixed in, so all of it is meeting audio.
fn imported_audio(folder: &Path) -> Option<PathBuf> {
    let text = std::fs::read_to_string(folder.join(FOLDER_METADATA_FILE)).ok()?;
    let metadata: FolderMetadata = serde_json::from_str(&text).ok()?;
    if metadata.source.as_deref() != Some("import") {
        return None;
    }
    let path = folder.join(metadata.audio_file?);
    path.exists().then_some(path)
}

async fn diarize_meeting<R: Runtime>(app: &AppHandle<R>, pool: &SqlitePool, meeting_id: &str) -> Result<DiarizationOutcome> {
    let Some(system_track) = meeting_audio_track(pool, meeting_id).await? else {
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
    // The ~300 MB CoreML download only starts when the user asks for it (Settings, or
    // the download prompt on Separate Speakers); until then separation runs on CPU.
    if backend == DiarizationBackend::CoreMl && !engine::models_ready(&models_dir, backend) {
        backend = DiarizationBackend::Cpu;
    }
    if let Err(e) = engine::ensure_models(&models_dir, backend).await {
        if backend == DiarizationBackend::Cpu {
            return Err(e.context("fetching diarization models"));
        }
        warn!("CoreML models unavailable, diarizing on CPU: {:#}", e);
        backend = DiarizationBackend::Cpu;
        engine::ensure_models(&models_dir, backend).await.context("fetching diarization models")?;
    }

    let _pipeline = PIPELINE.acquire().await.context("diarization queue closed")?;
    // The last line's end stands in for the audio length, which is unknown until decoded.
    let audio_secs = segments.iter().map(|s| s.audio_end_time).fold(0.0, f64::max);
    let speed = super::commands::load_speed(app);
    let run = DiarizationRun {
        started_at_ms: Some(epoch_ms()),
        estimated_seconds: Some(speed.estimate_secs(backend, audio_secs)),
    };
    if let Some(entry) = in_flight().get_mut(meeting_id) {
        *entry = run;
    }
    let _ = app.emit(DIARIZATION_EVENT, DiarizationStarted { meeting_id, status: "running", run });

    let started = Instant::now();
    let limit = worker::time_limit(speed.estimate_secs(backend, audio_secs));
    let diarization = match worker::diarize_in_worker(&system_track, &models_dir, backend, limit).await {
        Ok(diarization) => {
            info!("Diarized {} ({:.0} s of audio) on {:?} in {:.1} s", meeting_id, audio_secs, backend, started.elapsed().as_secs_f64());
            let learned = speed.learn(backend, audio_secs, started.elapsed().as_secs_f64());
            if let Err(e) = super::commands::save_speed(app, learned) {
                warn!("Could not save separation speed: {}", e);
            }
            diarization
        }
        // CPU files always download with CoreML ones, and CPU stays near 0.5 GB where CoreML can balloon.
        Err(e) if backend == DiarizationBackend::CoreMl => {
            warn!("CoreML diarization failed for {}, retrying on CPU: {:#}", meeting_id, e);
            let cpu = DiarizationBackend::Cpu;
            let estimate = speed.estimate_secs(cpu, audio_secs);
            let retry = DiarizationRun { started_at_ms: Some(epoch_ms()), estimated_seconds: Some(estimate) };
            if let Some(entry) = in_flight().get_mut(meeting_id) {
                *entry = retry;
            }
            let _ = app.emit(DIARIZATION_EVENT, DiarizationStarted { meeting_id, status: "running", run: retry });
            let retry_started = Instant::now();
            let diarization = worker::diarize_in_worker(&system_track, &models_dir, cpu, worker::time_limit(estimate))
                .await
                .context("separating speakers on CPU after CoreML failed")?;
            // Learned too, so the CPU estimate and time limit adapt on machines that keep falling back.
            if let Err(e) = super::commands::save_speed(app, speed.learn(cpu, audio_secs, retry_started.elapsed().as_secs_f64())) {
                warn!("Could not save separation speed: {}", e);
            }
            diarization
        }
        Err(e) => return Err(e.context("separating speakers")),
    };

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
    let matches = match_profiles(&voice_embeddings, &profiles, PROFILE_MATCH_THRESHOLD, PROFILE_MATCH_MARGIN);

    let auto_named = matches.iter().filter(|m| m.is_some()).count();
    let voices: Vec<DiarizedVoice> = voice_embeddings
        .into_iter()
        .zip(matches)
        .enumerate()
        .map(|(index, (embedding, profile_id))| DiarizedVoice {
            label: SpeakerLabel::Speaker(index as u32),
            profile_id,
            embedding,
            sample: longest_turn(&turns, attribution.label_clusters[index]),
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

fn epoch_ms() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map_or(0, |d| d.as_millis() as u64)
}

fn skipped(reason: &str) -> DiarizationOutcome {
    DiarizationOutcome::Skipped { reason: reason.to_string() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn folder_with(metadata: &str, files: &[&str]) -> tempfile::TempDir {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join(FOLDER_METADATA_FILE), metadata).unwrap();
        for file in files {
            std::fs::write(dir.path().join(file), b"audio").unwrap();
        }
        dir
    }

    #[test]
    fn an_imported_file_is_the_meeting_audio() {
        let dir = folder_with(r#"{"source": "import", "audio_file": "audio.m4a"}"#, &["audio.m4a"]);
        assert_eq!(imported_audio(dir.path()), Some(dir.path().join("audio.m4a")));
    }

    #[test]
    fn a_recording_or_a_missing_file_is_not() {
        // A recording's audio.mp4 mixes in the user's microphone, so it never stands in for the system track.
        let recorded = folder_with(r#"{"source": "recording", "audio_file": "audio.mp4"}"#, &["audio.mp4"]);
        assert_eq!(imported_audio(recorded.path()), None);
        let missing = folder_with(r#"{"source": "import", "audio_file": "audio.m4a"}"#, &[]);
        assert_eq!(imported_audio(missing.path()), None);
        let broken = folder_with("not json", &["audio.m4a"]);
        assert_eq!(imported_audio(broken.path()), None);
    }
}
