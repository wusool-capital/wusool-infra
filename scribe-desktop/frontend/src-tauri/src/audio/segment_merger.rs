// audio/segment_merger.rs
//
// Joins short speech fragments into sentence-sized lines before transcription, for better accuracy and fewer lines.

use super::vad::SpeechSegment;

const SAMPLE_RATE: f64 = 16_000.0;
/// Pieces shorter than this wait for the speech that follows ("Yeah," then the rest of the sentence).
const MIN_LINE_MS: f64 = 2_500.0;
/// A longer silence is a real break: the held piece is released as its own line.
const MAX_JOIN_GAP_MS: f64 = 2_000.0;
/// Joining stops here; the voice detector itself can still emit longer unbroken speech.
const MAX_LINE_MS: f64 = 20_000.0;

#[derive(Default)]
pub struct SegmentMerger {
    pending: Option<SpeechSegment>,
}

impl SegmentMerger {
    /// Takes the next VAD segment and returns the lines ready to transcribe.
    pub fn push(&mut self, segment: SpeechSegment) -> Vec<SpeechSegment> {
        let mut ready = Vec::new();
        let segment = match self.pending.take() {
            Some(held) if can_join(&held, &segment) => join(held, segment),
            Some(held) => {
                ready.push(held);
                segment
            }
            None => segment,
        };
        if duration_ms(&segment) >= MIN_LINE_MS {
            ready.push(segment);
        } else {
            self.pending = Some(segment);
        }
        ready
    }

    /// Releases a held piece once `now_ms` shows nothing followed it in time.
    pub fn tick(&mut self, now_ms: f64) -> Option<SpeechSegment> {
        let expired = self
            .pending
            .as_ref()
            .is_some_and(|held| now_ms - held.end_timestamp_ms > MAX_JOIN_GAP_MS);
        if expired { self.pending.take() } else { None }
    }

    /// Releases whatever is held, for the end of a recording.
    pub fn flush(&mut self) -> Option<SpeechSegment> {
        self.pending.take()
    }
}

fn duration_ms(segment: &SpeechSegment) -> f64 {
    segment.end_timestamp_ms - segment.start_timestamp_ms
}

fn can_join(held: &SpeechSegment, next: &SpeechSegment) -> bool {
    let gap = next.start_timestamp_ms - held.end_timestamp_ms;
    gap <= MAX_JOIN_GAP_MS && next.end_timestamp_ms - held.start_timestamp_ms <= MAX_LINE_MS
}

/// Joins two pieces with the real silence between them, so line times stay on the recording's timeline.
fn join(held: SpeechSegment, next: SpeechSegment) -> SpeechSegment {
    let gap_ms = (next.start_timestamp_ms - held.end_timestamp_ms).max(0.0);
    let mut samples = held.samples;
    samples.resize(samples.len() + (gap_ms / 1000.0 * SAMPLE_RATE).round() as usize, 0.0);
    samples.extend(next.samples);
    SpeechSegment {
        samples,
        start_timestamp_ms: held.start_timestamp_ms,
        end_timestamp_ms: next.end_timestamp_ms,
        confidence: held.confidence.min(next.confidence),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn segment(start_ms: f64, end_ms: f64) -> SpeechSegment {
        let len = ((end_ms - start_ms) / 1000.0 * SAMPLE_RATE) as usize;
        SpeechSegment { samples: vec![0.1; len], start_timestamp_ms: start_ms, end_timestamp_ms: end_ms, confidence: 0.9 }
    }

    #[test]
    fn long_pieces_pass_straight_through() {
        let mut merger = SegmentMerger::default();
        assert_eq!(merger.push(segment(0.0, 4_000.0)).len(), 1);
        assert!(merger.flush().is_none());
    }

    #[test]
    fn short_fragments_join_the_speech_that_follows() {
        let mut merger = SegmentMerger::default();
        assert!(merger.push(segment(27_000.0, 27_400.0)).is_empty()); // "An"
        let ready = merger.push(segment(28_000.0, 31_000.0)); // "d we ate a lot of food."
        assert_eq!(ready.len(), 1);
        assert_eq!(ready[0].start_timestamp_ms, 27_000.0);
        assert_eq!(ready[0].end_timestamp_ms, 31_000.0);
        // The silence is kept, so sample count still matches the timeline.
        assert_eq!(ready[0].samples.len(), (4.0 * SAMPLE_RATE) as usize);
    }

    #[test]
    fn a_long_silence_keeps_lines_apart() {
        let mut merger = SegmentMerger::default();
        assert!(merger.push(segment(0.0, 800.0)).is_empty());
        let ready = merger.push(segment(5_000.0, 9_000.0));
        assert_eq!(ready.len(), 2);
        assert_eq!(ready[0].end_timestamp_ms, 800.0);
    }

    #[test]
    fn a_held_piece_is_released_when_nothing_follows() {
        let mut merger = SegmentMerger::default();
        assert!(merger.push(segment(0.0, 800.0)).is_empty());
        assert!(merger.tick(2_000.0).is_none());
        assert!(merger.tick(3_000.0).is_some());
    }

    #[test]
    fn lines_never_grow_past_the_cap() {
        let mut merger = SegmentMerger::default();
        let mut released = Vec::new();
        let mut start = 0.0;
        for _ in 0..30 {
            released.extend(merger.push(segment(start, start + 2_000.0)));
            start += 2_500.0;
        }
        released.extend(merger.flush());
        assert!(released.iter().all(|s| duration_ms(s) <= MAX_LINE_MS));
    }
}

#[cfg(test)]
mod recording_stats {
    use super::*;
    use crate::audio::vad::get_speech_chunks;

    fn stats(label: &str, lines: &[SpeechSegment]) -> String {
        let mut secs: Vec<f64> = lines.iter().map(|s| duration_ms(s) / 1000.0).collect();
        secs.sort_by(f64::total_cmp);
        let under_1s = secs.iter().filter(|&&d| d < 1.0).count();
        format!(
            "{label}: {} lines, median {:.1}s, under 1s: {} ({:.0}%), longest {:.1}s",
            secs.len(),
            secs[secs.len() / 2],
            under_1s,
            100.0 * under_1s as f64 / secs.len() as f64,
            secs.last().copied().unwrap_or(0.0)
        )
    }

    /// Compares line shapes for a real recording; prints counts and lengths only.
    /// SEGMENT_FIXTURE=meeting.mp4 cargo test --lib -- --ignored --nocapture compares_line_shapes
    #[test]
    #[ignore]
    fn compares_line_shapes() {
        let path = std::env::var("SEGMENT_FIXTURE").expect("SEGMENT_FIXTURE");
        let audio = crate::diarization::audio::decode_16k_mono(std::path::Path::new(&path)).unwrap();

        let before = get_speech_chunks(&audio, 400).unwrap();
        let mut merger = SegmentMerger::default();
        let mut after: Vec<SpeechSegment> = Vec::new();
        for segment in get_speech_chunks(&audio, 800).unwrap() {
            after.extend(merger.push(segment));
        }
        after.extend(merger.flush());

        println!("{}", stats("400 ms, no merging", &before));
        println!("{}", stats("800 ms + merging  ", &after));
    }
}
