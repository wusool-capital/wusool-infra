// audio/bleed_gate.rs
//
// Detects when the microphone is only picking up the meeting audio from the speakers.
// Without headphones, remote voices leak into the mic and would be transcribed twice,
// once from each source, and wrongly attributed to the local user.

use std::collections::VecDeque;

const FRAME_MS: usize = 10;
const HISTORY_FRAMES: usize = 150;
// Speaker-to-mic acoustic delay plus device buffering rarely exceeds this.
const MAX_LAG_FRAMES: usize = 25;
const CORRELATION_THRESHOLD: f32 = 0.8;
const SYSTEM_ACTIVITY_RMS: f32 = 0.005;

pub struct BleedGate {
    frame_samples: usize,
    mic_env: VecDeque<f32>,
    sys_env: VecDeque<f32>,
}

impl BleedGate {
    pub fn new(sample_rate: u32) -> Self {
        Self {
            frame_samples: (sample_rate as usize * FRAME_MS) / 1000,
            mic_env: VecDeque::with_capacity(HISTORY_FRAMES),
            sys_env: VecDeque::with_capacity(HISTORY_FRAMES),
        }
    }

    /// Feeds one aligned window of each source and reports whether the mic window is bleed.
    pub fn is_bleed(&mut self, mic_window: &[f32], sys_window: &[f32]) -> bool {
        for (mic_frame, sys_frame) in mic_window
            .chunks(self.frame_samples)
            .zip(sys_window.chunks(self.frame_samples))
        {
            push_bounded(&mut self.mic_env, rms(mic_frame));
            push_bounded(&mut self.sys_env, rms(sys_frame));
        }

        let sys_mean = self.sys_env.iter().sum::<f32>() / self.sys_env.len().max(1) as f32;
        if sys_mean < SYSTEM_ACTIVITY_RMS || self.mic_env.len() <= MAX_LAG_FRAMES * 2 {
            return false;
        }

        let mic: Vec<f32> = self.mic_env.iter().copied().collect();
        let sys: Vec<f32> = self.sys_env.iter().copied().collect();
        (0..=MAX_LAG_FRAMES)
            .map(|lag| pearson(&mic[lag..], &sys[..sys.len() - lag]))
            .fold(f32::MIN, f32::max)
            >= CORRELATION_THRESHOLD
    }
}

fn push_bounded(buffer: &mut VecDeque<f32>, value: f32) {
    if buffer.len() == HISTORY_FRAMES {
        buffer.pop_front();
    }
    buffer.push_back(value);
}

fn rms(frame: &[f32]) -> f32 {
    (frame.iter().map(|x| x * x).sum::<f32>() / frame.len().max(1) as f32).sqrt()
}

fn pearson(a: &[f32], b: &[f32]) -> f32 {
    let n = a.len().min(b.len()) as f32;
    let (mean_a, mean_b) = (a.iter().sum::<f32>() / n, b.iter().sum::<f32>() / n);
    let (mut cov, mut var_a, mut var_b) = (0.0, 0.0, 0.0);
    for (x, y) in a.iter().zip(b) {
        let (dx, dy) = (x - mean_a, y - mean_b);
        cov += dx * dy;
        var_a += dx * dx;
        var_b += dy * dy;
    }
    if var_a == 0.0 || var_b == 0.0 {
        return 0.0;
    }
    cov / (var_a.sqrt() * var_b.sqrt())
}

#[cfg(test)]
mod tests {
    use super::*;

    const RATE: u32 = 48_000;
    const WINDOW: usize = 28_800; // 600 ms, matching the pipeline mixer window

    /// Speech-like signal: a tone whose loudness follows a syllable-rate envelope.
    fn speech(seconds: f32, seed: f32) -> Vec<f32> {
        let n = (RATE as f32 * seconds) as usize;
        (0..n)
            .map(|i| {
                let t = i as f32 / RATE as f32;
                let envelope = ((t * 3.7 + seed).sin() * (t * 1.3 + seed * 2.0).sin()).abs();
                envelope * 0.3 * (t * 220.0 * std::f32::consts::TAU).sin()
            })
            .collect()
    }

    fn run(gate: &mut BleedGate, mic: &[f32], sys: &[f32]) -> bool {
        mic.chunks(WINDOW)
            .zip(sys.chunks(WINDOW))
            .map(|(m, s)| gate.is_bleed(m, s))
            .last()
            .unwrap()
    }

    #[test]
    fn delayed_quieter_copy_of_system_audio_is_bleed() {
        let sys = speech(4.0, 0.0);
        let delay = RATE as usize / 20; // 50 ms
        let mut mic = vec![0.0; delay];
        mic.extend(sys.iter().map(|x| x * 0.2));
        mic.truncate(sys.len());
        assert!(run(&mut BleedGate::new(RATE), &mic, &sys));
    }

    #[test]
    fn independent_speech_over_system_audio_is_not_bleed() {
        let sys = speech(4.0, 0.0);
        let mic = speech(4.0, 5.0);
        assert!(!run(&mut BleedGate::new(RATE), &mic, &sys));
    }

    #[test]
    fn silent_system_audio_is_never_bleed() {
        let sys = vec![0.0; RATE as usize * 4];
        let mic = speech(4.0, 1.0);
        assert!(!run(&mut BleedGate::new(RATE), &mic, &sys));
    }
}
