// database/repositories/speaker.rs
//
// Persistence for the voice library (speaker_profiles) and per-meeting speaker maps
// (meeting_speakers). Embeddings are stored as little-endian f32 BLOBs.

use chrono::Utc;
use serde::Serialize;
use sqlx::{Connection, FromRow, SqlitePool};
use uuid::Uuid;

use crate::diarization::assign::merge_embedding;
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

#[derive(Debug, thiserror::Error)]
pub enum SpeakerRepositoryError {
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error("{0} has no stored voice in this meeting")]
    UnknownLabel(SpeakerLabel),
}

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

        sqlx::query("DELETE FROM meeting_speakers WHERE meeting_id = ?")
            .bind(meeting_id)
            .execute(&mut *tx)
            .await?;
        for voice in voices {
            sqlx::query(
                "INSERT INTO meeting_speakers (meeting_id, label, profile_id, embedding) VALUES (?, ?, ?, ?)",
            )
            .bind(meeting_id)
            .bind(voice.label)
            .bind(&voice.profile_id)
            .bind(encode_embedding(&voice.embedding))
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

        tx.commit().await
    }

    /// Names a meeting's voice. An existing person with that name absorbs this voice sample,
    /// otherwise a new person is enrolled from it.
    pub async fn name_meeting_speaker(
        pool: &SqlitePool,
        meeting_id: &str,
        label: SpeakerLabel,
        name: &str,
    ) -> Result<(), SpeakerRepositoryError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let voice: Option<(Vec<u8>,)> =
            sqlx::query_as("SELECT embedding FROM meeting_speakers WHERE meeting_id = ? AND label = ?")
                .bind(meeting_id)
                .bind(label)
                .fetch_optional(&mut *tx)
                .await?;
        let voice = decode_embedding(&voice.ok_or(SpeakerRepositoryError::UnknownLabel(label))?.0);

        let existing: Option<(String, Vec<u8>, i64)> = sqlx::query_as(
            "SELECT id, embedding, sample_count FROM speaker_profiles WHERE name = ? COLLATE NOCASE",
        )
        .bind(name)
        .fetch_optional(&mut *tx)
        .await?;

        let now = Utc::now().to_rfc3339();
        let profile_id = match existing {
            Some((id, saved, samples)) => {
                let merged = merge_embedding(&decode_embedding(&saved), samples.max(1) as u32, &voice);
                sqlx::query(
                    "UPDATE speaker_profiles SET embedding = ?, sample_count = sample_count + 1, updated_at = ? WHERE id = ?",
                )
                .bind(encode_embedding(&merged))
                .bind(&now)
                .bind(&id)
                .execute(&mut *tx)
                .await?;
                id
            }
            None => {
                let id = format!("speaker-{}", Uuid::new_v4());
                sqlx::query(
                    "INSERT INTO speaker_profiles (id, name, embedding, sample_count, created_at, updated_at)
                     VALUES (?, ?, ?, 1, ?, ?)",
                )
                .bind(&id)
                .bind(name)
                .bind(encode_embedding(&voice))
                .bind(&now)
                .bind(&now)
                .execute(&mut *tx)
                .await?;
                id
            }
        };

        sqlx::query("UPDATE meeting_speakers SET profile_id = ? WHERE meeting_id = ? AND label = ?")
            .bind(&profile_id)
            .bind(meeting_id)
            .bind(label)
            .execute(&mut *tx)
            .await?;

        tx.commit().await?;
        Ok(())
    }
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
    async fn naming_enrols_then_refines_a_profile() {
        let pool = pool_with_meeting().await;
        SpeakerRepository::save_diarization(&pool, MEETING, &[voice(0, vec![1.0, 0.0]), voice(1, vec![0.0, 1.0])], &[])
            .await
            .unwrap();

        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(0), "Alice").await.unwrap();
        SpeakerRepository::name_meeting_speaker(&pool, MEETING, SpeakerLabel::Speaker(1), "alice").await.unwrap();

        let profiles = SpeakerRepository::list_profiles(&pool).await.unwrap();
        assert_eq!(profiles.len(), 1, "same name, any case, is the same person");
        assert_eq!(profiles[0].sample_count, 2);
        let embedding = &SpeakerRepository::profile_embeddings(&pool).await.unwrap()[0].embedding;
        assert_eq!(embedding, &vec![0.5, 0.5]);

        let names: Vec<Option<String>> = SpeakerRepository::meeting_speakers(&pool, MEETING)
            .await
            .unwrap()
            .into_iter()
            .map(|s| s.name)
            .collect();
        assert_eq!(names, vec![Some("Alice".to_string()), Some("Alice".to_string())]);
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
}
