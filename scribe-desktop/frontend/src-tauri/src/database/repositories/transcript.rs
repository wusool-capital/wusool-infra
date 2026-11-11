use crate::api::{TranscriptSearchResult, TranscriptSegment};
use crate::diarization::SpeakerLabel;
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
    pub speaker: Option<SpeakerLabel>,
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

/// Below this a line reads as a fragment ("Yeah.", "And") and joins its neighbour.
const MIN_LINE_SECS: f64 = 2.5;
/// A longer silence is a real break between lines.
const MAX_JOIN_GAP_SECS: f64 = 2.0;
/// Matches the live pipeline's cap, keeping lines easy to read and edit.
const MAX_LINE_SECS: f64 = 20.0;

/// One line made from several in time order: texts joined, times spanning all of them, first row's id and speaker.
fn join_rows(rows: &[TranscriptRow]) -> TranscriptRow {
    let mut merged = rows[0].clone();
    merged.transcript = rows
        .iter()
        .map(|r| r.transcript.trim())
        .filter(|t| !t.is_empty())
        .collect::<Vec<_>>()
        .join(" ");
    merged.audio_end_time = rows
        .iter()
        .filter_map(|r| r.audio_end_time)
        .fold(None, |acc: Option<f64>, e| Some(acc.map_or(e, |a| a.max(e))))
        .or(merged.audio_end_time);
    merged.duration = match (merged.audio_start_time, merged.audio_end_time) {
        (Some(s), Some(e)) => Some(e - s),
        _ => merged.duration,
    };
    merged
}

fn ends_sentence(text: &str) -> bool {
    text.trim_end().ends_with(['.', '?', '!', '…'])
}

/// Index ranges of time-ordered rows to join: same speaker, close in time, and the line so far is
/// either unfinished or still a fragment. Groups of one are left alone.
fn tidy_groups(rows: &[TranscriptRow]) -> Vec<std::ops::Range<usize>> {
    let mut groups = Vec::new();
    let mut start = 0;
    for i in 1..=rows.len() {
        let joins = i < rows.len() && {
            let (first, prev, next) = (&rows[start], &rows[i - 1], &rows[i]);
            match (first.audio_start_time, prev.audio_end_time, next.audio_start_time, next.audio_end_time) {
                (Some(line_start), Some(prev_end), Some(next_start), Some(next_end)) => {
                    let line_so_far = prev_end - line_start;
                    next.speaker == prev.speaker
                        && next_start - prev_end <= MAX_JOIN_GAP_SECS
                        && next_end - line_start <= MAX_LINE_SECS
                        && (!ends_sentence(&prev.transcript) || line_so_far < MIN_LINE_SECS)
                }
                _ => false,
            }
        };
        if !joins {
            if i - start > 1 {
                groups.push(start..i);
            }
            start = i;
        }
    }
    groups
}

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
            // Speakers belong to diarization, so an existing row keeps its current speaker on undo.
            sqlx::query(&format!(
                "INSERT INTO transcripts ({ROW_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                 ON CONFLICT(id) DO UPDATE SET
                   meeting_id = excluded.meeting_id, transcript = excluded.transcript,
                   timestamp = excluded.timestamp, audio_start_time = excluded.audio_start_time,
                   audio_end_time = excluded.audio_end_time, duration = excluded.duration"
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

        let merged = join_rows(&before);
        let removed: Vec<String> = before[1..].iter().map(|r| r.id.clone()).collect();
        Self::write_rows(&mut tx, meeting_id, &removed, std::slice::from_ref(&merged)).await?;
        tx.commit().await?;

        Ok(TranscriptEdit { before, after: vec![merged] })
    }

    /// Joins every run of fragments into sentence-sized lines in one undoable edit.
    pub async fn tidy_transcripts(pool: &SqlitePool, meeting_id: &str) -> Result<TranscriptEdit, SqlxError> {
        let mut conn = pool.acquire().await?;
        let mut tx = conn.begin().await?;
        let rows = Self::fetch_meeting_rows(&mut tx, meeting_id).await?;

        let mut before = Vec::new();
        let mut after = Vec::new();
        let mut removed = Vec::new();
        for group in tidy_groups(&rows) {
            let members = &rows[group];
            let merged = join_rows(members);
            removed.extend(members[1..].iter().map(|r| r.id.clone()));
            before.extend_from_slice(members);
            after.push(merged);
        }
        if !after.is_empty() {
            Self::write_rows(&mut tx, meeting_id, &removed, &after).await?;
        }
        tx.commit().await?;
        Ok(TranscriptEdit { before, after })
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
                "INSERT INTO transcripts (id, meeting_id, transcript, timestamp, audio_start_time, audio_end_time, duration, speaker)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            )
            .bind(&transcript_id)
            .bind(&meeting_id)
            .bind(&segment.text)
            .bind(&segment.timestamp)
            .bind(segment.audio_start_time)
            .bind(segment.audio_end_time)
            .bind(segment.duration)
            .bind(segment.speaker)
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
        assert_eq!(rows[0].speaker, Some(SpeakerLabel::Me));
    }

    fn row(id: &str, text: &str, start: f64, end: f64, speaker: Option<SpeakerLabel>) -> TranscriptRow {
        TranscriptRow {
            id: id.to_string(),
            meeting_id: MEETING.to_string(),
            transcript: text.to_string(),
            timestamp: "ts".to_string(),
            audio_start_time: Some(start),
            audio_end_time: Some(end),
            duration: Some(end - start),
            speaker,
        }
    }

    #[test]
    fn tidy_joins_fragments_but_keeps_finished_sentences_apart() {
        let me = Some(SpeakerLabel::Me);
        // The fragmented lines from a real meeting: 0:19 "And" / 0:24 "We ate..." / 0:27 "An" / 0:28 "d".
        let rows = vec![
            row("a", "Today was a beautiful day.", 6.0, 8.6, me),
            row("b", "And", 19.0, 19.4, me),
            row("c", "we ate a lot of food", 20.0, 22.0, me),
            row("d", "and then", 22.8, 23.5, me),
            row("e", "Next topic.", 40.0, 43.0, me),
        ];
        assert_eq!(tidy_groups(&rows), vec![1..4]);
    }

    #[test]
    fn tidy_never_joins_different_speakers_or_long_gaps() {
        let rows = vec![
            row("a", "So", 0.0, 0.5, Some(SpeakerLabel::Me)),
            row("b", "right", 0.8, 1.2, Some(SpeakerLabel::Speaker(0))),
            row("c", "and", 5.0, 5.3, Some(SpeakerLabel::Speaker(0))),
        ];
        assert!(tidy_groups(&rows).is_empty());
    }

    #[test]
    fn tidy_caps_line_length() {
        let me = Some(SpeakerLabel::Me);
        let rows: Vec<TranscriptRow> =
            (0..12).map(|i| row(&format!("r{i}"), "and so on", i as f64 * 3.0, i as f64 * 3.0 + 2.5, me)).collect();
        for group in tidy_groups(&rows) {
            let span = rows[group.end - 1].audio_end_time.unwrap() - rows[group.start].audio_start_time.unwrap();
            assert!(span <= MAX_LINE_SECS);
        }
    }

    #[tokio::test]
    async fn tidy_is_one_undoable_edit() {
        let pool = seeded_pool().await;
        // Seeded lines are back to back with no sentence ends, so they join into one.
        let edit = TranscriptsRepository::tidy_transcripts(&pool, MEETING).await.unwrap();
        assert_eq!(texts(&pool).await, vec!["Hello there Wasool is great wasool again"]);
        assert_eq!(edit.before.len(), 3);
        assert_eq!(edit.after.len(), 1);

        let delete_ids: Vec<String> = Vec::new();
        TranscriptsRepository::apply_edit(&pool, MEETING, &delete_ids, &edit.before).await.unwrap();
        assert_eq!(texts(&pool).await.len(), 3);
    }

    #[tokio::test]
    async fn undoing_a_text_edit_keeps_a_speaker_set_since() {
        let pool = seeded_pool().await;
        let edit = TranscriptsRepository::edit_transcript_text(&pool, MEETING, "b", "Wusool is great")
            .await
            .unwrap();
        // Diarization relabels the line after the edit was recorded.
        sqlx::query("UPDATE transcripts SET speaker = 'speaker_1' WHERE id = 'b'")
            .execute(&pool)
            .await
            .unwrap();

        TranscriptsRepository::apply_edit(&pool, MEETING, &[], &edit.before).await.unwrap();
        let rows = TranscriptsRepository::list_meeting_rows(&pool, MEETING).await.unwrap();
        assert_eq!(rows[1].transcript, "Wasool is great");
        assert_eq!(rows[1].speaker, Some(SpeakerLabel::Speaker(1)));
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
