//! Push flow: sends a finished, user-edited transcript to the Scribe
//! EC2 backend's `/desktop/meetings` ingestion route (see
//! app/desktop/api in the wusool-scribe repo) once the user is done
//! editing and tagging a recording. Push is one-shot per recording —
//! the backend rejects a re-push for the same (install_id,
//! local_recording_id) pair with 409, so a re-edit-then-push is
//! surfaced as an error rather than silently discarded.
//!
//! Summarization happens server-side; this app only pushes the
//! transcript and polls for the resulting summary — it does not call
//! its own local summarizer for pushed meetings.
//!
//! The remote meeting_id a push gets back is never persisted (only
//! held in the frontend's React state for that session), so a summary
//! that lands after the user closes the app -- or just never clicks
//! "Check" -- would otherwise be permanently unreachable. sync_pushed_meetings
//! is the recovery path: it lists this install's own meetings from the
//! server (keyed on install_id, which push_config.json does persist)
//! and reconciles anything missing, on launch and on a background timer.

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};

use log::{error, info, warn};
use once_cell::sync::Lazy;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use tauri::{AppHandle, Manager, Runtime};
use tauri_plugin_store::StoreExt;
use uuid::Uuid;

use crate::database::models::MeetingModel;
use crate::database::repositories::meeting::MeetingsRepository;
use crate::state::AppState;

const PUSH_CONFIG_STORE: &str = "push_config.json";

// ---------------------------------------------------------------------------
// Config: where to push, and this install's identity
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PushConfig {
    #[serde(default)]
    pub server_url: String,
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "new_install_id")]
    pub install_id: String,
}

fn new_install_id() -> String {
    Uuid::new_v4().to_string()
}

impl Default for PushConfig {
    fn default() -> Self {
        Self {
            server_url: String::new(),
            api_key: String::new(),
            install_id: new_install_id(),
        }
    }
}

fn load_push_config<R: Runtime>(app: &AppHandle<R>) -> PushConfig {
    let store = match app.store(PUSH_CONFIG_STORE) {
        Ok(store) => store,
        Err(e) => {
            warn!("Failed to access push config store: {}, using defaults", e);
            return PushConfig::default();
        }
    };

    let config = match store.get("config") {
        Some(value) => serde_json::from_value::<PushConfig>(value.clone()).unwrap_or_else(|e| {
            warn!("Failed to deserialize push config: {}, using defaults", e);
            PushConfig::default()
        }),
        None => PushConfig::default(),
    };

    // Persist a freshly-generated install_id immediately so it's stable
    // across restarts even before the user has saved a server_url/api_key.
    if store.get("config").is_none() {
        if let Ok(value) = serde_json::to_value(&config) {
            store.set("config", value);
            let _ = store.save();
        }
    }

    config
}

fn save_push_config<R: Runtime>(app: &AppHandle<R>, config: &PushConfig) -> Result<(), String> {
    let store = app
        .store(PUSH_CONFIG_STORE)
        .map_err(|e| format!("Failed to access push config store: {}", e))?;
    let value =
        serde_json::to_value(config).map_err(|e| format!("Failed to serialize push config: {}", e))?;
    store.set("config", value);
    store
        .save()
        .map_err(|e| format!("Failed to save push config to disk: {}", e))?;
    Ok(())
}

#[tauri::command]
pub async fn get_push_config<R: Runtime>(app: AppHandle<R>) -> Result<PushConfig, String> {
    Ok(load_push_config(&app))
}

#[tauri::command]
pub async fn set_push_config<R: Runtime>(
    app: AppHandle<R>,
    server_url: String,
    api_key: String,
) -> Result<PushConfig, String> {
    let mut config = load_push_config(&app);
    config.server_url = server_url;
    config.api_key = api_key;
    save_push_config(&app, &config)?;
    Ok(config)
}

// ---------------------------------------------------------------------------
// Push payload — must match app.desktop.schemas.DesktopMeetingSubmitRequest
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize)]
struct DesktopTranscriptTurn {
    speaker: String,
    start: f64,
    end: f64,
    text: String,
}

#[derive(Debug, Serialize)]
struct DesktopMeetingSubmitRequest {
    install_id: String,
    local_recording_id: String,
    transcript: Vec<DesktopTranscriptTurn>,
    duration_seconds: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    buyer_query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    buyer_selection: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    seller_query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    seller_selection: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    investor_query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    investor_selection: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    internal_query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    internal_selection: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    general_query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    general_selection: Option<String>,
    org_names: HashMap<String, String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    slack_channel_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    client_version: Option<String>,
    /// Always true: the desktop app always wants the finished summary
    /// back via GET /desktop/meetings/{id} (see push_meeting's poll
    /// flow). Sent explicitly rather than relying on the backend's
    /// default, since that default could change independently.
    return_summary: bool,
}

// ---------------------------------------------------------------------------
// Buyer/seller company search — mirrors app.desktop.api.search_companies,
// which itself mirrors the Slack --buyer/--seller confirmation modal's
// candidate sourcing (Wusool organizations, falling back to scribe's own
// companies) and value encoding ("attio:<id>" / a company UUID / the
// "__create_new__" sentinel).
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct CompanyCandidate {
    pub label: String,
    pub value: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct CompanySearchResponse {
    pub candidates: Vec<CompanyCandidate>,
    pub org_names: HashMap<String, String>,
}

#[tauri::command]
pub async fn search_companies<R: Runtime>(
    app: AppHandle<R>,
    query: String,
) -> Result<CompanySearchResponse, String> {
    let config = load_push_config(&app);
    if config.server_url.trim().is_empty() {
        return Err("Push destination is not configured. Set it in Settings.".to_string());
    }
    if query.trim().is_empty() {
        return Ok(CompanySearchResponse { candidates: Vec::new(), org_names: HashMap::new() });
    }

    let url = format!("{}/desktop/companies/search", config.server_url.trim_end_matches('/'));
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let mut request = client.get(&url).query(&[("query", query.as_str())]);
    if !config.api_key.trim().is_empty() {
        request = request.header("Authorization", format!("Bearer {}", config.api_key));
    }

    let response = request
        .send()
        .await
        .map_err(|e| format!("Failed to reach {}: {}", url, e))?;
    let status = response.status();
    let response_text = response.text().await.unwrap_or_default();

    if !status.is_success() {
        return Err(format!("Company search failed ({}): {}", status, response_text));
    }

    serde_json::from_str(&response_text)
        .map_err(|e| format!("Search server returned an unexpected response: {}", e))
}

#[derive(Debug, Deserialize, Serialize)]
pub struct DesktopMeetingSubmitResponse {
    pub meeting_id: String,
    pub status: String,
    pub already_existed: bool,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct DesktopMeetingStatusResponse {
    pub meeting_id: String,
    pub status: String,
    pub summary: Option<serde_json::Value>,
}

/// speaker isn't real per-person diarization in this build (see
/// meetily/CLAUDE.md and app/audio/transcription — no pyannote
/// integration is compiled in), so every turn gets a single generic
/// label. The backend's SummarizeMeetingCommand only reads
/// speaker+text and doesn't require it to be meaningful.
const GENERIC_SPEAKER_LABEL: &str = "Participant";

#[tauri::command]
pub async fn push_meeting<R: Runtime>(
    app: AppHandle<R>,
    state: tauri::State<'_, AppState>,
    meeting_id: String,
    slack_channel_id: Option<String>,
    buyer_query: Option<String>,
    buyer_selection: Option<String>,
    seller_query: Option<String>,
    seller_selection: Option<String>,
    investor_query: Option<String>,
    investor_selection: Option<String>,
    internal_query: Option<String>,
    internal_selection: Option<String>,
    general_query: Option<String>,
    general_selection: Option<String>,
    org_names: Option<HashMap<String, String>>,
) -> Result<DesktopMeetingSubmitResponse, String> {
    let config = load_push_config(&app);
    if config.server_url.trim().is_empty() {
        return Err("Push destination is not configured. Set it in Settings.".to_string());
    }

    let pool = state.db_manager.pool();
    let meeting = MeetingsRepository::get_meeting(pool, &meeting_id)
        .await
        .map_err(|e| format!("Failed to load meeting {}: {}", meeting_id, e))?
        .ok_or_else(|| format!("Meeting {} not found", meeting_id))?;

    if meeting.transcripts.is_empty() {
        return Err("This meeting has no transcript to push.".to_string());
    }

    let turns: Vec<DesktopTranscriptTurn> = meeting
        .transcripts
        .iter()
        .map(|t| DesktopTranscriptTurn {
            speaker: GENERIC_SPEAKER_LABEL.to_string(),
            start: t.audio_start_time.unwrap_or(0.0),
            end: t.audio_end_time.unwrap_or(0.0),
            text: t.text.clone(),
        })
        .collect();

    let duration_seconds = meeting
        .transcripts
        .iter()
        .filter_map(|t| t.audio_end_time)
        .fold(0.0_f64, f64::max);

    let request_body = DesktopMeetingSubmitRequest {
        install_id: config.install_id.clone(),
        local_recording_id: meeting_id.clone(),
        transcript: turns,
        duration_seconds,
        buyer_query: buyer_query.filter(|s| !s.trim().is_empty()),
        buyer_selection,
        seller_query: seller_query.filter(|s| !s.trim().is_empty()),
        seller_selection,
        investor_query: investor_query.filter(|s| !s.trim().is_empty()),
        investor_selection,
        internal_query: internal_query.filter(|s| !s.trim().is_empty()),
        internal_selection,
        general_query: general_query.filter(|s| !s.trim().is_empty()),
        general_selection,
        org_names: org_names.unwrap_or_default(),
        slack_channel_id: slack_channel_id.filter(|s| !s.trim().is_empty()),
        client_version: Some(env!("CARGO_PKG_VERSION").to_string()),
        return_summary: true,
    };

    let url = format!("{}/desktop/meetings", config.server_url.trim_end_matches('/'));
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let mut request = client.post(&url).json(&request_body);
    if !config.api_key.trim().is_empty() {
        request = request.header("Authorization", format!("Bearer {}", config.api_key));
    }

    let response = request
        .send()
        .await
        .map_err(|e| format!("Failed to reach {}: {}", url, e))?;
    let status = response.status();
    let response_text = response.text().await.unwrap_or_default();

    if status.as_u16() == 409 {
        return Err(
            "This meeting was already pushed. Edits after a push are not re-sent.".to_string(),
        );
    }
    if !status.is_success() {
        error!("Push failed for meeting {}: {} {}", meeting_id, status, response_text);
        return Err(format!("Push failed ({}): {}", status, response_text));
    }

    let parsed: DesktopMeetingSubmitResponse = serde_json::from_str(&response_text)
        .map_err(|e| format!("Push server returned an unexpected response: {}", e))?;
    info!(
        "Pushed meeting {} -> remote meeting {} (status={})",
        meeting_id, parsed.meeting_id, parsed.status
    );

    // Locks further transcript edits (see update_transcript_text) and
    // hides the push option, persisted across restarts -- not just this
    // session's React state.
    if let Err(e) = MeetingsRepository::mark_meeting_pushed(pool, &meeting_id).await {
        warn!("Pushed meeting {} but failed to record pushed_at: {}", meeting_id, e);
    }

    Ok(parsed)
}

// ---------------------------------------------------------------------------
// Shared "a summary arrived" handling -- used by both get_push_status
// (checkStatus's manual, same-session poll) and sync_pushed_meetings
// (the install_id-keyed background/launch reconcile), so there is
// exactly one implementation of filing a summary and one of the title
// normalization, rather than a second copy drifting in either Rust or
// the frontend.
// ---------------------------------------------------------------------------

/// Scribe prefixes a generated title with role brackets like
/// "[Seller: Acme] [Buyer: X]" -- mirrors the TS
/// stripRoleBracketPrefix (usePush.ts) exactly, so titles read the same
/// whether filled by the manual check or by sync.
static ROLE_BRACKET_PREFIX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(?i)^(\[(?:Seller|Buyer|Investor|Internal|General):[^\]]*\]\s*)+").unwrap()
});

fn strip_role_bracket_prefix(title: &str) -> String {
    ROLE_BRACKET_PREFIX.replace(title, "").trim().to_string()
}

/// Matches only the auto-generated recording placeholder (see
/// recording_commands.rs's "Meeting {timestamp}" default), never a real
/// title -- so a title fill never clobbers a user's manual rename or an
/// AI title a previous check/sync already applied.
static PLACEHOLDER_TITLE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^Meeting \d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$").unwrap());

fn is_placeholder_title(title: &str) -> bool {
    PLACEHOLDER_TITLE.is_match(title)
}

/// Applies the local, network-free fills a finished summary implies:
/// the AI-generated title (only over a still-placeholder title) and
/// pushed_at (only if unset, recovering a push whose mark never landed
/// locally). Idempotent -- safe to call again even if a previous call
/// already applied both.
async fn apply_local_summary_fills(
    pool: &SqlitePool,
    meeting_id: &str,
    summary: &serde_json::Value,
    current_title: &str,
    pushed_at: Option<&str>,
) {
    if is_placeholder_title(current_title) {
        let raw_title = summary.get("title").and_then(|v| v.as_str()).unwrap_or("").trim();
        let ai_title = strip_role_bracket_prefix(raw_title);
        if !ai_title.is_empty() {
            if let Err(e) = MeetingsRepository::update_meeting_title(pool, meeting_id, &ai_title).await
            {
                warn!("Failed to update title for meeting {}: {}", meeting_id, e);
            }
        }
    }
    if pushed_at.is_none() {
        if let Err(e) = MeetingsRepository::mark_meeting_pushed(pool, meeting_id).await {
            warn!("Failed to mark meeting {} pushed: {}", meeting_id, e);
        }
    }
}

/// Files a freshly-fetched summary: writes it into the meeting's
/// recording folder (see write_summary_files) alongside its audio and
/// transcripts.json, and applies the local fills above. Every failure
/// is warn-logged and non-fatal -- a summary that can't be filed this
/// time is retried on the next check/sync, not lost.
async fn store_summary_for_meeting(pool: &SqlitePool, meeting_id: &str, summary: &serde_json::Value) {
    match MeetingsRepository::get_meeting_metadata(pool, meeting_id).await {
        Ok(Some(meeting)) => {
            match &meeting.folder_path {
                Some(folder_path) => {
                    let folder = std::path::PathBuf::from(folder_path);
                    if folder.exists() {
                        if let Err(e) = write_summary_files(&folder, summary) {
                            warn!("Failed to write summary files to {}: {}", folder.display(), e);
                        } else {
                            info!("Saved summary to {}", folder.display());
                        }
                    } else {
                        warn!(
                            "Recording folder {} does not exist; summary not saved to disk",
                            folder_path
                        );
                    }
                }
                None => warn!(
                    "Meeting {} has no recording folder; summary not saved to disk",
                    meeting_id
                ),
            }
            apply_local_summary_fills(
                pool,
                meeting_id,
                summary,
                &meeting.title,
                meeting.pushed_at.as_deref(),
            )
            .await;
        }
        Ok(None) => warn!("Meeting {} not found locally; summary not saved to disk", meeting_id),
        Err(e) => warn!("Failed to load meeting {} for summary save: {}", meeting_id, e),
    }
}

/// GET /desktop/meetings/{remote_meeting_id} -- shared by get_push_status
/// and sync_pushed_meetings's per-meeting fetch.
async fn fetch_meeting_status(
    client: &reqwest::Client,
    config: &PushConfig,
    remote_meeting_id: &str,
) -> Result<DesktopMeetingStatusResponse, String> {
    let url = format!(
        "{}/desktop/meetings/{}",
        config.server_url.trim_end_matches('/'),
        remote_meeting_id
    );
    let mut request = client.get(&url);
    if !config.api_key.trim().is_empty() {
        request = request.header("Authorization", format!("Bearer {}", config.api_key));
    }

    let response = request
        .send()
        .await
        .map_err(|e| format!("Failed to reach {}: {}", url, e))?;
    let status = response.status();
    let response_text = response.text().await.unwrap_or_default();

    if !status.is_success() {
        return Err(format!("Status check failed ({}): {}", status, response_text));
    }

    serde_json::from_str(&response_text)
        .map_err(|e| format!("Status server returned an unexpected response: {}", e))
}

#[tauri::command]
pub async fn get_push_status<R: Runtime>(
    app: AppHandle<R>,
    state: tauri::State<'_, AppState>,
    meeting_id: String,
    remote_meeting_id: String,
) -> Result<DesktopMeetingStatusResponse, String> {
    let config = load_push_config(&app);
    if config.server_url.trim().is_empty() {
        return Err("Push destination is not configured. Set it in Settings.".to_string());
    }
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let parsed = fetch_meeting_status(&client, &config, &remote_meeting_id).await?;

    // Once a summary comes back, file it alongside the recording's own
    // audio + transcripts.json in that meeting's existing recording
    // folder (see recording_saver.rs), so audio/transcript/summary all
    // live together -- the same folder the sidebar's tag grouping and
    // "Open Recording Folder" button both point at.
    if let Some(summary) = &parsed.summary {
        store_summary_for_meeting(state.db_manager.pool(), &meeting_id, summary).await;
    }

    Ok(parsed)
}

/// Writes summary.md (human-readable) and summary.json (raw) into a
/// meeting's recording folder, atomically (temp file + rename), matching
/// the convention recording_saver.rs already uses for transcripts.json.
///
/// summary.json is written LAST and is the sentinel the sync sweep
/// (sync_pushed_meetings) and get_saved_summary both use to decide a
/// summary already exists -- if the process died between the two
/// writes with json written first, the sentinel would be satisfied
/// while summary.md never landed, and nothing would ever retry it.
fn write_summary_files(folder: &std::path::Path, summary: &serde_json::Value) -> std::io::Result<()> {
    let md_path = folder.join("summary.md");
    let md_temp = folder.join(".summary.md.tmp");
    std::fs::write(&md_temp, format_summary_markdown(summary))?;
    std::fs::rename(&md_temp, &md_path)?;

    let json_path = folder.join("summary.json");
    let json_temp = folder.join(".summary.json.tmp");
    std::fs::write(&json_temp, serde_json::to_string_pretty(summary).unwrap_or_default())?;
    std::fs::rename(&json_temp, &json_path)?;

    Ok(())
}

const SUMMARY_LIST_SECTIONS: &[(&str, &str)] = &[
    ("discussion_topics", "Discussion Topics"),
    ("action_items", "Action Items"),
    ("decisions", "Decisions"),
    ("open_questions", "Open Questions"),
    ("risks", "Risks"),
    ("keywords", "Keywords"),
];

/// Mirrors app.delivery.service._format_slack_text on the backend, so
/// the on-disk summary reads the same way the Slack message does.
fn format_summary_markdown(summary: &serde_json::Value) -> String {
    let mut lines = vec!["# Meeting Summary".to_string()];
    if let Some(exec) = summary.get("executive_summary").and_then(|v| v.as_str()) {
        lines.push(String::new());
        lines.push(exec.to_string());
    }
    for (key, heading) in SUMMARY_LIST_SECTIONS {
        if let Some(items) = summary.get(*key).and_then(|v| v.as_array()) {
            if items.is_empty() {
                continue;
            }
            lines.push(String::new());
            lines.push(format!("## {}", heading));
            for item in items {
                if let Some(text) = item.as_str() {
                    lines.push(format!("- {}", text));
                }
            }
        }
    }
    lines.join("\n")
}

/// Reads back the summary.json written by get_push_status for a meeting
/// that's already been pushed and summarized, so reopening it (e.g. via
/// a sidebar folder) can show the summary without re-polling the backend.
/// Returns None if the meeting has no folder, or no summary was ever saved.
#[tauri::command]
pub async fn get_saved_summary(
    state: tauri::State<'_, AppState>,
    meeting_id: String,
) -> Result<Option<serde_json::Value>, String> {
    let pool = state.db_manager.pool();
    let meeting = MeetingsRepository::get_meeting_metadata(pool, &meeting_id)
        .await
        .map_err(|e| format!("Failed to load meeting {}: {}", meeting_id, e))?
        .ok_or_else(|| format!("Meeting {} not found", meeting_id))?;

    let Some(folder_path) = meeting.folder_path else {
        return Ok(None);
    };
    let summary_path = std::path::PathBuf::from(folder_path).join("summary.json");
    if !summary_path.exists() {
        return Ok(None);
    }

    let contents = std::fs::read_to_string(&summary_path)
        .map_err(|e| format!("Failed to read {}: {}", summary_path.display(), e))?;
    let summary = serde_json::from_str(&contents)
        .map_err(|e| format!("Failed to parse {}: {}", summary_path.display(), e))?;
    Ok(Some(summary))
}

// ---------------------------------------------------------------------------
// Buyer/seller tag (push_tag column)
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn update_meeting_tag(
    state: tauri::State<'_, AppState>,
    meeting_id: String,
    tag: String,
) -> Result<bool, String> {
    let pool = state.db_manager.pool();
    MeetingsRepository::update_meeting_push_tag(pool, &meeting_id, &tag)
        .await
        .map_err(|e| format!("Failed to update tag for meeting {}: {}", meeting_id, e))
}

// ---------------------------------------------------------------------------
// Sync: recovers summaries the manual "Check" button never reached --
// on app launch and on a background timer (see lib.rs). Keyed on
// install_id (the only per-device identity that's actually persisted,
// in push_config.json) rather than a per-meeting remote id, so it also
// recovers meetings pushed before this sweep existed.
// ---------------------------------------------------------------------------

/// Deserialized from GET /desktop/meetings -- mirrors
/// app.desktop.schemas.DesktopMeetingSyncItem. Deliberately carries no
/// summary body (see that schema's docstring): summary_available lets
/// this stay a single cheap indexed query server-side, safe to poll.
#[derive(Debug, Deserialize)]
struct SyncListItem {
    meeting_id: String,
    local_recording_id: String,
    summary_available: bool,
}

#[derive(Debug, Deserialize)]
struct SyncListResponse {
    meetings: Vec<SyncListItem>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SyncAction {
    Skip,
    LocalFillOnly,
    FetchAndFill,
}

/// The whole "never overwrite" decision, isolated as a pure function so
/// it's testable with no pool, no AppHandle, no network:
/// - no summary on the server yet (or return_summary=false) -> Skip
/// - no local recording folder -> Skip (nowhere to file it)
/// - folder exists but summary.json is already there -> LocalFillOnly
///   (title/pushed_at may still need filling, but never re-fetch/overwrite)
/// - folder exists and summary.json is absent -> FetchAndFill
fn plan_sync(summary_available: bool, folder_exists: bool, summary_json_exists: bool) -> SyncAction {
    if !summary_available || !folder_exists {
        return SyncAction::Skip;
    }
    if summary_json_exists {
        SyncAction::LocalFillOnly
    } else {
        SyncAction::FetchAndFill
    }
}

/// Caps GET /desktop/meetings/{id} calls per sync run -- the first sync
/// after shipping this could otherwise find dozens of meetings missing
/// summaries and burst-fetch all of them at once. The remainder drains
/// over subsequent ticks.
const MAX_FETCHES_PER_SYNC: usize = 5;

static SYNC_IN_PROGRESS: AtomicBool = AtomicBool::new(false);

/// RAII guard mirroring RetranscriptionGuard (audio/retranscription.rs)
/// -- prevents the launch sync and a background tick (or two ticks)
/// from racing each other over the same SQLite writes.
struct SyncGuard;

impl SyncGuard {
    fn acquire() -> Option<Self> {
        if SYNC_IN_PROGRESS
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return None;
        }
        Some(SyncGuard)
    }
}

impl Drop for SyncGuard {
    fn drop(&mut self) {
        SYNC_IN_PROGRESS.store(false, Ordering::SeqCst);
    }
}

#[derive(Debug, Serialize)]
pub struct SyncResult {
    pub checked: usize,
    pub synced: usize,
    /// True if this call did no work because another sync was already
    /// running, or because push isn't configured / app state isn't
    /// ready yet (e.g. first launch before database import completes).
    /// Never an error -- sync is unattended background work and must
    /// never surface a toast on its own.
    pub skipped: bool,
    /// Set only on a genuine failure to reach or parse the server's
    /// response, so the manual "Check now" button can show it -- the
    /// background timer ignores this field entirely.
    pub error: Option<String>,
}

impl SyncResult {
    fn skipped() -> Self {
        Self { checked: 0, synced: 0, skipped: true, error: None }
    }

    fn failed(error: String) -> Self {
        Self { checked: 0, synced: 0, skipped: false, error: Some(error) }
    }
}

/// Reconciles this install's local meetings against the server's view
/// of them. Every failure path is non-fatal (see SyncResult::error) --
/// this command is called unattended on every app launch and every
/// background tick, so it must never reject/toast on its own.
#[tauri::command]
pub async fn sync_pushed_meetings<R: Runtime>(app: AppHandle<R>) -> Result<SyncResult, String> {
    let Some(_guard) = SyncGuard::acquire() else {
        return Ok(SyncResult::skipped());
    };

    // First launch: AppState isn't managed until database import/setup
    // completes (see database/setup.rs). Not an error -- the next tick,
    // or the manual "Check now" button once the app is ready, retries.
    let Some(app_state) = app.try_state::<AppState>() else {
        return Ok(SyncResult::skipped());
    };
    let pool = app_state.db_manager.pool();

    let config = load_push_config(&app);
    if config.server_url.trim().is_empty() {
        return Ok(SyncResult::skipped());
    }

    let client = match reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
    {
        Ok(c) => c,
        Err(e) => return Ok(SyncResult::failed(format!("Failed to create HTTP client: {}", e))),
    };

    let list_url = format!("{}/desktop/meetings", config.server_url.trim_end_matches('/'));
    let mut list_request = client.get(&list_url).query(&[("install_id", config.install_id.as_str())]);
    if !config.api_key.trim().is_empty() {
        list_request = list_request.header("Authorization", format!("Bearer {}", config.api_key));
    }

    let response = match list_request.send().await {
        Ok(r) => r,
        Err(e) => {
            warn!("sync_pushed_meetings: failed to reach {}: {}", list_url, e);
            return Ok(SyncResult::failed(format!("Failed to reach {}: {}", list_url, e)));
        }
    };
    let status = response.status();
    let response_text = response.text().await.unwrap_or_default();
    if !status.is_success() {
        warn!("sync_pushed_meetings: list failed ({}): {}", status, response_text);
        return Ok(SyncResult::failed(format!("Sync failed ({}): {}", status, response_text)));
    }
    let remote: SyncListResponse = match serde_json::from_str(&response_text) {
        Ok(parsed) => parsed,
        Err(e) => {
            warn!("sync_pushed_meetings: unexpected list response shape: {}", e);
            return Ok(SyncResult::failed(
                "Sync server returned an unexpected response".to_string(),
            ));
        }
    };

    let local: Vec<MeetingModel> = match MeetingsRepository::list_all_metadata(pool).await {
        Ok(rows) => rows,
        Err(e) => {
            warn!("sync_pushed_meetings: failed to load local meetings: {}", e);
            return Ok(SyncResult::failed(e.to_string()));
        }
    };
    let local_by_recording_id: HashMap<&str, &MeetingModel> =
        local.iter().map(|m| (m.id.as_str(), m)).collect();

    let mut checked = 0usize;
    let mut synced = 0usize;
    let mut fetches_used = 0usize;

    for item in &remote.meetings {
        let Some(meeting) = local_by_recording_id.get(item.local_recording_id.as_str()) else {
            continue;
        };
        let folder_exists = meeting
            .folder_path
            .as_deref()
            .map(|p| std::path::Path::new(p).exists())
            .unwrap_or(false);
        let summary_json_exists = meeting
            .folder_path
            .as_deref()
            .map(|p| std::path::Path::new(p).join("summary.json").exists())
            .unwrap_or(false);

        checked += 1;

        match plan_sync(item.summary_available, folder_exists, summary_json_exists) {
            SyncAction::Skip => {}
            SyncAction::LocalFillOnly => {
                // summary.json already landed (a prior manual check, or
                // an earlier sync run) but the title/pushed_at fill may
                // not have -- e.g. usePush's own best-effort title save
                // failed, or the app was killed before mark_meeting_pushed
                // ran. Idempotent, no network involved either way.
                if let Some(folder_path) = &meeting.folder_path {
                    let summary_path = std::path::Path::new(folder_path).join("summary.json");
                    if let Ok(contents) = std::fs::read_to_string(&summary_path) {
                        if let Ok(summary) = serde_json::from_str::<serde_json::Value>(&contents) {
                            apply_local_summary_fills(
                                pool,
                                &meeting.id,
                                &summary,
                                &meeting.title,
                                meeting.pushed_at.as_deref(),
                            )
                            .await;
                        }
                    }
                }
            }
            SyncAction::FetchAndFill => {
                if fetches_used >= MAX_FETCHES_PER_SYNC {
                    continue; // drained by a later tick
                }
                fetches_used += 1;
                match fetch_meeting_status(&client, &config, &item.meeting_id).await {
                    Ok(fetched) => {
                        if let Some(summary) = &fetched.summary {
                            store_summary_for_meeting(pool, &meeting.id, summary).await;
                            synced += 1;
                        }
                    }
                    Err(e) => warn!(
                        "sync_pushed_meetings: failed to fetch summary for {}: {}",
                        item.meeting_id, e
                    ),
                }
            }
        }
    }

    Ok(SyncResult { checked, synced, skipped: false, error: None })
}

#[cfg(test)]
mod sync_tests {
    use super::*;

    #[test]
    fn plan_sync_skips_when_summary_not_available() {
        assert_eq!(plan_sync(false, true, false), SyncAction::Skip);
        assert_eq!(plan_sync(false, true, true), SyncAction::Skip);
    }

    #[test]
    fn plan_sync_skips_when_no_local_folder() {
        assert_eq!(plan_sync(true, false, false), SyncAction::Skip);
        assert_eq!(plan_sync(true, false, true), SyncAction::Skip);
    }

    #[test]
    fn plan_sync_never_refetches_once_summary_json_exists() {
        assert_eq!(plan_sync(true, true, true), SyncAction::LocalFillOnly);
    }

    #[test]
    fn plan_sync_fetches_when_missing_locally() {
        assert_eq!(plan_sync(true, true, false), SyncAction::FetchAndFill);
    }

    #[test]
    fn strip_role_bracket_prefix_removes_single_prefix() {
        assert_eq!(strip_role_bracket_prefix("[Seller: Acme] Q3 review"), "Q3 review");
    }

    #[test]
    fn strip_role_bracket_prefix_removes_stacked_prefixes() {
        assert_eq!(
            strip_role_bracket_prefix("[Seller: Acme] [Buyer: X] Q3 review"),
            "Q3 review"
        );
    }

    #[test]
    fn strip_role_bracket_prefix_is_case_insensitive() {
        assert_eq!(strip_role_bracket_prefix("[seller: Acme] Q3 review"), "Q3 review");
    }

    #[test]
    fn strip_role_bracket_prefix_leaves_untagged_title_unchanged() {
        assert_eq!(strip_role_bracket_prefix("Q3 review"), "Q3 review");
    }

    #[test]
    fn strip_role_bracket_prefix_handles_prefix_only_string() {
        assert_eq!(strip_role_bracket_prefix("[Buyer: Acme]"), "");
    }

    #[test]
    fn is_placeholder_title_matches_recording_default() {
        assert!(is_placeholder_title("Meeting 2026-08-20_17-42-02"));
    }

    #[test]
    fn is_placeholder_title_rejects_real_titles() {
        assert!(!is_placeholder_title("Q3 Renewal Call"));
        assert!(!is_placeholder_title("Meeting notes 2026-08-20"));
    }

    #[test]
    fn sync_guard_blocks_reentrant_acquire_and_releases_on_drop() {
        let first = SyncGuard::acquire();
        assert!(first.is_some());
        assert!(SyncGuard::acquire().is_none());
        drop(first);
        assert!(SyncGuard::acquire().is_some());
    }

    #[test]
    fn write_summary_files_writes_markdown_before_json() {
        let dir = tempfile::tempdir().unwrap();
        let summary = serde_json::json!({"executive_summary": "done"});
        write_summary_files(dir.path(), &summary).unwrap();
        assert!(dir.path().join("summary.md").exists());
        assert!(dir.path().join("summary.json").exists());
    }
}
