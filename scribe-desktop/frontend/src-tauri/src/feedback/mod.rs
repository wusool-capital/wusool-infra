//! Sends user feedback to the Scribe backend's `POST /desktop/feedback`
//! route, which relays it by email via SES -- this app has no email
//! credential of its own. Reuses push_config.json's
//! server_url/api_key/install_id: feedback has no separate destination.
//! The webview's CSP pins connect-src to localhost, so this call must
//! originate here in Rust.

use log::warn;
use serde::Serialize;
use tauri::{AppHandle, Runtime};

use crate::push::load_push_config;

const MAX_MESSAGE_CHARS: usize = 4000;
const MAX_CONTACT_CHARS: usize = 200;
const CATEGORIES: [&str; 4] = ["bug", "feature_request", "transcription_quality", "other"];

#[derive(Debug, Serialize)]
struct FeedbackRequest {
    install_id: String,
    category: String,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    contact: Option<String>,
    app_version: String,
    platform: String,
}

/// Pure, so it's testable without a network call or an AppHandle.
fn validate(category: &str, message: &str, contact: &str) -> Result<(), String> {
    if !CATEGORIES.contains(&category) {
        return Err("Unknown feedback category.".to_string());
    }
    if message.trim().is_empty() {
        return Err("Please describe your feedback.".to_string());
    }
    if message.chars().count() > MAX_MESSAGE_CHARS {
        return Err(format!(
            "Feedback is limited to {} characters.",
            MAX_MESSAGE_CHARS
        ));
    }
    if contact.chars().count() > MAX_CONTACT_CHARS {
        return Err("Contact field is too long.".to_string());
    }
    Ok(())
}

#[tauri::command]
pub async fn submit_feedback<R: Runtime>(
    app: AppHandle<R>,
    category: String,
    message: String,
    contact: String,
) -> Result<(), String> {
    validate(&category, &message, &contact)?;

    let config = load_push_config(&app);
    if config.server_url.trim().is_empty() || config.api_key.trim().is_empty() {
        return Err(
            "Feedback needs a configured server. Set the Push destination in Settings first."
                .to_string(),
        );
    }

    let body = FeedbackRequest {
        install_id: config.install_id,
        category,
        message: message.trim().to_string(),
        contact: Some(contact.trim().to_string()).filter(|c| !c.is_empty()),
        app_version: env!("CARGO_PKG_VERSION").to_string(),
        platform: format!("{} {}", std::env::consts::OS, std::env::consts::ARCH),
    };

    let url = format!(
        "{}/desktop/feedback",
        config.server_url.trim_end_matches('/')
    );
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let response = client
        .post(&url)
        .header("Authorization", format!("Bearer {}", config.api_key))
        .json(&body)
        .send()
        .await
        .map_err(|e| {
            // reqwest's chain ("dns error: nodename nor servname...") is
            // noise in a toast -- keep it in the log, same as
            // verify_push_config (push/mod.rs).
            warn!("submit_feedback: request to {} failed: {}", url, e);
            "Could not reach the server. Check your connection and try again.".to_string()
        })?;

    let status = response.status();
    if status == reqwest::StatusCode::UNAUTHORIZED {
        return Err("API key was rejected by the server.".to_string());
    }
    if status == reqwest::StatusCode::TOO_MANY_REQUESTS {
        return Err("Too many feedback submissions -- please try again later.".to_string());
    }
    if status == reqwest::StatusCode::SERVICE_UNAVAILABLE {
        return Err("Feedback delivery isn't configured on the server yet.".to_string());
    }
    if !status.is_success() {
        warn!(
            "submit_feedback: {} returned {}: {}",
            url,
            status,
            response.text().await.unwrap_or_default()
        );
        return Err(format!("Server returned {}.", status));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validate_rejects_unknown_category() {
        assert!(validate("spam", "hello", "").is_err());
    }

    #[test]
    fn validate_rejects_empty_message() {
        assert!(validate("bug", "", "").is_err());
    }

    #[test]
    fn validate_rejects_whitespace_only_message() {
        assert!(validate("bug", "   \n\t  ", "").is_err());
    }

    #[test]
    fn validate_rejects_overlong_message() {
        let message = "a".repeat(MAX_MESSAGE_CHARS + 1);
        assert!(validate("bug", &message, "").is_err());
    }

    #[test]
    fn validate_accepts_message_at_the_limit() {
        let message = "a".repeat(MAX_MESSAGE_CHARS);
        assert!(validate("bug", &message, "").is_ok());
    }

    #[test]
    fn validate_counts_chars_not_bytes() {
        // Each 'é' is 2 bytes but 1 char -- must not reject at the byte count.
        let message = "é".repeat(MAX_MESSAGE_CHARS);
        assert!(validate("bug", &message, "").is_ok());
    }

    #[test]
    fn validate_accepts_every_known_category() {
        for category in CATEGORIES {
            assert!(validate(category, "hello", "").is_ok());
        }
    }

    #[test]
    fn validate_rejects_overlong_contact() {
        let contact = "a".repeat(MAX_CONTACT_CHARS + 1);
        assert!(validate("bug", "hello", &contact).is_err());
    }
}
