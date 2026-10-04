use crate::api::{TranscriptSearchResult, TranscriptSegment};
use chrono::Utc;
use regex::{NoExpand, Regex};
use serde::{Deserialize, Serialize};
use sqlx::{Connection, Error as SqlxError, FromRow, SqlitePool, Sqlite, Transaction};
use tracing::{error, info};
use uuid::Uuid;

/// Full transcript row, including `speaker`, which `models::Transcript`
/// omits. Undo needs every column to restore a deleted row faithfully.
#[derive(Debug, Clone, FromRow, Serialize, Deserialize)]
pub struct TranscriptRow {
    pub id: String,
    pub meeting_id: String,
    pub transcript: String,
    pub timestamp: String,
    pub audio_start_time: Option<f64>,
    pub audio_end_time: Option<f64>,
    pub duration: Option<f64>,
    pub speaker: Option<String>,
}

/// Row state around one edit. Undo applies `before`, redo applies `after`,
/// so every edit type shares a single apply path.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptEdit {
    pub before: Vec<TranscriptRow>,
    pub after: Vec<TranscriptRow>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptMatches {
    pub segment_ids: Vec<String>,
    pub match_count: usize,
}

const ROW_COLUMNS: &str =
    "id, meeting_id, transcript, timestamp, audio_start_time, audio_end_time, duration, speaker";

pub struct TranscriptsRepository;

impl TranscriptsRepository {
    pub async fn is_meeting_pushed(
        pool: &SqlitePool,
        meeting_id: &str,
    ) -> Result<bool, SqlxError> {
        let row: Option<(Option<String>,)> =
            sqlx::query_as("SELECT pushed_at FROM meetings WHERE id = ?")
                .bind(meeting_id)
                .fetch_optional(pool)
                .await?;
        Ok(row.and_then(|r| r.0).is_some())
    }

    async fn fetch_row(
        tx: &mut Transaction<'_, Sqlite>,
        meeting_id: &str,
        id: &str,
    ) -> Result<TranscriptRow, SqlxError> {
        sqlx::query_as::<_, TranscriptRow>(&format!(
            "SELECT {ROW_COLUMNS} FROM transcripts WHERE id = ? AND meeting_id = ?"
        ))
        .bind(id)
        .bind(meeting_id)
        .fetch_one(&mut **tx)
        .await
    }

    async fn fetch_meeting_rows(
        tx: &mut Transaction<'_, Sqlite>,
        meeting_id: &str,
    ) -> Result<Vec<TranscriptRow>, SqlxError> {
        sqlx::query_as::<_, TranscriptRow>(&format!(
            "SELECT {ROW_COLUMNS} FROM transcripts WHERE meeting_id = ? ORDER BY audio_start_time ASC"
        ))
        .bind(meeting_id)
        .fetch_all(&mut **tx)
        .await
    }

    async fn write_rows(
        tx: &mut Transaction<'_, Sqlite>,
        meeting_id: &str,
        delete_ids: &[String],
        upsert: &[TranscriptRow],
    ) -> Result<(), SqlxError> {
        for id in delete_ids {
            sqlx::query("DELETE FROM transcripts WHERE id = ? AND meeting_id = ?")
                .bind(id)
                .bind(meeting_id)
                .execute(&mut **tx)
                .await?;
        }
        for row in upsert {
            if row.meeting_id != meeting_id {
                return Err(SqlxError::Protocol(
                    "transcript row belongs to a different meeting".to_string(),
                ));
            }
            sqlx::query(&format!(
                "INSERT OR REPLACE INTO transcripts ({ROW_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            ))
            .bind(&row.id)
            .bind(&row.meeting_id)
            .bind(&row.transcript)
            .bind(&row.timestamp)
            .bind(row.audio_start_time)
            .bind(row.audio_end_time)
            .bind(row.duration)
            .bind(&row.speaker)
            .execute(&mut **tx)
            .await?;
        }
        Ok(())
    }

    /// Applies a prior edit's row state: removes `delete_ids`, upserts `upsert`.
    /// Used for undo/redo.
    pub async fn apply_edit(
        pool: &SqlitePool,
        meeting_id: &str,
        delete_ids: &[String],
        upsert: &[TranscriptRow],
    ) -> Result<(), SqlxError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;
        Self::write_rows(&mut tx, meeting_id, delete_ids, upsert).await?;
        tx.commit().await
    }

    /// Like `update_transcript_text`, but returns the row before/after so
    /// the edit can join the undo stack.
    pub async fn edit_transcript_text(
        pool: &SqlitePool,
        meeting_id: &str,
        id: &str,
        text: &str,
    ) -> Result<TranscriptEdit, SqlxError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let original = Self::fetch_row(&mut tx, meeting_id, id).await?;
        let mut edited = original.clone();
        edited.transcript = text.to_string();
        Self::write_rows(&mut tx, meeting_id, &[], std::slice::from_ref(&edited)).await?;
        tx.commit().await?;

        Ok(TranscriptEdit { before: vec![original], after: vec![edited] })
    }

    pub async fn delete_transcripts(
        pool: &SqlitePool,
        meeting_id: &str,
        ids: &[String],
    ) -> Result<TranscriptEdit, SqlxError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let mut before = Vec::with_capacity(ids.len());
        for id in ids {
            before.push(Self::fetch_row(&mut tx, meeting_id, id).await?);
        }
        Self::write_rows(&mut tx, meeting_id, ids, &[]).await?;
        tx.commit().await?;

        Ok(TranscriptEdit { before, after: Vec::new() })
    }

    /// Splits at a character offset. The audio time of the split is
    /// interpolated from the offset because Whisper gives no word timings.
    pub async fn split_transcript(
        pool: &SqlitePool,
        meeting_id: &str,
        id: &str,
        cursor: usize,
    ) -> Result<TranscriptEdit, SqlxError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let original = Self::fetch_row(&mut tx, meeting_id, id).await?;
        let chars: Vec<char> = original.transcript.chars().collect();
        let left_text: String = chars.iter().take(cursor).collect::<String>().trim_end().to_string();
        let right_text: String = chars.iter().skip(cursor).collect::<String>().trim_start().to_string();
        if left_text.is_empty() || right_text.is_empty() {
            return Err(SqlxError::Protocol(
                "split point must leave text on both sides".to_string(),
            ));
        }

        let split_time = match (original.audio_start_time, original.audio_end_time) {
            (Some(start), Some(end)) => Some(start + (end - start) * cursor as f64 / chars.len() as f64),
            _ => None,
        };

        let mut left = original.clone();
        left.transcript = left_text;
        left.audio_end_time = split_time.or(original.audio_end_time);
        left.duration = match (left.audio_start_time, left.audio_end_time) {
            (Some(s), Some(e)) => Some(e - s),
            _ => original.duration,
        };

        let mut right = original.clone();
        right.id = format!("transcript-{}", Uuid::new_v4());
        right.transcript = right_text;
        right.audio_start_time = split_time.or(original.audio_start_time);
        right.duration = match (right.audio_start_time, right.audio_end_time) {
            (Some(s), Some(e)) => Some(e - s),
            _ => original.duration,
        };

        let after = vec![left, right];
        Self::write_rows(&mut tx, meeting_id, &[], &after).await?;
        tx.commit().await?;

        Ok(TranscriptEdit { before: vec![original], after })
    }

    /// Merges the given segments into the earliest one. Only adjacent
    /// segments may merge; the UI checks too, but a stale selection can slip through.
    pub async fn merge_transcripts(
        pool: &SqlitePool,
        meeting_id: &str,
        ids: &[String],
    ) -> Result<TranscriptEdit, SqlxError> {
        let mut unique: Vec<&String> = Vec::with_capacity(ids.len());
        for id in ids {
            if !unique.contains(&id) {
                unique.push(id);
            }
        }
        if unique.len() < 2 {
            return Err(SqlxError::Protocol(
                "merge needs at least two segments".to_string(),
            ));
        }
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let ordered_ids: Vec<String> = Self::fetch_meeting_rows(&mut tx, meeting_id)
            .await?
            .into_iter()
            .map(|r| r.id)
            .collect();
        let mut positions = Vec::with_capacity(unique.len());
        for id in &unique {
            positions.push(ordered_ids.iter().position(|o| o == *id).ok_or(SqlxError::RowNotFound)?);
        }
        positions.sort_unstable();
        if positions.windows(2).any(|w| w[1] != w[0] + 1) {
            return Err(SqlxError::Protocol(
                "only adjacent segments can be merged".to_string(),
            ));
        }

        let mut before = Vec::with_capacity(unique.len());
        for id in unique {
            before.push(Self::fetch_row(&mut tx, meeting_id, id).await?);
        }
        before.sort_by(|a, b| {
            a.audio_start_time
                .unwrap_or(0.0)
                .total_cmp(&b.audio_start_time.unwrap_or(0.0))
        });

        let mut merged = before[0].clone();
        merged.transcript = before
            .iter()
            .map(|r| r.transcript.trim())
            .filter(|t| !t.is_empty())
            .collect::<Vec<_>>()
            .join(" ");
        merged.audio_end_time = before
            .iter()
            .filter_map(|r| r.audio_end_time)
            .fold(None, |acc: Option<f64>, e| Some(acc.map_or(e, |a| a.max(e))))
            .or(merged.audio_end_time);
        merged.duration = match (merged.audio_start_time, merged.audio_end_time) {
            (Some(s), Some(e)) => Some(e - s),
            _ => merged.duration,
        };

        let removed: Vec<String> = before[1..].iter().map(|r| r.id.clone()).collect();
        Self::write_rows(&mut tx, meeting_id, &removed, std::slice::from_ref(&merged)).await?;
        tx.commit().await?;

        Ok(TranscriptEdit { before, after: vec![merged] })
    }

    fn match_regex(find: &str) -> Result<Regex, SqlxError> {
        if find.is_empty() {
            return Err(SqlxError::Protocol("search text cannot be empty".to_string()));
        }
        Regex::new(&format!("(?i){}", regex::escape(find)))
            .map_err(|e| SqlxError::Protocol(e.to_string()))
    }

    pub async fn find_in_meeting(
        pool: &SqlitePool,
        meeting_id: &str,
        find: &str,
    ) -> Result<TranscriptMatches, SqlxError> {
        let re = Self::match_regex(find)?;
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;
        let rows = Self::fetch_meeting_rows(&mut tx, meeting_id).await?;
        tx.rollback().await?;

        let mut segment_ids = Vec::new();
        let mut match_count = 0;
        for row in rows {
            let count = re.find_iter(&row.transcript).count();
            if count > 0 {
                match_count += count;
                segment_ids.push(row.id);
            }
        }
        Ok(TranscriptMatches { segment_ids, match_count })
    }

    /// Case-insensitive literal replace across the whole meeting, or only
    /// `only_ids` when given.
    pub async fn replace_in_meeting(
        pool: &SqlitePool,
        meeting_id: &str,
        find: &str,
        replacement: &str,
        only_ids: Option<&[String]>,
    ) -> Result<TranscriptEdit, SqlxError> {
        let re = Self::match_regex(find)?;
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;

        let mut before = Vec::new();
        let mut after = Vec::new();
        for row in Self::fetch_meeting_rows(&mut tx, meeting_id).await? {
            if only_ids.is_some_and(|ids| !ids.contains(&row.id)) {
                continue;
            }
            let replaced = re.replace_all(&row.transcript, NoExpand(replacement)).into_owned();
            if replaced != row.transcript {
                let mut changed = row.clone();
                changed.transcript = replaced;
                before.push(row);
                after.push(changed);
            }
        }
        Self::write_rows(&mut tx, meeting_id, &[], &after).await?;
        tx.commit().await?;

        Ok(TranscriptEdit { before, after })
    }

    /// Every segment of a meeting, for the correction suggester.
    pub async fn list_meeting_rows(
        pool: &SqlitePool,
        meeting_id: &str,
    ) -> Result<Vec<TranscriptRow>, SqlxError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;
        let rows = Self::fetch_meeting_rows(&mut tx, meeting_id).await?;
        tx.rollback().await?;
        Ok(rows)
    }

    /// Updates one transcript segment's text (user edit, pre-push only --
    /// callers are responsible for checking the meeting isn't pushed yet;
    /// this method itself doesn't enforce that lock).
    pub async fn update_transcript_text(
        pool: &SqlitePool,
        transcript_id: &str,
        text: &str,
    ) -> Result<bool, SqlxError> {
        if transcript_id.trim().is_empty() {
            return Err(SqlxError::Protocol(
                "transcript_id cannot be empty".to_string(),
            ));
        }

        let rows_affected = sqlx::query("UPDATE transcripts SET transcript = ? WHERE id = ?")
            .bind(text)
            .bind(transcript_id)
            .execute(pool)
            .await?
            .rows_affected();

        Ok(rows_affected > 0)
    }

    /// Saves a new meeting and its associated transcript segments.
    /// This function uses a transaction to ensure that either both the meeting
    /// and all its transcripts are saved, or none of them are.
    pub async fn save_transcript(
        pool: &SqlitePool,
        meeting_title: &str,
        transcripts: &[TranscriptSegment],
        folder_path: Option<String>,
    ) -> Result<String, SqlxError> {
        let meeting_id = format!("meeting-{}", Uuid::new_v4());

        let mut conn = pool.acquire().await?;
        let mut transaction = conn.begin().await?;

        let now = Utc::now();

        // 1. Create the new meeting
        let result = sqlx::query(
            "INSERT INTO meetings (id, title, created_at, updated_at, folder_path) VALUES (?, ?, ?, ?, ?)",
        )
        .bind(&meeting_id)
        .bind(meeting_title)
        .bind(now)
        .bind(now)
        .bind(&folder_path)
        .execute(&mut *transaction)
        .await;

        if let Err(e) = result {
            error!("Failed to create meeting '{}': {}", meeting_title, e);
            transaction.rollback().await?;
            return Err(e);
        }

        info!("Successfully created meeting with id: {}", meeting_id);

        // 2. Save each transcript segment with audio timing fields
        for segment in transcripts {
            let transcript_id = format!("transcript-{}", Uuid::new_v4());
            let result = sqlx::query(
                "INSERT INTO transcripts (id, meeting_id, transcript, timestamp, audio_start_time, audio_end_time, duration)
                 VALUES (?, ?, ?, ?, ?, ?, ?)"
            )
            .bind(&transcript_id)
            .bind(&meeting_id)
            .bind(&segment.text)
            .bind(&segment.timestamp)
            .bind(segment.audio_start_time)
            .bind(segment.audio_end_time)
            .bind(segment.duration)
            .execute(&mut *transaction)
            .await;

            if let Err(e) = result {
                error!(
                    "Failed to save transcript segment for meeting {}: {}",
                    meeting_id, e
                );
                transaction.rollback().await?;
                return Err(e);
            }
        }

        info!(
            "Successfully saved {} transcript segments for meeting {}",
            transcripts.len(),
            meeting_id
        );

        // Commit the transaction
        transaction.commit().await?;

        Ok(meeting_id)
    }

    /// Searches for a query string within the transcripts.
    /// It returns a list of matching transcripts with context.
    pub async fn search_transcripts(
        pool: &SqlitePool,
        query: &str,
    ) -> Result<Vec<TranscriptSearchResult>, SqlxError> {
        if query.trim().is_empty() {
            return Ok(Vec::new());
        }

        let search_query = format!("%{}%", query.to_lowercase());

        let rows = sqlx::query_as::<_, (String, String, String, String)>(
            "SELECT m.id, m.title, t.transcript, t.timestamp
             FROM meetings m
             JOIN transcripts t ON m.id = t.meeting_id
             WHERE LOWER(t.transcript) LIKE ?",
        )
        .bind(&search_query)
        .fetch_all(pool)
        .await?;

        let results = rows
            .into_iter()
            .map(|(id, title, transcript, timestamp)| {
                let match_context = Self::get_match_context(&transcript, query);
                TranscriptSearchResult {
                    id,
                    title,
                    match_context,
                    timestamp,
                }
            })
            .collect();

        Ok(results)
    }

    /// Helper function to extract a snippet of text around the first match of a query.
    fn get_match_context(transcript: &str, query: &str) -> String {
        let transcript_lower = transcript.to_lowercase();
        let query_lower = query.to_lowercase();

        match transcript_lower.find(&query_lower) {
            Some(match_index) => {
                let start_index = match_index.saturating_sub(100);
                let end_index = (match_index + query.len() + 100).min(transcript.len());

                let mut context = String::new();
                if start_index > 0 {
                    context.push_str("...");
                }
                context.push_str(&transcript[start_index..end_index]);
                if end_index < transcript.len() {
                    context.push_str("...");
                }
                context
            }
            None => transcript.chars().take(200).collect(), // Fallback to the start of the transcript
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sqlx::sqlite::SqlitePoolOptions;

    const MEETING: &str = "meeting-1";

    async fn seeded_pool() -> SqlitePool {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::migrate!("./migrations").run(&pool).await.unwrap();
        sqlx::query("INSERT INTO meetings (id, title, created_at, updated_at) VALUES (?, 't', 'x', 'x')")
            .bind(MEETING)
            .execute(&pool)
            .await
            .unwrap();
        for (id, text, start, end) in [
            ("a", "Hello there", 0.0, 4.0),
            ("b", "Wasool is great", 4.0, 8.0),
            ("c", "wasool again", 8.0, 12.0),
        ] {
            sqlx::query(
                "INSERT INTO transcripts (id, meeting_id, transcript, timestamp, audio_start_time, audio_end_time, duration, speaker)
                 VALUES (?, ?, ?, 'ts', ?, ?, ?, 'mic')",
            )
            .bind(id)
            .bind(MEETING)
            .bind(text)
            .bind(start)
            .bind(end)
            .bind(end - start)
            .execute(&pool)
            .await
            .unwrap();
        }
        pool
    }

    async fn texts(pool: &SqlitePool) -> Vec<String> {
        TranscriptsRepository::list_meeting_rows(pool, MEETING)
            .await
            .unwrap()
            .into_iter()
            .map(|r| r.transcript)
            .collect()
    }

    #[tokio::test]
    async fn delete_then_restore_round_trips_every_column() {
        let pool = seeded_pool().await;
        let ids = vec!["a".to_string(), "b".to_string()];

        let edit = TranscriptsRepository::delete_transcripts(&pool, MEETING, &ids).await.unwrap();
        assert_eq!(texts(&pool).await, vec!["wasool again"]);

        TranscriptsRepository::apply_edit(&pool, MEETING, &[], &edit.before).await.unwrap();
        let rows = TranscriptsRepository::list_meeting_rows(&pool, MEETING).await.unwrap();
        assert_eq!(rows.len(), 3);
        assert_eq!(rows[0].speaker.as_deref(), Some("mic"));
    }

    #[tokio::test]
    async fn split_interpolates_audio_time_and_undo_restores() {
        let pool = seeded_pool().await;

        // "Hello there": cursor 5 is 5/11 of the 0..4s segment.
        let edit = TranscriptsRepository::split_transcript(&pool, MEETING, "a", 5).await.unwrap();
        assert_eq!(texts(&pool).await[..2], ["Hello", "there"]);
        let mid = 4.0 * 5.0 / 11.0;
        assert!((edit.after[0].audio_end_time.unwrap() - mid).abs() < 1e-9);
        assert!((edit.after[1].audio_start_time.unwrap() - mid).abs() < 1e-9);

        let delete_ids: Vec<String> = edit.after.iter().skip(1).map(|r| r.id.clone()).collect();
        TranscriptsRepository::apply_edit(&pool, MEETING, &delete_ids, &edit.before).await.unwrap();
        assert_eq!(texts(&pool).await[0], "Hello there");
        assert_eq!(texts(&pool).await.len(), 3);
    }

    #[tokio::test]
    async fn split_rejects_edges() {
        let pool = seeded_pool().await;
        assert!(TranscriptsRepository::split_transcript(&pool, MEETING, "a", 0).await.is_err());
        assert!(TranscriptsRepository::split_transcript(&pool, MEETING, "a", 11).await.is_err());
    }

    #[tokio::test]
    async fn merge_joins_text_and_spans_full_time_range() {
        let pool = seeded_pool().await;
        let ids = vec!["b".to_string(), "a".to_string()];

        let edit = TranscriptsRepository::merge_transcripts(&pool, MEETING, &ids).await.unwrap();
        assert_eq!(texts(&pool).await, vec!["Hello there Wasool is great", "wasool again"]);
        let merged = &edit.after[0];
        assert_eq!(merged.audio_start_time, Some(0.0));
        assert_eq!(merged.audio_end_time, Some(8.0));
        assert_eq!(merged.duration, Some(8.0));
    }

    #[tokio::test]
    async fn merge_rejects_non_adjacent_and_ignores_duplicate_ids() {
        let pool = seeded_pool().await;

        let skipping = vec!["a".to_string(), "c".to_string()];
        assert!(TranscriptsRepository::merge_transcripts(&pool, MEETING, &skipping).await.is_err());

        let one_real = vec!["a".to_string(), "a".to_string()];
        assert!(TranscriptsRepository::merge_transcripts(&pool, MEETING, &one_real).await.is_err());

        let with_dupe = vec!["a".to_string(), "b".to_string(), "b".to_string()];
        TranscriptsRepository::merge_transcripts(&pool, MEETING, &with_dupe).await.unwrap();
        assert_eq!(texts(&pool).await, vec!["Hello there Wasool is great", "wasool again"]);
    }

    #[tokio::test]
    async fn replace_covers_all_segments_case_insensitively() {
        let pool = seeded_pool().await;

        let found = TranscriptsRepository::find_in_meeting(&pool, MEETING, "wasool").await.unwrap();
        assert_eq!(found.match_count, 2);
        assert_eq!(found.segment_ids, vec!["b", "c"]);

        let edit = TranscriptsRepository::replace_in_meeting(&pool, MEETING, "wasool", "Wusool", None)
            .await
            .unwrap();
        assert_eq!(edit.after.len(), 2);
        assert_eq!(texts(&pool).await[1..], ["Wusool is great", "Wusool again"]);
    }

    #[tokio::test]
    async fn pushed_meetings_are_reported_locked() {
        let pool = seeded_pool().await;
        assert!(!TranscriptsRepository::is_meeting_pushed(&pool, MEETING).await.unwrap());

        sqlx::query("UPDATE meetings SET pushed_at = 'now' WHERE id = ?")
            .bind(MEETING)
            .execute(&pool)
            .await
            .unwrap();
        assert!(TranscriptsRepository::is_meeting_pushed(&pool, MEETING).await.unwrap());
    }
}
