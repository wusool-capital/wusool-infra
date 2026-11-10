// diarization/assign.rs
//
// Pure attribution logic, free of I/O so it tests directly: segments to voices, voices to people.

/// A span of meeting audio attributed to one diarized voice, in seconds.
#[derive(Debug, Clone, Copy, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct SpeakerTurn {
    pub start: f64,
    pub end: f64,
    pub speaker: u32,
}

/// A saved voice the user has named.
#[derive(Debug, Clone, PartialEq)]
pub struct VoiceProfile {
    pub id: String,
    pub embedding: Vec<f32>,
}

// Same-person WeSpeaker scores sit well above this. Raising it trades wrong names for unnamed voices.
pub const PROFILE_MATCH_THRESHOLD: f32 = 0.7;
// Auto-naming also needs a clear winner: a voice almost as close to a second
// person is left unnamed, and the overview offers the closest one to confirm.
pub const PROFILE_MATCH_MARGIN: f32 = 0.1;

/// The voice that overlaps a segment the most, or `None` if no turn overlaps it.
pub fn dominant_speaker(start: f64, end: f64, turns: &[SpeakerTurn]) -> Option<u32> {
    dominant_label(start, end, turns.iter().map(|t| (t.start, t.end, t.speaker)))
}

/// The label whose spans overlap `start..end` the most, summed across spans.
pub fn dominant_label<L: Copy + PartialEq>(
    start: f64,
    end: f64,
    spans: impl IntoIterator<Item = (f64, f64, L)>,
) -> Option<L> {
    let mut overlap_by_label: Vec<(L, f64)> = Vec::new();
    for (span_start, span_end, label) in spans {
        let overlap = end.min(span_end) - start.max(span_start);
        if overlap <= 0.0 {
            continue;
        }
        match overlap_by_label.iter_mut().find(|(l, _)| *l == label) {
            Some((_, total)) => *total += overlap,
            None => overlap_by_label.push((label, overlap)),
        }
    }
    overlap_by_label
        .into_iter()
        .max_by(|a, b| a.1.total_cmp(&b.1))
        .map(|(label, _)| label)
}

/// Which label each transcript segment gets, and which diarized cluster each label is.
#[derive(Debug, PartialEq)]
pub struct Attribution {
    /// Per segment: the index `n` of its `SpeakerLabel::Speaker(n)`, if any voice overlaps it.
    pub segment_labels: Vec<Option<u32>>,
    /// Per label index: the diarization cluster it came from.
    pub label_clusters: Vec<u32>,
}

/// Attributes time-ordered segments to voices, numbered by first appearance; clusters owning no segment get no label.
pub fn attribute_segments(segments: &[(f64, f64)], turns: &[SpeakerTurn]) -> Attribution {
    let mut label_clusters: Vec<u32> = Vec::new();
    let segment_labels = segments
        .iter()
        .map(|&(start, end)| {
            let cluster = dominant_speaker(start, end, turns)?;
            let index = match label_clusters.iter().position(|&c| c == cluster) {
                Some(index) => index,
                None => {
                    label_clusters.push(cluster);
                    label_clusters.len() - 1
                }
            };
            Some(index as u32)
        })
        .collect();
    Attribution { segment_labels, label_clusters }
}

/// The matching saved profile per voice, one-to-one, strongest pairs first, so two voices never share a name.
/// A voice whose best score beats its second-best person by less than `margin` gets none.
pub fn match_profiles(
    centroids: &[Vec<f32>],
    profiles: &[VoiceProfile],
    threshold: f32,
    margin: f32,
) -> Vec<Option<String>> {
    let mut candidates: Vec<(usize, usize, f32)> = Vec::new();
    for (voice, centroid) in centroids.iter().enumerate() {
        let scores: Vec<f32> = profiles.iter().map(|saved| cosine_similarity(centroid, &saved.embedding)).collect();
        let Some((best, &best_score)) = scores.iter().enumerate().max_by(|a, b| a.1.total_cmp(b.1)) else {
            continue;
        };
        let runner_up = scores
            .iter()
            .enumerate()
            .filter(|&(profile, _)| profile != best)
            .map(|(_, &score)| score)
            .fold(f32::NEG_INFINITY, f32::max);
        if best_score - runner_up < margin {
            continue;
        }
        for (profile, &score) in scores.iter().enumerate() {
            if score >= threshold {
                candidates.push((voice, profile, score));
            }
        }
    }
    candidates.sort_by(|a, b| b.2.total_cmp(&a.2));

    let mut matches = vec![None; centroids.len()];
    let mut used_profiles = vec![false; profiles.len()];
    for (voice, profile, _) in candidates {
        if matches[voice].is_none() && !used_profiles[profile] {
            matches[voice] = Some(profiles[profile].id.clone());
            used_profiles[profile] = true;
        }
    }
    matches
}

pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() {
        return 0.0;
    }
    let dot: f32 = a.iter().zip(b).map(|(x, y)| x * y).sum();
    let norm = a.iter().map(|x| x * x).sum::<f32>().sqrt() * b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm == 0.0 { 0.0 } else { dot / norm }
}

/// Mean of the usable samples; empty or odd-sized ones are skipped so a bad sample never blanks a profile.
pub fn mean_embedding(samples: &[Vec<f32>]) -> Option<Vec<f32>> {
    let dim = samples.iter().map(Vec::len).find(|&len| len > 0)?;
    let usable: Vec<&Vec<f32>> = samples.iter().filter(|s| s.len() == dim).collect();
    let mut sum = vec![0.0f32; dim];
    for sample in &usable {
        for (total, value) in sum.iter_mut().zip(sample.iter()) {
            *total += value;
        }
    }
    Some(sum.into_iter().map(|x| x / usable.len() as f32).collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn turn(start: f64, end: f64, speaker: u32) -> SpeakerTurn {
        SpeakerTurn { start, end, speaker }
    }

    #[test]
    fn picks_speaker_with_most_overlap() {
        let turns = [turn(0.0, 4.0, 0), turn(4.0, 10.0, 1)];
        assert_eq!(dominant_speaker(3.0, 8.0, &turns), Some(1));
        assert_eq!(dominant_speaker(0.5, 4.5, &turns), Some(0));
    }

    #[test]
    fn sums_overlap_across_split_turns() {
        let turns = [turn(0.0, 1.0, 0), turn(1.0, 2.5, 1), turn(2.5, 4.0, 0)];
        assert_eq!(dominant_speaker(0.0, 4.0, &turns), Some(0));
    }

    #[test]
    fn no_overlap_means_no_speaker() {
        assert_eq!(dominant_speaker(5.0, 6.0, &[turn(0.0, 4.0, 0)]), None);
    }

    #[test]
    fn numbers_voices_by_first_appearance_and_skips_unused_clusters() {
        let turns = [turn(0.0, 2.0, 4), turn(2.0, 4.0, 1), turn(4.0, 6.0, 4), turn(9.0, 9.5, 7)];
        let segments = [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0), (6.5, 8.0)];
        assert_eq!(
            attribute_segments(&segments, &turns),
            Attribution {
                segment_labels: vec![Some(0), Some(1), Some(0), None],
                label_clusters: vec![4, 1],
            }
        );
    }

    #[test]
    fn matches_profiles_above_threshold_only() {
        let profiles = vec![
            VoiceProfile { id: "alice".into(), embedding: vec![1.0, 0.0] },
            VoiceProfile { id: "bob".into(), embedding: vec![0.0, 1.0] },
        ];
        let centroids = vec![vec![0.9, 0.1], vec![0.7, 0.7], vec![0.1, 0.95]];
        assert_eq!(
            match_profiles(&centroids, &profiles, 0.9, 0.0),
            vec![Some("alice".into()), None, Some("bob".into())]
        );
    }

    #[test]
    fn never_gives_two_voices_the_same_profile() {
        let profiles = vec![VoiceProfile { id: "alice".into(), embedding: vec![1.0, 0.0] }];
        let centroids = vec![vec![0.95, 0.05], vec![1.0, 0.0]];
        assert_eq!(match_profiles(&centroids, &profiles, 0.5, 0.0), vec![None, Some("alice".into())]);
    }

    #[test]
    fn mean_ignores_empty_and_mismatched_samples() {
        let samples = vec![vec![1.0, 0.0], vec![], vec![0.0, 1.0], vec![9.0]];
        assert_eq!(mean_embedding(&samples), Some(vec![0.5, 0.5]));
        assert_eq!(mean_embedding(&[vec![]]), None);
    }

    #[test]
    fn dominant_label_works_for_any_label_type() {
        let spans = [(0.0, 2.0, "me"), (2.0, 5.0, "speaker_0")];
        assert_eq!(dominant_label(1.0, 4.0, spans), Some("speaker_0"));
    }

    #[test]
    fn match_profiles_leaves_a_voice_unnamed_when_two_people_are_close() {
        let profiles = vec![
            VoiceProfile { id: "alice".into(), embedding: vec![1.0, 0.0] },
            VoiceProfile { id: "bea".into(), embedding: vec![0.96, 0.28] },
        ];
        // Both people score above the threshold, within the margin of each other.
        let centroids = vec![vec![0.99, 0.12]];
        assert_eq!(match_profiles(&centroids, &profiles, 0.7, PROFILE_MATCH_MARGIN), vec![None]);
        let clear = vec![vec![1.0, -0.3]];
        assert_eq!(match_profiles(&clear, &profiles, 0.7, PROFILE_MATCH_MARGIN), vec![Some("alice".into())]);
    }

}
