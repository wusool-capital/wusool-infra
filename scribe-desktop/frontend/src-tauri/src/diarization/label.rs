// diarization/label.rs
//
// The speaker key stored on every transcript segment. It is a stable key, not a display
// name: names are resolved through the meeting's speaker map so a rename touches one row.

use std::fmt;
use std::str::FromStr;

use serde::{Deserialize, Serialize};

use crate::audio::recording_state::DeviceType;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub enum SpeakerLabel {
    /// The local user, captured from the microphone.
    Me,
    /// Meeting audio that has not been diarized yet.
    Others,
    /// One diarized voice from the meeting audio, numbered per meeting.
    Speaker(u32),
}

impl SpeakerLabel {
    pub fn from_source(device_type: &DeviceType) -> Self {
        match device_type {
            DeviceType::Microphone => Self::Me,
            DeviceType::System => Self::Others,
        }
    }
}

impl fmt::Display for SpeakerLabel {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Me => f.write_str("me"),
            Self::Others => f.write_str("others"),
            Self::Speaker(n) => write!(f, "speaker_{n}"),
        }
    }
}

#[derive(Debug, thiserror::Error)]
#[error("unknown speaker label: {0}")]
pub struct InvalidSpeakerLabel(String);

impl FromStr for SpeakerLabel {
    type Err = InvalidSpeakerLabel;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            // "mic"/"system" were written by an earlier schema comment and test fixtures.
            "me" | "mic" => Ok(Self::Me),
            "others" | "system" => Ok(Self::Others),
            _ => value
                .strip_prefix("speaker_")
                .and_then(|n| n.parse().ok())
                .map(Self::Speaker)
                .ok_or_else(|| InvalidSpeakerLabel(value.to_string())),
        }
    }
}

impl TryFrom<String> for SpeakerLabel {
    type Error = InvalidSpeakerLabel;

    fn try_from(value: String) -> Result<Self, Self::Error> {
        value.parse()
    }
}

impl From<SpeakerLabel> for String {
    fn from(label: SpeakerLabel) -> Self {
        label.to_string()
    }
}

impl sqlx::Type<sqlx::Sqlite> for SpeakerLabel {
    fn type_info() -> sqlx::sqlite::SqliteTypeInfo {
        <String as sqlx::Type<sqlx::Sqlite>>::type_info()
    }
}

impl<'q> sqlx::Encode<'q, sqlx::Sqlite> for SpeakerLabel {
    fn encode_by_ref(
        &self,
        buf: &mut Vec<sqlx::sqlite::SqliteArgumentValue<'q>>,
    ) -> Result<sqlx::encode::IsNull, sqlx::error::BoxDynError> {
        <String as sqlx::Encode<'q, sqlx::Sqlite>>::encode(self.to_string(), buf)
    }
}

impl<'r> sqlx::Decode<'r, sqlx::Sqlite> for SpeakerLabel {
    fn decode(value: sqlx::sqlite::SqliteValueRef<'r>) -> Result<Self, sqlx::error::BoxDynError> {
        let text = <&str as sqlx::Decode<'r, sqlx::Sqlite>>::decode(value)?;
        Ok(text.parse()?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_through_string() {
        for label in [SpeakerLabel::Me, SpeakerLabel::Others, SpeakerLabel::Speaker(3)] {
            assert_eq!(label.to_string().parse::<SpeakerLabel>().unwrap(), label);
        }
    }

    #[test]
    fn accepts_legacy_source_values() {
        assert_eq!("mic".parse::<SpeakerLabel>().unwrap(), SpeakerLabel::Me);
        assert_eq!("system".parse::<SpeakerLabel>().unwrap(), SpeakerLabel::Others);
    }

    #[test]
    fn rejects_unknown_values() {
        assert!("speaker_x".parse::<SpeakerLabel>().is_err());
        assert!("Alice".parse::<SpeakerLabel>().is_err());
    }

    #[test]
    fn serializes_as_plain_string() {
        assert_eq!(serde_json::to_string(&SpeakerLabel::Speaker(0)).unwrap(), "\"speaker_0\"");
        let parsed: SpeakerLabel = serde_json::from_str("\"me\"").unwrap();
        assert_eq!(parsed, SpeakerLabel::Me);
    }
}
