// audio/mic_level.rs
//
// The live microphone loudness the recording controls show, measured from the audio actually captured.

use std::sync::atomic::{AtomicU32, Ordering};

/// Quietest level reported; anything below reads as silence on the meter.
pub const SILENCE_DB: f32 = -60.0;

// f32 bits of the latest level in dBFS, written by the pipeline and read by the UI.
static LATEST_DB: AtomicU32 = AtomicU32::new(SILENCE_DB.to_bits());

/// Records the loudness of one stretch of microphone audio.
pub fn record(samples: &[f32]) {
    LATEST_DB.store(rms_db(samples).to_bits(), Ordering::Relaxed);
}

/// Back to silence, so a stopped recording never shows a stale level.
pub fn reset() {
    LATEST_DB.store(SILENCE_DB.to_bits(), Ordering::Relaxed);
}

/// Latest microphone level in dBFS, from `SILENCE_DB` up to 0.
#[tauri::command]
pub fn get_mic_level() -> f32 {
    f32::from_bits(LATEST_DB.load(Ordering::Relaxed))
}

fn rms_db(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return SILENCE_DB;
    }
    let rms = (samples.iter().map(|x| x * x).sum::<f32>() / samples.len() as f32).sqrt();
    (20.0 * rms.max(f32::MIN_POSITIVE).log10()).clamp(SILENCE_DB, 0.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn silence_and_full_scale_map_to_the_ends() {
        assert_eq!(rms_db(&[0.0; 480]), SILENCE_DB);
        assert!((rms_db(&[1.0; 480]) - 0.0).abs() < 1e-4);
    }

    #[test]
    fn half_scale_is_about_minus_six_db() {
        assert!((rms_db(&[0.5; 480]) + 6.02).abs() < 0.05);
    }
}
