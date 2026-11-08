// diarization/overview.rs
//
// Who spoke in a meeting, for naming every voice in one place instead of line by line.

use serde::Serialize;

use super::assign::{match_profiles, VoiceProfile};
use super::SpeakerLabel;
use crate::database::repositories::speaker::{VoiceOverviewRow, VoiceSample};

// Below the auto-name threshold the voice may still be this person: the user confirms with one click.
pub const SUGGESTION_THRESHOLD: f32 = 0.5;

/// A saved person, as the overview needs them.
pub struct NamedProfile {
    pub id: String,
    pub name: String,
    pub embedding: Vec<f32>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SpeakerSuggestion {
    pub profile_id: String,
    pub name: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SpeakerOverview {
    pub label: SpeakerLabel,
    pub name: Option<String>,
    pub line_count: i64,
    pub talk_seconds: f64,
    pub sample: Option<VoiceSample>,
    pub suggestion: Option<SpeakerSuggestion>,
}

/// Voices ordered by talk time, each unnamed one with the closest person not already in this meeting.
pub fn build_overview(voices: Vec<VoiceOverviewRow>, profiles: &[NamedProfile]) -> Vec<SpeakerOverview> {
    let linked: Vec<&str> = voices.iter().filter_map(|v| v.profile_id.as_deref()).collect();
    let available: Vec<&NamedProfile> = profiles.iter().filter(|p| !linked.contains(&p.id.as_str())).collect();
    let candidates: Vec<VoiceProfile> = available
        .iter()
        .map(|p| VoiceProfile { id: p.id.clone(), embedding: p.embedding.clone() })
        .collect();

    let unnamed: Vec<usize> = (0..voices.len())
        .filter(|&i| voices[i].profile_id.is_none() && !voices[i].embedding.is_empty())
        .collect();
    let centroids: Vec<Vec<f32>> = unnamed.iter().map(|&i| voices[i].embedding.clone()).collect();
    let matches = match_profiles(&centroids, &candidates, SUGGESTION_THRESHOLD);

    let mut suggestions: Vec<Option<SpeakerSuggestion>> = vec![None; voices.len()];
    for (&voice, matched) in unnamed.iter().zip(matches) {
        suggestions[voice] = matched.and_then(|id| {
            available
                .iter()
                .find(|p| p.id == id)
                .map(|p| SpeakerSuggestion { profile_id: p.id.clone(), name: p.name.clone() })
        });
    }

    let mut overview: Vec<SpeakerOverview> = voices
        .into_iter()
        .zip(suggestions)
        .map(|(voice, suggestion)| SpeakerOverview {
            label: voice.label,
            name: voice.name,
            line_count: voice.line_count,
            talk_seconds: voice.talk_seconds,
            sample: voice.sample,
            suggestion,
        })
        .collect();
    overview.sort_by(|a, b| b.talk_seconds.total_cmp(&a.talk_seconds));
    overview
}

#[cfg(test)]
mod tests {
    use super::*;

    fn voice(n: u32, embedding: Vec<f32>, profile_id: Option<&str>, talk_seconds: f64) -> VoiceOverviewRow {
        VoiceOverviewRow {
            label: SpeakerLabel::Speaker(n),
            profile_id: profile_id.map(str::to_string),
            name: profile_id.map(|_| "Named".to_string()),
            embedding,
            line_count: 1,
            talk_seconds,
            sample: None,
        }
    }

    fn profile(id: &str, embedding: Vec<f32>) -> NamedProfile {
        NamedProfile { id: id.to_string(), name: id.to_uppercase(), embedding }
    }

    #[test]
    fn orders_by_talk_time() {
        let overview = build_overview(vec![voice(0, vec![1.0], None, 3.0), voice(1, vec![1.0], None, 9.0)], &[]);
        assert_eq!(overview[0].label, SpeakerLabel::Speaker(1));
    }

    #[test]
    fn suggests_a_near_match_but_never_a_distant_one() {
        // cos ~0.6 for the first voice, ~0.0 for the second.
        let profiles = [profile("faisal", vec![0.6, 0.8])];
        let overview = build_overview(
            vec![voice(0, vec![1.0, 0.0], None, 5.0), voice(1, vec![-0.8, 0.6], None, 4.0)],
            &profiles,
        );
        assert_eq!(overview[0].suggestion.as_ref().unwrap().name, "FAISAL");
        assert!(overview[1].suggestion.is_none());
    }

    #[test]
    fn never_suggests_someone_already_in_the_meeting_or_for_a_named_voice() {
        let profiles = [profile("faisal", vec![1.0, 0.0])];
        let overview = build_overview(
            vec![voice(0, vec![1.0, 0.0], Some("faisal"), 5.0), voice(1, vec![1.0, 0.0], None, 4.0)],
            &profiles,
        );
        assert!(overview.iter().all(|v| v.suggestion.is_none()));
    }
}
