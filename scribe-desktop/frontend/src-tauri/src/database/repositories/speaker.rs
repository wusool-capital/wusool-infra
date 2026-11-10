// database/repositories/speaker.rs
//
// Persistence for the voice library (speaker_profiles) and per-meeting speaker maps
// (meeting_speakers). Embeddings are stored as little-endian f32 BLOBs.

use chrono::Utc;
use serde::{Deserialize, Serialize};
use sqlx::{Connection, FromRow, Sqlite, SqlitePool, Transaction};
use uuid::Uuid;

use crate::diarization::assign::mean_embedding;
use crate::diarization::overview::NamedProfile;
use crate::diarization::SpeakerLabel;

/// A named voice, as listed in settings.
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct SpeakerProfileSummary {
    pub id: String,
    pub name: String,
    pub sample_count: i64,
}

#[derive(Debug, Clone)]
pub struct StoredProfile {
    pub id: String,
    pub embedding: Vec<f32>,
}

/// One diarized voice in a meeting and the person it was matched or named as.
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct MeetingSpeaker {
    pub label: SpeakerLabel,
    pub profile_id: Option<String>,
    pub name: Option<String>,
}

/// A voice found by diarization, ready to be stored for a meeting.
pub struct DiarizedVoice {
    pub label: SpeakerLabel,
    pub profile_id: Option<String>,
    pub embedding: Vec<f32>,
}

/// A transcript segment of meeting audio that diarization can attribute.
#[derive(Debug, Clone, FromRow)]
pub struct AttributableSegment {
    pub id: String,
    pub audio_start_time: f64,
    pub audio_end_time: f64,
}

/// A diarized voice's share of a meeting, with one line to recognise it by.
#[derive(Debug, Clone)]
pub struct VoiceOverviewRow {
    pub label: SpeakerLabel,
    pub profile_id: Option<String>,
    pub name: Option<String>,
    pub embedding: Vec<f32>,
    pub auto_named: bool,
    pub line_count: i64,
    pub talk_seconds: f64,
    pub sample: Option<VoiceSample>,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct VoiceSample {
    pub segment_id: String,
    pub text: String,
    pub start: f64,
    pub end: f64,
}

#[derive(FromRow)]
struct VoiceStatsRow {
    label: SpeakerLabel,
    line_count: i64,
    talk_seconds: f64,
}

#[derive(FromRow)]
struct VoiceSampleRow {
    label: SpeakerLabel,
    #[sqlx(flatten)]
    sample: VoiceSample,
}

#[derive(FromRow)]
struct StoredVoiceRow {
    label: SpeakerLabel,
    profile_id: Option<String>,
    name: Option<String>,
    embedding: Vec<u8>,
    auto_named: bool,
}

/// Where the user moves transcript lines: a voice already in the meeting (or "me"), or a new one.
#[derive(Debug, Clone, Copy, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum SpeakerTarget {
    Existing { label: SpeakerLabel },
    New,
}

#[derive(Debug, thiserror::Error)]
pub enum SpeakerRepositoryError {
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error("{0} has no stored voice in this meeting")]
    UnknownLabel(SpeakerLabel),
    #[error("These voices have changed since they were combined, so they can't be separated again")]
    MergeChanged,
}

/// Everything a merge changed, so the UI can offer Undo.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SpeakerMerge {
    pub kept: SpeakerLabel,
    pub kept_embedding: Vec<f32>,
    /// The kept voice's print right after this merge; any other value means a later change.
    pub kept_embedding_after: Vec<f32>,
    pub kept_auto_named: bool,
    pub merged: SpeakerLabel,
    pub merged_embedding: Vec<f32>,
    /// The person the merged voice was linked to before it was named, if any.
    pub merged_profile_id: Option<String>,
    pub merged_auto_named: bool,
    pub segment_ids: Vec<String>,
}

/// The voice's label after naming, and the merge it caused, if it joined another voice.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct NamedSpeaker {
    pub label: SpeakerLabel,
    pub merge: Option<SpeakerMerge>,
}

/// The voice being named, as it was before naming changed it.
struct VoiceBefore {
    label: SpeakerLabel,
    embedding: Vec<u8>,
    profile_id: Option<String>,
    auto_named: bool,
}

// Each voice's longest line: the most speech from one person, so the clip that best represents the voice.
const VOICE_SAMPLES_SQL: &str = "WITH ranked AS (
        SELECT id, speaker, transcript, audio_start_time, audio_end_time,
               ROW_NUMBER() OVER (
                   PARTITION BY speaker ORDER BY audio_end_time - audio_start_time DESC, audio_start_time
               ) AS rank
        FROM transcripts
        WHERE meeting_id = ? AND audio_start_time IS NOT NULL AND audio_end_time IS NOT NULL
          AND speaker LIKE 'speaker\\_%' ESCAPE '\\'
     ), samples AS (
        SELECT speaker AS label, id AS segment_id, transcript AS text,
               audio_start_time AS start, audio_end_time AS end
        FROM ranked WHERE rank = 1
     )";

pub struct SpeakerRepository;

impl SpeakerRepository {
    pub async fn list_profiles(pool: &SqlitePool) -> Result<Vec<SpeakerProfileSummary>, sqlx::Error> {
        sqlx::query_as("SELECT id, name, sample_count FROM speaker_profiles ORDER BY name")
            .fetch_all(pool)
            .await
    }

    pub async fn profile_embeddings(pool: &SqlitePool) -> Result<Vec<StoredProfile>, sqlx::Error> {
        let rows: Vec<(String, Vec<u8>)> = sqlx::query_as("SELECT id, embedding FROM speaker_profiles")
            .fetch_all(pool)
            .await?;
        Ok(rows
            .into_iter()
            .map(|(id, blob)| StoredProfile { id, embedding: decode_embedding(&blob) })
            .collect())
    }

    pub async fn named_profiles(pool: &SqlitePool) -> Result<Vec<NamedProfile>, sqlx::Error> {
        let rows: Vec<(String, String, Vec<u8>)> = sqlx::query_as("SELECT id, name, embedding FROM speaker_profiles")
            .fetch_all(pool)
            .await?;
        Ok(rows
            .into_iter()
            .map(|(id, name, blob)| NamedProfile { id, name, embedding: decode_embedding(&blob) })
            .collect())
    }

    pub async fn delete_profile(pool: &SqlitePool, profile_id: &str) -> Result<(), sqlx::Error> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;
        sqlx::query("UPDATE meeting_speakers SET profile_id = NULL WHERE profile_id = ?")
            .bind(profile_id)
            .execute(&mut *tx)
            .await?;
        sqlx::query("DELETE FROM speaker_profiles WHERE id = ?")
            .bind(profile_id)
            .execute(&mut *tx)
            .await?;
        tx.commit().await
    }

    pub async fn meeting_speakers(
        pool: &SqlitePool,
        meeting_id: &str,
    ) -> Result<Vec<MeetingSpeaker>, sqlx::Error> {
        sqlx::query_as(
            "SELECT ms.label, ms.profile_id, sp.name
             FROM meeting_speakers ms
             LEFT JOIN speaker_profiles sp ON sp.id = ms.profile_id
             WHERE ms.meeting_id = ?
             ORDER BY ms.label",
        )
        .bind(meeting_id)
        .fetch_all(pool)
        .await
    }

    /// Every diarized voice in a meeting with its talk time and a sample line.
    pub async fn voice_overview(pool: &SqlitePool, meeting_id: &str) -> Result<Vec<VoiceOverviewRow>, sqlx::Error> {
        let voices: Vec<StoredVoiceRow> = sqlx::query_as(
            "SELECT ms.label, ms.profile_id, sp.name, ms.embedding, ms.auto_named
             FROM meeting_speakers ms
             LEFT JOIN speaker_profiles sp ON sp.id = ms.profile_id
             WHERE ms.meeting_id = ?",
        )
        .bind(meeting_id)
        .fetch_all(pool)
        .await?;
        let stats: Vec<VoiceStatsRow> = sqlx::query_as(
            "SELECT speaker AS label, COUNT(*) AS line_count,
                    COALESCE(SUM(audio_end_time - audio_start_time), 0.0) AS talk_seconds
             FROM transcripts
             WHERE meeting_id = ? AND audio_start_time IS NOT NULL AND audio_end_time IS NOT NULL
               AND speaker LIKE 'speaker\\_%' ESCAPE '\\'
             GROUP BY speaker",
        )
        .bind(meeting_id)
        .fetch_all(pool)
        .await?;
        let samples: Vec<VoiceSampleRow> = sqlx::query_as(&format!("{VOICE_SAMPLES_SQL} SELECT * FROM samples"))
            .bind(meeting_id)
        .fetch_all(pool)
        .await?;

        // A voice whose lines were all deleted or reassigned no longer needs a name.
        Ok(voices
            .into_iter()
            .filter_map(|voice| {
                let stat = stats.iter().find(|s| s.label == voice.label)?;
                Some(VoiceOverviewRow {
                    label: voice.label,
                    profile_id: voice.profile_id,
                    name: voice.name,
                    embedding: decode_embedding(&voice.embedding),
                    auto_named: voice.auto_named,
                    line_count: stat.line_count,
                    talk_seconds: stat.talk_seconds,
                    sample: samples.iter().find(|s| s.label == voice.label).map(|s| s.sample.clone()),
                })
            })
            .collect())
    }

    /// One voice's sample line, for cutting its playback clip.
    pub async fn voice_sample(
        pool: &SqlitePool,
        meeting_id: &str,
        label: SpeakerLabel,
    ) -> Result<Option<VoiceSample>, sqlx::Error> {
        let row: Option<VoiceSampleRow> =
            sqlx::query_as(&format!("{VOICE_SAMPLES_SQL} SELECT * FROM samples WHERE label = ?"))
                .bind(meeting_id)
                .bind(label)
                .fetch_optional(pool)
                .await?;
        Ok(row.map(|r| r.sample))
    }

    /// Meeting-audio segments: never diarized ("others"), or diarized before and being re-run.
    pub async fn attributable_segments(
        pool: &SqlitePool,
        meeting_id: &str,
    ) -> Result<Vec<AttributableSegment>, sqlx::Error> {
        sqlx::query_as(
            "SELECT id, audio_start_time, audio_end_time FROM transcripts
             WHERE meeting_id = ?
               AND audio_start_time IS NOT NULL AND audio_end_time IS NOT NULL
               AND (speaker = 'others' OR speaker LIKE 'speaker\\_%' ESCAPE '\\')",
        )
        .bind(meeting_id)
        .fetch_all(pool)
        .await
    }

    /// Moves lines to another speaker. A new speaker has no voice print, since diarization never heard it apart.
    pub async fn reassign_segments(
        pool: &SqlitePool,
        meeting_id: &str,
        segment_ids: &[String],
        target: SpeakerTarget,
    ) -> Result<SpeakerLabel, SpeakerRepositoryError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let label = match target {
            SpeakerTarget::Existing { label: label @ SpeakerLabel::Speaker(_) } => {
                let known: Option<(i64,)> =
                    sqlx::query_as("SELECT 1 FROM meeting_speakers WHERE meeting_id = ? AND label = ?")
                        .bind(meeting_id)
                        .bind(label)
                        .fetch_optional(&mut *tx)
                        .await?;
                known.ok_or(SpeakerRepositoryError::UnknownLabel(label))?;
                label
            }
            SpeakerTarget::Existing { label } => label,
            SpeakerTarget::New => {
                let used: Vec<(SpeakerLabel,)> = sqlx::query_as(
                    "SELECT label FROM meeting_speakers WHERE meeting_id = ?
                     UNION SELECT speaker FROM transcripts
                     WHERE meeting_id = ? AND speaker LIKE 'speaker\\_%' ESCAPE '\\'",
                )
                .bind(meeting_id)
                .bind(meeting_id)
                .fetch_all(&mut *tx)
                .await?;
                let next = used
                    .iter()
                    .filter_map(|(l,)| match l {
                        SpeakerLabel::Speaker(n) => Some(n + 1),
                        _ => None,
                    })
                    .max()
                    .unwrap_or(0);
                let label = SpeakerLabel::Speaker(next);
                sqlx::query(
                    "INSERT INTO meeting_speakers (meeting_id, label, profile_id, embedding, auto_named)
                     VALUES (?, ?, NULL, x'', 0)",
                )
                .bind(meeting_id)
                .bind(label)
                .execute(&mut *tx)
                .await?;
                label
            }
        };

        for segment_id in segment_ids {
            sqlx::query("UPDATE transcripts SET speaker = ? WHERE id = ? AND meeting_id = ?")
                .bind(label)
                .bind(segment_id)
                .bind(meeting_id)
                .execute(&mut *tx)
                .await?;
        }
        tx.commit().await?;
        Ok(label)
    }

    /// Replaces a meeting's diarization result atomically, so a failed run never leaves
    /// segments pointing at speakers that were not stored.
    pub async fn save_diarization(
        pool: &SqlitePool,
        meeting_id: &str,
        voices: &[DiarizedVoice],
        segment_labels: &[(String, SpeakerLabel)],
    ) -> Result<(), sqlx::Error> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let previous: Vec<(String,)> = sqlx::query_as(
            "SELECT DISTINCT profile_id FROM meeting_speakers WHERE meeting_id = ? AND profile_id IS NOT NULL",
        )
        .bind(meeting_id)
        .fetch_all(&mut *tx)
        .await?;

        sqlx::query("DELETE FROM meeting_speakers WHERE meeting_id = ?")
            .bind(meeting_id)
            .execute(&mut *tx)
            .await?;
        for voice in voices {
            sqlx::query(
                "INSERT INTO meeting_speakers (meeting_id, label, profile_id, embedding, auto_named)
                 VALUES (?, ?, ?, ?, ?)",
            )
            .bind(meeting_id)
            .bind(voice.label)
            .bind(&voice.profile_id)
            .bind(encode_embedding(&voice.embedding))
            .bind(voice.profile_id.is_some())
            .execute(&mut *tx)
            .await?;
        }
        for (segment_id, label) in segment_labels {
            sqlx::query("UPDATE transcripts SET speaker = ? WHERE id = ? AND meeting_id = ?")
                .bind(label)
                .bind(segment_id)
                .bind(meeting_id)
                .execute(&mut *tx)
                .await?;
        }

        let mut touched: Vec<String> = previous.into_iter().map(|(id,)| id).collect();
        touched.extend(voices.iter().filter_map(|v| v.profile_id.clone()));
        touched.sort();
        touched.dedup();
        for profile_id in &touched {
            recompute_profile(&mut tx, profile_id).await?;
        }

        tx.commit().await
    }

    /// Links a meeting's voice to the named person, recomputing profiles so renaming never double-counts.
    /// Naming a voice after someone another voice in the meeting already is merges the two.
    pub async fn name_meeting_speaker(
        pool: &SqlitePool,
        meeting_id: &str,
        label: SpeakerLabel,
        name: &str,
    ) -> Result<NamedSpeaker, SpeakerRepositoryError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let voice: Option<(Vec<u8>, Option<String>, bool)> = sqlx::query_as(
            "SELECT embedding, profile_id, auto_named FROM meeting_speakers WHERE meeting_id = ? AND label = ?",
        )
        .bind(meeting_id)
        .bind(label)
        .fetch_optional(&mut *tx)
        .await?;
        let (voice_blob, previous_profile, auto_named) = voice.ok_or(SpeakerRepositoryError::UnknownLabel(label))?;
        let before = VoiceBefore { label, embedding: voice_blob.clone(), profile_id: previous_profile.clone(), auto_named };

        let existing: Option<(String,)> =
            sqlx::query_as("SELECT id FROM speaker_profiles WHERE name = ? COLLATE NOCASE")
                .bind(name)
                .fetch_optional(&mut *tx)
                .await?;

        let profile_id = match existing {
            Some((id,)) if previous_profile.as_deref() == Some(id.as_str()) => {
                // Already this person: the user has now confirmed it, nothing to re-learn.
                sqlx::query("UPDATE meeting_speakers SET auto_named = 0 WHERE meeting_id = ? AND label = ?")
                    .bind(meeting_id)
                    .bind(label)
                    .execute(&mut *tx)
                    .await?;
                // Still merges, so older duplicate voices are tidied by renaming them, one per rename.
                let merge = merge_into_same_person(&mut tx, meeting_id, &before, &id).await?;
                tx.commit().await?;
                return Ok(named(label, merge));
            }
            Some((id,)) => id,
            None => {
                let id = format!("speaker-{}", Uuid::new_v4());
                let now = Utc::now().to_rfc3339();
                sqlx::query(
                    "INSERT INTO speaker_profiles (id, name, embedding, sample_count, created_at, updated_at)
                     VALUES (?, ?, ?, 0, ?, ?)",
                )
                .bind(&id)
                .bind(name)
                .bind(&voice_blob)
                .bind(&now)
                .bind(&now)
                .execute(&mut *tx)
                .await?;
                id
            }
        };

        sqlx::query("UPDATE meeting_speakers SET profile_id = ?, auto_named = 0 WHERE meeting_id = ? AND label = ?")
            .bind(&profile_id)
            .bind(meeting_id)
            .bind(label)
            .execute(&mut *tx)
            .await?;

        let merge = merge_into_same_person(&mut tx, meeting_id, &before, &profile_id).await?;
        // A merge has already recomputed this profile.
        if merge.is_none() {
            recompute_profile(&mut tx, &profile_id).await?;
        }
        if let Some(previous) = previous_profile {
            recompute_profile(&mut tx, &previous).await?;
        }

        tx.commit().await?;
        Ok(named(label, merge))
    }

    /// Splits a merged voice back out, exactly as it was before it was named.
    pub async fn undo_merge(pool: &SqlitePool, meeting_id: &str, merge: &SpeakerMerge) -> Result<(), SpeakerRepositoryError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let kept: Option<(Option<String>, Vec<u8>)> =
            sqlx::query_as("SELECT profile_id, embedding FROM meeting_speakers WHERE meeting_id = ? AND label = ?")
                .bind(meeting_id)
                .bind(merge.kept)
                .fetch_optional(&mut *tx)
                .await?;
        let merged_back: Option<(i64,)> = sqlx::query_as("SELECT 1 FROM meeting_speakers WHERE meeting_id = ? AND label = ?")
            .bind(meeting_id)
            .bind(merge.merged)
            .fetch_optional(&mut *tx)
            .await?;
        // A re-run separation or another merge since makes the snapshot stale; restoring it would scramble voices.
        let (Some((kept_profile, kept_blob)), None) = (kept, merged_back) else {
            return Err(SpeakerRepositoryError::MergeChanged);
        };
        if decode_embedding(&kept_blob) != merge.kept_embedding_after {
            return Err(SpeakerRepositoryError::MergeChanged);
        }

        sqlx::query("UPDATE meeting_speakers SET embedding = ?, auto_named = ? WHERE meeting_id = ? AND label = ?")
            .bind(encode_embedding(&merge.kept_embedding))
            .bind(merge.kept_auto_named)
            .bind(meeting_id)
            .bind(merge.kept)
            .execute(&mut *tx)
            .await?;
        sqlx::query(
            "INSERT INTO meeting_speakers (meeting_id, label, profile_id, embedding, auto_named) VALUES (?, ?, ?, ?, ?)",
        )
        .bind(meeting_id)
        .bind(merge.merged)
        .bind(&merge.merged_profile_id)
        .bind(encode_embedding(&merge.merged_embedding))
        .bind(merge.merged_auto_named)
        .execute(&mut *tx)
        .await?;
        // Only lines still on the kept voice: one the user has since moved elsewhere stays where they put it.
        for segment_id in &merge.segment_ids {
            sqlx::query("UPDATE transcripts SET speaker = ? WHERE id = ? AND meeting_id = ? AND speaker = ?")
                .bind(merge.merged)
                .bind(segment_id)
                .bind(meeting_id)
                .bind(merge.kept)
                .execute(&mut *tx)
                .await?;
        }

        let mut touched: Vec<String> = kept_profile.into_iter().chain(merge.merged_profile_id.clone()).collect();
        touched.dedup();
        for profile_id in &touched {
            recompute_profile(&mut tx, profile_id).await?;
        }
        tx.commit().await?;
        Ok(())
    }
}

fn named(label: SpeakerLabel, merge: Option<SpeakerMerge>) -> NamedSpeaker {
    NamedSpeaker { label: merge.as_ref().map_or(label, |m| m.kept), merge }
}

/// Folds a voice into another of the meeting's voices already named as the same person,
/// since diarization sometimes splits one person in two. Returns the voice it joined.
async fn merge_into_same_person(
    tx: &mut Transaction<'_, Sqlite>,
    meeting_id: &str,
    before: &VoiceBefore,
    profile_id: &str,
) -> Result<Option<SpeakerMerge>, sqlx::Error> {
    let label = before.label;
    let other: Option<(SpeakerLabel, Vec<u8>, bool)> = sqlx::query_as(
        "SELECT label, embedding, auto_named FROM meeting_speakers
         WHERE meeting_id = ? AND profile_id = ? AND label != ? LIMIT 1",
    )
    .bind(meeting_id)
    .bind(profile_id)
    .bind(label)
    .fetch_optional(&mut **tx)
    .await?;
    let Some((keep, keep_blob, keep_auto_named)) = other else {
        return Ok(None);
    };
    let moved: Vec<(String,)> = sqlx::query_as("SELECT id FROM transcripts WHERE meeting_id = ? AND speaker = ?")
        .bind(meeting_id)
        .bind(label)
        .fetch_all(&mut **tx)
        .await?;
    // Both halves' voice prints stay in the kept voice, so the person's profile still learns from each.
    let combined = mean_embedding(&[decode_embedding(&keep_blob), decode_embedding(&before.embedding)]);
    let snapshot = SpeakerMerge {
        kept: keep,
        kept_embedding: decode_embedding(&keep_blob),
        kept_embedding_after: combined.clone().unwrap_or_else(|| decode_embedding(&keep_blob)),
        kept_auto_named: keep_auto_named,
        merged: label,
        merged_embedding: decode_embedding(&before.embedding),
        merged_profile_id: before.profile_id.clone(),
        merged_auto_named: before.auto_named,
        segment_ids: moved.into_iter().map(|(id,)| id).collect(),
    };

    if let Some(mean) = combined {
        sqlx::query("UPDATE meeting_speakers SET embedding = ? WHERE meeting_id = ? AND label = ?")
            .bind(encode_embedding(&mean))
            .bind(meeting_id)
            .bind(keep)
            .execute(&mut **tx)
            .await?;
    }
    sqlx::query("UPDATE meeting_speakers SET auto_named = 0 WHERE meeting_id = ? AND label = ?")
        .bind(meeting_id)
        .bind(keep)
        .execute(&mut **tx)
        .await?;
    sqlx::query("UPDATE transcripts SET speaker = ? WHERE meeting_id = ? AND speaker = ?")
        .bind(keep)
        .bind(meeting_id)
        .bind(label)
        .execute(&mut **tx)
        .await?;
    sqlx::query("DELETE FROM meeting_speakers WHERE meeting_id = ? AND label = ?")
        .bind(meeting_id)
        .bind(label)
        .execute(&mut **tx)
        .await?;
    recompute_profile(tx, profile_id).await?;
    Ok(Some(snapshot))
}

/// Rebuilds a profile from its linked voices, keeping the stored embedding when none remain.
async fn recompute_profile(tx: &mut Transaction<'_, Sqlite>, profile_id: &str) -> Result<(), sqlx::Error> {
    let blobs: Vec<(Vec<u8>,)> = sqlx::query_as("SELECT embedding FROM meeting_speakers WHERE profile_id = ?")
        .bind(profile_id)
        .fetch_all(&mut **tx)
        .await?;
    let samples: Vec<Vec<f32>> = blobs.iter().map(|(b,)| decode_embedding(b)).collect();
    let usable = samples.iter().filter(|s| !s.is_empty()).count() as i64;
    let now = Utc::now().to_rfc3339();

    match mean_embedding(&samples) {
        Some(mean) => {
            sqlx::query("UPDATE speaker_profiles SET embedding = ?, sample_count = ?, updated_at = ? WHERE id = ?")
                .bind(encode_embedding(&mean))
                .bind(usable)
                .bind(&now)
                .bind(profile_id)
                .execute(&mut **tx)
                .await?;
        }
        None => {
            sqlx::query("UPDATE speaker_profiles SET sample_count = ?, updated_at = ? WHERE id = ?")
                .bind(usable)
                .bind(&now)
                .bind(profile_id)
                .execute(&mut **tx)
                .await?;
        }
    }
    Ok(())
}

fn encode_embedding(embedding: &[f32]) -> Vec<u8> {
    embedding.iter().flat_map(|x| x.to_le_bytes()).collect()
}

fn decode_embedding(blob: &[u8]) -> Vec<f32> {
    blob.chunks_exact(4)
        .map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use sqlx::sqlite::SqlitePoolOptions;

    const MEETING: &str = "meeting-1";

    async fn pool_with_meeting() -> SqlitePool {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::migrate!("./migrations").run(&pool).await.unwrap();
        sqlx::query("INSERT INTO meetings (id, title, created_at, updated_at) VALUES (?, 't', 'now', 'now')")
            .bind(MEETING)
            .execute(&pool)
            .await
            .unwrap();
        for (id, speaker, start) in [("t-me", "me", 0.0), ("t-1", "others", 1.0), ("t-2", "others", 5.0)] {
            sqlx::query(
                "INSERT INTO transcripts (id, meeting_id, transcript, timestamp, audio_start_time, audio_end_time, duration, speaker)
                 VALUES (?, ?, 'text', 'ts', ?, ?, 1.0, ?)",
            )
            .bind(id)
            .bind(MEETING)
            .bind(start)
            .bind(start + 1.0)
            .bind(speaker)
            .execute(&pool)
            .await
            .unwrap();
        }
        pool
    }

    fn voice(label: u32, embedding: Vec<f32>) -> DiarizedVoice {
        DiarizedVoice { label: SpeakerLabel::Speaker(label), profile_id: None, embedding }
    }

    #[tokio::test]
    async fn only_meeting_audio_segments_are_attributable() {
        let pool = pool_with_meeting().await;
        let ids: Vec<String> = SpeakerRepository::attributable_segments(&pool, MEETING)
            .await
            .unwrap()
            .into_iter()
            .map(|s| s.id)
            .collect();
        assert_eq!(ids, vec!["t-1", "t-2"]);
    }

    #[tokio::test]
    async fn save_diarization_labels_segments_and_stays_rerunnable() {
        let pool = pool_with_meeting().await;
        let labels = vec![
            ("t-1".to_string(), SpeakerLabel::Speaker(0)),
            ("t-2".to_string(), SpeakerLabel::Speaker(1)),
        ];
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &labels)
            .await
            .unwrap();

        let speakers = SpeakerRepository::meeting_speakers(&pool, MEETING).await.unwrap();
        assert_eq!(speakers.len(), 2);
        // Diarized rows must still be picked up by a re-run.
        assert_eq!(SpeakerRepository::attributable_segments(&pool, MEETING).await.unwrap().len(), 2);
    }

    #[tokio::test]
    async fn auto_named_voices_are_marked_until_the_user_confirms_them() {
        let pool = pool_with_meeting().await;
        let labels = vec![("t-1".to_string(), SpeakerLabel::Speaker(0))];
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0])], &labels)
            .await
            .unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice")
            .await
            .unwrap();
        let alice = SpeakerRepository::list_profiles(&pool).await.unwrap().remove(0).id;

        // A re-run where the voice library recognises Alice on its own.
        let recognised = DiarizedVoice { profile_id: Some(alice), ..voice(0, vec![1.0, 0.0]) };
        SpeakerRepository::save_diarization(&pool, MEETING, &[recognised], &labels).await.unwrap();
        let auto = |pool: SqlitePool| async move {
            SpeakerRepository::voice_overview(&pool, MEETING).await.unwrap()[0].auto_named
        };
        assert!(auto(pool.clone()).await);

        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice")
            .await
            .unwrap();
        assert!(!auto(pool.clone()).await);
    }

    #[tokio::test]
    async fn voice_overview_counts_talk_time_and_picks_the_longest_line() {
        let pool = pool_with_meeting().await;
        sqlx::query(
            "INSERT INTO transcripts (id, meeting_id, transcript, timestamp, audio_start_time, audio_end_time, duration, speaker)
             VALUES ('t-3', ?, 'a much longer line', 'ts', 10.0, 14.0, 4.0, 'others')",
        )
        .bind(MEETING)
        .execute(&pool)
        .await
        .unwrap();
        let labels = vec![
            ("t-1".to_string(), SpeakerLabel::Speaker(0)),
            ("t-2".to_string(), SpeakerLabel::Speaker(1)),
            ("t-3".to_string(), SpeakerLabel::Speaker(0)),
        ];
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &labels)
            .await
            .unwrap();

        let overview = SpeakerRepository::voice_overview(&pool, MEETING).await.unwrap();
        let first = overview.iter().find(|v| v.label == SpeakerLabel::Speaker(0)).unwrap();
        assert_eq!(first.line_count, 2);
        assert!((first.talk_seconds - 5.0).abs() < 1e-9);
        assert_eq!(first.sample.as_ref().unwrap().segment_id, "t-3");
        assert_eq!(first.embedding, vec![1.0, 0.0]);
        let second = overview.iter().find(|v| v.label == SpeakerLabel::Speaker(1)).unwrap();
        assert_eq!(second.line_count, 1);

        let clip = SpeakerRepository::voice_sample(&pool, MEETING, SpeakerLabel::Speaker(0)).await.unwrap();
        assert_eq!(clip.unwrap().segment_id, "t-3");

        // Once a voice has no lines left it drops out, so nobody is asked to name it.
        sqlx::query("DELETE FROM transcripts WHERE id = 't-2'").execute(&pool).await.unwrap();
        let overview = SpeakerRepository::voice_overview(&pool, MEETING).await.unwrap();
        assert!(overview.iter().all(|v| v.label != SpeakerLabel::Speaker(1)));
        assert!(SpeakerRepository::voice_sample(&pool, MEETING, SpeakerLabel::Speaker(1)).await.unwrap().is_none());
    }

    #[tokio::test]
    async fn naming_enrols_then_refines_a_profile() {
        let pool = pool_with_meeting().await;
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &[])
            .await
            .unwrap();

        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice").await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "alice").await.unwrap();

        let profiles = SpeakerRepository::list_profiles(&pool).await.unwrap();
        assert_eq!(profiles.len(), 1, "same name, any case, is the same person");
        assert_eq!(profiles[0].sample_count, 1, "one merged voice for this meeting");
        let embedding = &SpeakerRepository::profile_embeddings(&pool).await.unwrap()[0].embedding;
        assert_eq!(embedding, &vec![0.5, 0.5], "both halves still teach the profile");
    }

    async fn speakers_of(pool: &SqlitePool) -> Vec<(String, String)> {
        sqlx::query_as("SELECT id, speaker FROM transcripts WHERE meeting_id = ? ORDER BY id")
            .bind(MEETING)
            .fetch_all(pool)
            .await
            .unwrap()
    }

    #[tokio::test]
    async fn naming_a_second_voice_as_the_same_person_merges_it() {
        let pool = pool_with_meeting().await;
        let labels = [("t-1".to_string(), SpeakerLabel::Speaker(0)), ("t-2".to_string(), SpeakerLabel::Speaker(1))];
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &labels)
            .await
            .unwrap();

        let first = SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Saleeq").await.unwrap();
        assert_eq!(first, NamedSpeaker { label: SpeakerLabel::Speaker(0), merge: None });
        let second = SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Saleeq").await.unwrap();
        assert_eq!(second.label, SpeakerLabel::Speaker(0), "joins the voice already named Saleeq");
        assert_eq!(second.merge.unwrap().segment_ids, vec!["t-2".to_string()]);

        let speakers = SpeakerRepository::meeting_speakers(&pool, MEETING).await.unwrap();
        assert_eq!(speakers.len(), 1);
        let lines = speakers_of(&pool).await;
        assert!(lines.iter().filter(|(id, _)| id != "t-me").all(|(_, s)| s == "speaker_0"));
        let overview = SpeakerRepository::voice_overview(&pool, MEETING).await.unwrap();
        assert_eq!(overview.len(), 1);
        assert_eq!(overview[0].line_count, 2);
    }

    #[tokio::test]
    async fn renaming_an_already_duplicated_voice_merges_it() {
        let pool = pool_with_meeting().await;
        let labels = [("t-1".to_string(), SpeakerLabel::Speaker(0)), ("t-2".to_string(), SpeakerLabel::Speaker(1))];
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &labels)
            .await
            .unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Saleeq").await.unwrap();
        // Two rows linked to one person, as meetings named before merging existed were left.
        sqlx::query("UPDATE meeting_speakers SET profile_id = (SELECT id FROM speaker_profiles) WHERE label = 'speaker_1'")
            .execute(&pool)
            .await
            .unwrap();

        let kept = SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Saleeq").await.unwrap();
        assert_eq!(kept.label, SpeakerLabel::Speaker(0));
        assert_eq!(SpeakerRepository::meeting_speakers(&pool, MEETING).await.unwrap().len(), 1);
    }

    #[tokio::test]
    async fn naming_the_same_voice_twice_does_not_double_count() {
        let pool = pool_with_meeting().await;
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0])], &[]).await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice").await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice").await.unwrap();
        assert_eq!(SpeakerRepository::list_profiles(&pool).await.unwrap()[0].sample_count, 1);
    }

    #[tokio::test]
    async fn correcting_a_name_moves_the_voice_between_profiles() {
        let pool = pool_with_meeting().await;
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &[])
            .await
            .unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Bob").await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Alice").await.unwrap();
        // speaker_0 was really Alice.
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice").await.unwrap();

        let profiles = SpeakerRepository::list_profiles(&pool).await.unwrap();
        let count = |name: &str| profiles.iter().find(|p| p.name == name).unwrap().sample_count;
        assert_eq!(count("Alice"), 1, "both voices are now Alice, merged into one");
        assert_eq!(count("Bob"), 0);
    }

    async fn two_voices_one_named_saleeq(pool: &SqlitePool) {
        let labels = [("t-1".to_string(), SpeakerLabel::Speaker(0)), ("t-2".to_string(), SpeakerLabel::Speaker(1))];
        SpeakerRepository::save_diarization(pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &labels)
            .await
            .unwrap();
        SpeakerRepository::name_meeting_speaker(pool, MEETING, SpeakerLabel::Speaker(0), "Saleeq").await.unwrap();
    }

    #[tokio::test]
    async fn undoing_a_merge_restores_both_voices_exactly() {
        let pool = pool_with_meeting().await;
        two_voices_one_named_saleeq(&pool).await;
        let speakers_before = SpeakerRepository::meeting_speakers(&pool, MEETING).await.unwrap();
        let lines_before = speakers_of(&pool).await;
        let profile_before = SpeakerRepository::profile_embeddings(&pool).await.unwrap()[0].embedding.clone();

        let named = SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Saleeq").await.unwrap();
        SpeakerRepository::undo_merge(&pool, MEETING, &named.merge.unwrap()).await.unwrap();

        assert_eq!(SpeakerRepository::meeting_speakers(&pool, MEETING).await.unwrap().len(), speakers_before.len());
        assert_eq!(speakers_of(&pool).await, lines_before);
        assert_eq!(SpeakerRepository::profile_embeddings(&pool).await.unwrap()[0].embedding, profile_before);
        let unnamed = SpeakerRepository::meeting_speakers(&pool, MEETING).await.unwrap();
        assert!(unnamed.iter().any(|s| s.label == SpeakerLabel::Speaker(1) && s.name.is_none()));
    }

    #[tokio::test]
    async fn undo_brings_back_an_earlier_automatic_name() {
        let pool = pool_with_meeting().await;
        two_voices_one_named_saleeq(&pool).await;
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Bob").await.unwrap();
        sqlx::query("UPDATE meeting_speakers SET auto_named = 1 WHERE label = 'speaker_1'").execute(&pool).await.unwrap();

        let named = SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Saleeq").await.unwrap();
        SpeakerRepository::undo_merge(&pool, MEETING, &named.merge.unwrap()).await.unwrap();

        let (name, auto_named): (Option<String>, bool) = sqlx::query_as(
            "SELECT p.name, s.auto_named FROM meeting_speakers s LEFT JOIN speaker_profiles p ON p.id = s.profile_id
             WHERE s.label = 'speaker_1'",
        )
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!((name.as_deref(), auto_named), (Some("Bob"), true));
    }

    #[tokio::test]
    async fn a_stale_undo_changes_nothing() {
        let pool = pool_with_meeting().await;
        two_voices_one_named_saleeq(&pool).await;
        let named = SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Saleeq").await.unwrap();
        // Separating speakers again brings speaker_1 back on its own.
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &[])
            .await
            .unwrap();

        let result = SpeakerRepository::undo_merge(&pool, MEETING, &named.merge.unwrap()).await;
        assert!(matches!(result, Err(SpeakerRepositoryError::MergeChanged)));
        assert_eq!(SpeakerRepository::meeting_speakers(&pool, MEETING).await.unwrap().len(), 2);
    }

    #[tokio::test]
    async fn undoing_an_earlier_merge_after_a_later_one_is_refused() {
        let pool = pool_with_meeting().await;
        two_voices_one_named_saleeq(&pool).await;
        sqlx::query("INSERT INTO meeting_speakers (meeting_id, label, profile_id, embedding, auto_named) VALUES (?, 'speaker_2', NULL, ?, 0)")
            .bind(MEETING)
            .bind(encode_embedding(&[1.0, 1.0]))
            .execute(&pool)
            .await
            .unwrap();
        let first = SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Saleeq").await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(2), "Saleeq").await.unwrap();
        let print_before = SpeakerRepository::profile_embeddings(&pool).await.unwrap()[0].embedding.clone();

        let result = SpeakerRepository::undo_merge(&pool, MEETING, &first.merge.unwrap()).await;
        assert!(matches!(result, Err(SpeakerRepositoryError::MergeChanged)));
        assert_eq!(SpeakerRepository::profile_embeddings(&pool).await.unwrap()[0].embedding, print_before, "the later merge is kept");
    }

    #[tokio::test]
    async fn an_empty_voice_sample_never_blanks_a_profile() {
        let pool = pool_with_meeting().await;
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![])], &[])
            .await
            .unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice").await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "Alice").await.unwrap();

        let embedding = &SpeakerRepository::profile_embeddings(&pool).await.unwrap()[0].embedding;
        assert_eq!(embedding, &vec![1.0, 0.0]);
    }

    #[tokio::test]
    async fn naming_an_unknown_label_fails() {
        let pool = pool_with_meeting().await;
        let result = SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(9), "Bob").await;
        assert!(matches!(result, Err(SpeakerRepositoryError::UnknownLabel(_))));
    }

    #[tokio::test]
    async fn deleting_a_profile_unlinks_meetings() {
        let pool = pool_with_meeting().await;
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0])], &[]).await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice").await.unwrap();
        let id = SpeakerRepository::list_profiles(&pool).await.unwrap()[0].id.clone();

        SpeakerRepository::delete_profile(&pool, &id).await.unwrap();

        let speakers = SpeakerRepository::meeting_speakers(&pool, MEETING).await.unwrap();
        assert_eq!(speakers[0].profile_id, None);
        assert_eq!(speakers[0].name, None);
    }

    #[tokio::test]
    async fn the_sample_is_the_longest_line_even_late_in_the_meeting() {
        let pool = pool_with_meeting().await;
        for (id, start, end) in [("e-1", 10.0, 11.0), ("e-2", 12.0, 13.0), ("e-3", 14.0, 15.0), ("e-4", 16.0, 17.0), ("late", 90.0, 98.0)] {
            sqlx::query(
                "INSERT INTO transcripts (id, meeting_id, transcript, timestamp, audio_start_time, audio_end_time, duration, speaker)
                 VALUES (?, ?, 'text', 'ts', ?, ?, 1.0, 'others')",
            )
            .bind(id)
            .bind(MEETING)
            .bind(start)
            .bind(end)
            .execute(&pool)
            .await
            .unwrap();
        }
        let labels: Vec<(String, SpeakerLabel)> = ["t-1", "t-2", "e-1", "e-2", "e-3", "e-4", "late"]
            .iter()
            .map(|id| (id.to_string(), SpeakerLabel::Speaker(0)))
            .collect();
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0])], &labels).await.unwrap();

        let clip = SpeakerRepository::voice_sample(&pool, MEETING, SpeakerLabel::Speaker(0)).await.unwrap();
        assert_eq!(clip.unwrap().segment_id, "late");
    }

    #[tokio::test]
    async fn reassigning_lines_moves_them_to_an_existing_voice_or_me() {
        let pool = pool_with_meeting().await;
        let labels = vec![
            ("t-1".to_string(), SpeakerLabel::Speaker(0)),
            ("t-2".to_string(), SpeakerLabel::Speaker(1)),
        ];
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &labels)
            .await
            .unwrap();
        let speaker_of = |id: &'static str| {
            let pool = pool.clone();
            async move {
                sqlx::query_as::<_, (SpeakerLabel,)>("SELECT speaker FROM transcripts WHERE id = ?")
                    .bind(id)
                    .fetch_one(&pool)
                    .await
                    .unwrap()
                    .0
            }
        };

        let target = SpeakerTarget::Existing { label: SpeakerLabel::Speaker(0) };
        SpeakerRepository::reassign_segments(&pool, MEETING, &["t-2".to_string()], target).await.unwrap();
        assert_eq!(speaker_of("t-2").await, SpeakerLabel::Speaker(0));

        let target = SpeakerTarget::Existing { label: SpeakerLabel::Me };
        SpeakerRepository::reassign_segments(&pool, MEETING, &["t-1".to_string()], target).await.unwrap();
        assert_eq!(speaker_of("t-1").await, SpeakerLabel::Me);

        let target = SpeakerTarget::Existing { label: SpeakerLabel::Speaker(7) };
        let result = SpeakerRepository::reassign_segments(&pool, MEETING, &["t-1".to_string()], target).await;
        assert!(matches!(result, Err(SpeakerRepositoryError::UnknownLabel(_))));
    }

    #[tokio::test]
    async fn a_new_speaker_gets_the_next_label_and_can_be_named_without_a_voice_print() {
        let pool = pool_with_meeting().await;
        let labels = vec![
            ("t-1".to_string(), SpeakerLabel::Speaker(0)),
            ("t-2".to_string(), SpeakerLabel::Speaker(0)),
        ];
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0])], &labels).await.unwrap();

        let label = SpeakerRepository::reassign_segments(&pool, MEETING, &["t-2".to_string()], SpeakerTarget::New)
            .await
            .unwrap();
        assert_eq!(label, SpeakerLabel::Speaker(1));

        let overview = SpeakerRepository::voice_overview(&pool, MEETING).await.unwrap();
        let added = overview.iter().find(|v| v.label == label).unwrap();
        assert_eq!(added.line_count, 1);
        assert!(added.embedding.is_empty());

        // Naming it joins an existing person without changing their voice print.
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice").await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, label, "Alice").await.unwrap();
        let embedding = &SpeakerRepository::profile_embeddings(&pool).await.unwrap()[0].embedding;
        assert_eq!(embedding, &vec![1.0, 0.0]);
    }
}
