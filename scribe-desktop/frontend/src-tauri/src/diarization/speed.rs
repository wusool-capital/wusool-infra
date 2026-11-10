// diarization/speed.rs
//
// How long separation takes per second of audio, learned from finished runs, for a progress estimate.

use serde::{Deserialize, Serialize};

use super::engine::DiarizationBackend;

// Model loading and ffmpeg start-up, paid once per run whatever the meeting length.
const OVERHEAD_SECS: f64 = 5.0;
// Shorter runs are mostly overhead, so they would teach a misleading rate.
const MIN_LEARN_AUDIO_SECS: f64 = 60.0;
// Weight of the newest run: adapts within a few meetings without one outlier swinging it.
const LEARN_WEIGHT: f64 = 0.5;

/// Processing seconds per second of audio, per backend.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct SeparationSpeed {
    pub cpu: f64,
    pub coreml: f64,
}

impl Default for SeparationSpeed {
    // The documented timings until this Mac has its own: an hour takes ~4 min on CPU, ~40 s on CoreML.
    fn default() -> Self {
        Self { cpu: 0.065, coreml: 0.01 }
    }
}

impl SeparationSpeed {
    fn rate(&self, backend: DiarizationBackend) -> f64 {
        match backend {
            DiarizationBackend::Cpu => self.cpu,
            DiarizationBackend::CoreMl => self.coreml,
        }
    }

    pub fn estimate_secs(&self, backend: DiarizationBackend, audio_secs: f64) -> f64 {
        OVERHEAD_SECS + audio_secs.max(0.0) * self.rate(backend)
    }

    /// Blends a finished run into the backend's rate.
    pub fn learn(self, backend: DiarizationBackend, audio_secs: f64, took_secs: f64) -> Self {
        if audio_secs < MIN_LEARN_AUDIO_SECS || !took_secs.is_finite() {
            return self;
        }
        let observed = (took_secs - OVERHEAD_SECS).max(0.0) / audio_secs;
        let blended = self.rate(backend) * (1.0 - LEARN_WEIGHT) + observed * LEARN_WEIGHT;
        match backend {
            DiarizationBackend::Cpu => Self { cpu: blended, ..self },
            DiarizationBackend::CoreMl => Self { coreml: blended, ..self },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn estimate_grows_with_audio_and_backend_rate() {
        let speed = SeparationSpeed::default();
        let hour = 3600.0;
        assert!(speed.estimate_secs(DiarizationBackend::Cpu, hour) > speed.estimate_secs(DiarizationBackend::CoreMl, hour));
        assert_eq!(speed.estimate_secs(DiarizationBackend::Cpu, 0.0), OVERHEAD_SECS);
    }

    #[test]
    fn learning_moves_only_the_backend_that_ran() {
        let speed = SeparationSpeed { cpu: 0.1, coreml: 0.01 };
        let learned = speed.learn(DiarizationBackend::Cpu, 1000.0, OVERHEAD_SECS + 20.0);
        assert!((learned.cpu - 0.06).abs() < 1e-9);
        assert_eq!(learned.coreml, 0.01);
    }

    #[test]
    fn short_or_broken_runs_teach_nothing() {
        let speed = SeparationSpeed::default();
        assert_eq!(speed.learn(DiarizationBackend::Cpu, 30.0, 100.0), speed);
        assert_eq!(speed.learn(DiarizationBackend::Cpu, 600.0, f64::NAN), speed);
    }
}
