use chrono::Utc;
use serde::{Deserialize, Serialize};
use sqlx::{Error as SqlxError, FromRow, SqlitePool};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, FromRow)]
pub struct MeetingNotes {
    pub meeting_id: String,
    pub notes_markdown: Option<String>,
    pub notes_json: Option<String>,
    pub updated_at: String,
}

pub struct MeetingNotesRepository;

impl MeetingNotesRepository {
    pub async fn get(pool: &SqlitePool, meeting_id: &str) -> Result<Option<MeetingNotes>, SqlxError> {
        sqlx::query_as::<_, MeetingNotes>(
            "SELECT meeting_id, notes_markdown, notes_json, updated_at \
             FROM meeting_notes WHERE meeting_id = ?",
        )
        .bind(meeting_id)
        .fetch_optional(pool)
        .await
    }

    pub async fn upsert(
        pool: &SqlitePool,
        meeting_id: &str,
        notes_markdown: Option<&str>,
        notes_json: Option<&str>,
    ) -> Result<(), SqlxError> {
        let now = Utc::now().to_rfc3339();
        sqlx::query(
            "INSERT INTO meeting_notes \
               (meeting_id, notes_markdown, notes_json, created_at, updated_at, needs_sync) \
             VALUES (?, ?, ?, ?, ?, 1) \
             ON CONFLICT(meeting_id) DO UPDATE SET \
               notes_markdown = excluded.notes_markdown, \
               notes_json = excluded.notes_json, \
               updated_at = excluded.updated_at, \
               needs_sync = 1",
        )
        .bind(meeting_id)
        .bind(notes_markdown)
        .bind(notes_json)
        .bind(&now)
        .bind(&now)
        .execute(pool)
        .await?;
        Ok(())
    }

    /// Clears the flag only if the row still holds what was sent, so an edit
    /// made while the request was in flight still gets synced.
    pub async fn mark_synced(
        pool: &SqlitePool,
        meeting_id: &str,
        sent_markdown: Option<&str>,
    ) -> Result<(), SqlxError> {
        sqlx::query(
            "UPDATE meeting_notes SET needs_sync = 0 \
             WHERE meeting_id = ? AND notes_markdown IS ?",
        )
        .bind(meeting_id)
        .bind(sent_markdown)
        .execute(pool)
        .await?;
        Ok(())
    }

    /// Unpushed meetings are skipped: their notes travel with the first push.
    pub async fn list_dirty_pushed(pool: &SqlitePool) -> Result<Vec<String>, SqlxError> {
        sqlx::query_scalar::<_, String>(
            "SELECT n.meeting_id FROM meeting_notes n \
             JOIN meetings m ON m.id = n.meeting_id \
             WHERE n.needs_sync = 1 AND m.pushed_at IS NOT NULL",
        )
        .fetch_all(pool)
        .await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sqlx::sqlite::SqlitePoolOptions;

    async fn pool_with_meeting(pushed: bool) -> SqlitePool {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::migrate!("./migrations").run(&pool).await.unwrap();
        let now = Utc::now().to_rfc3339();
        sqlx::query("INSERT INTO meetings (id, title, created_at, updated_at, pushed_at) VALUES (?, ?, ?, ?, ?)")
            .bind("m1")
            .bind("Meeting")
            .bind(&now)
            .bind(&now)
            .bind(if pushed { Some(now.clone()) } else { None })
            .execute(&pool)
            .await
            .unwrap();
        pool
    }

    #[tokio::test]
    async fn upsert_then_get_round_trips_and_overwrites() {
        let pool = pool_with_meeting(false).await;
        MeetingNotesRepository::upsert(&pool, "m1", Some("- a"), Some("[]")).await.unwrap();
        MeetingNotesRepository::upsert(&pool, "m1", Some("- b"), Some("[1]")).await.unwrap();

        let notes = MeetingNotesRepository::get(&pool, "m1").await.unwrap().unwrap();
        assert_eq!(notes.notes_markdown.as_deref(), Some("- b"));
        assert_eq!(notes.notes_json.as_deref(), Some("[1]"));
    }

    #[tokio::test]
    async fn dirty_list_only_covers_pushed_meetings() {
        let unpushed = pool_with_meeting(false).await;
        MeetingNotesRepository::upsert(&unpushed, "m1", Some("x"), None).await.unwrap();
        assert!(MeetingNotesRepository::list_dirty_pushed(&unpushed).await.unwrap().is_empty());

        let pushed = pool_with_meeting(true).await;
        MeetingNotesRepository::upsert(&pushed, "m1", Some("x"), None).await.unwrap();
        assert_eq!(MeetingNotesRepository::list_dirty_pushed(&pushed).await.unwrap(), vec!["m1"]);
    }

    #[tokio::test]
    async fn mark_synced_ignores_stale_content() {
        let pool = pool_with_meeting(true).await;
        MeetingNotesRepository::upsert(&pool, "m1", Some("new"), None).await.unwrap();

        MeetingNotesRepository::mark_synced(&pool, "m1", Some("old")).await.unwrap();
        assert_eq!(MeetingNotesRepository::list_dirty_pushed(&pool).await.unwrap(), vec!["m1"]);

        MeetingNotesRepository::mark_synced(&pool, "m1", Some("new")).await.unwrap();
        assert!(MeetingNotesRepository::list_dirty_pushed(&pool).await.unwrap().is_empty());
    }
}
