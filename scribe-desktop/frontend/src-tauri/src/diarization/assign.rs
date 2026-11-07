// diarization/assign.rs
//
// Pure attribution logic: map transcript segments onto diarized turns, and diarized voices
// onto the user's voice library. Kept free of I/O so it can be tested directly.

/// A span of meeting audio attributed to one diarized voice, in seconds.
#[derive(Debug, Clone, Copy, PartialEq)]
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

// WeSpeaker embeddings of the same person usually score well above this; distinct voices
// rarely do. Higher means fewer wrong auto-names at the cost of more unnamed speakers.
pub const PROFILE_MATCH_THRESHOLD: f32 = 0.7;

/// The voice that overlaps a segment the most, or `None` if no turn overlaps it.
pub fn dominant_speaker(start: f64, end: f64, turns: &[SpeakerTurn]) -> Option<u32> {
    let mut overlap_by_speaker: Vec<(u32, f64)> = Vec::new();
    for turn in turns {
        let overlap = end.min(turn.end) - start.max(turn.start);
        if overlap <= 0.0 {
            continue;
        }
        match overlap_by_speaker.iter_mut().find(|(s, _)| *s == turn.speaker) {
            Some((_, total)) => *total += overlap,
            None => overlap_by_speaker.push((turn.speaker, overlap)),
        }
    }
    overlap_by_speaker
        .into_iter()
        .max_by(|a, b| a.1.total_cmp(&b.1))
        .map(|(speaker, _)| speaker)
}

/// Which label each transcript segment gets, and which diarized cluster each label is.
#[derive(Debug, PartialEq)]
pub struct Attribution {
    /// Per segment: the index `n` of its `SpeakerLabel::Speaker(n)`, if any voice overlaps it.
    pub segment_labels: Vec<Option<u32>>,
    /// Per label index: the diarization cluster it came from.
    pub label_clusters: Vec<u32>,
}

/// Attributes segments (ordered by start time) to voices, numbering voices by first
/// appearance so labels read "Speaker 1, 2, 3" in transcript order and clusters that
/// never own a segment get no label.
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

/// For each diarized voice, the id of the matching saved profile.
///
/// Matching is one-to-one: two voices in one meeting are never given the same name,
/// so the strongest pairs are taken first.
pub fn match_profiles(
    centroids: &[Vec<f32>],
    profiles: &[VoiceProfile],
    threshold: f32,
) -> Vec<Option<String>> {
    let mut candidates: Vec<(usize, usize, f32)> = Vec::new();
    for (voice, centroid) in centroids.iter().enumerate() {
        for (profile, saved) in profiles.iter().enumerate() {
            let score = cosine_similarity(centroid, &saved.embedding);
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

/// Folds a new sample of a voice into its saved embedding, weighting by how many samples
/// it already holds so one noisy meeting cannot overwrite a well-established profile.
pub fn merge_embedding(saved: &[f32], saved_samples: u32, new: &[f32]) -> Vec<f32> {
    if saved.len() != new.len() {
        return new.to_vec();
    }
    let weight = saved_samples as f32;
    saved
        .iter()
        .zip(new)
        .map(|(s, n)| (s * weight + n) / (weight + 1.0))
        .collect()
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
            match_profiles(&centroids, &profiles, 0.9),
            vec![Some("alice".into()), None, Some("bob".into())]
        );
    }

    #[test]
    fn never_gives_two_voices_the_same_profile() {
        let profiles = vec![VoiceProfile { id: "alice".into(), embedding: vec![1.0, 0.0] }];
        let centroids = vec![vec![0.95, 0.05], vec![1.0, 0.0]];
        assert_eq!(match_profiles(&centroids, &profiles, 0.5), vec![None, Some("alice".into())]);
    }

    #[test]
    fn merge_weights_existing_samples() {
        assert_eq!(merge_embedding(&[1.0, 0.0], 3, &[0.0, 1.0]), vec![0.75, 0.25]);
    }
}
