// audio/mic_test.rs
//
// "Test Mic" in settings: opens the chosen microphone and reports what it really hears.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use anyhow::{anyhow, Result};
use cpal::traits::{DeviceTrait, StreamTrait};
use cpal::SampleFormat;
use log::{info, warn};
use serde::Serialize;
use tauri::{AppHandle, Emitter, Runtime};

use super::devices::{default_input_device, get_device_and_config, AudioDevice, DeviceType};
use super::mic_level::{db_fraction, rms_db};

const REPORT_EVERY: Duration = Duration::from_millis(100);
const ACTIVE_FRACTION: f32 = 0.1;

// Each test gets a number; a test thread stops as soon as a newer test (or a stop) replaces it.
static CURRENT_TEST: AtomicU64 = AtomicU64::new(0);
// Number of the test whose thread is live, or 0 when none is.
static ACTIVE_TEST: AtomicU64 = AtomicU64::new(0);

/// One device's level, in the `audio-levels` event the settings meter listens for.
#[derive(Debug, Serialize, Clone)]
pub struct AudioLevelData {
    pub device_name: String,
    pub device_type: String,
    /// Loudness on the meter's 0 to 1 scale.
    pub rms_level: f32,
    pub peak_level: f32,
    pub is_active: bool,
}

#[derive(Debug, Serialize, Clone)]
pub struct AudioLevelUpdate {
    pub timestamp: u64,
    pub levels: Vec<AudioLevelData>,
}

/// Loudness gathered by the audio callback since the last report.
#[derive(Default)]
struct Window {
    samples: Vec<f32>,
}

/// Starts testing one microphone: the named one, or the system default when none is given.
pub async fn start<R: Runtime>(app: AppHandle<R>, device_name: Option<String>) -> Result<()> {
    if super::recording_commands::is_recording_now() {
        return Err(anyhow!("Stop the recording before testing the microphone"));
    }
    let test_id = CURRENT_TEST.fetch_add(1, Ordering::SeqCst) + 1;

    let audio_device = match device_name {
        Some(name) => AudioDevice::new(name, DeviceType::Input),
        None => default_input_device()?,
    };
    let (device, config) = get_device_and_config(&audio_device).await?;
    let device_name = audio_device.name.clone();
    info!("Testing microphone '{}'", device_name);

    // cpal streams cannot move between threads on macOS, so one thread owns it start to finish.
    std::thread::spawn(move || {
        let window = Arc::new(Mutex::new(Window::default()));
        let stream = match build_stream(&device, &config, window.clone()) {
            Ok(stream) => stream,
            Err(e) => {
                warn!("Could not open '{}' for the mic test: {:#}", device_name, e);
                return;
            }
        };
        if let Err(e) = stream.play() {
            warn!("Could not start the mic test stream: {}", e);
            return;
        }
        ACTIVE_TEST.store(test_id, Ordering::SeqCst);

        // A recording needs the mic to itself, so a test ends when one starts.
        while CURRENT_TEST.load(Ordering::SeqCst) == test_id && !super::recording_commands::is_recording_now() {
            std::thread::sleep(REPORT_EVERY);
            let samples = std::mem::take(&mut window.lock().unwrap_or_else(|p| p.into_inner()).samples);
            let _ = app.emit("audio-levels", level_update(&device_name, &samples));
        }
        let _ = ACTIVE_TEST.compare_exchange(test_id, 0, Ordering::SeqCst, Ordering::SeqCst);
        info!("Microphone test for '{}' ended", device_name);
        // Dropping the stream here releases the microphone.
    });
    Ok(())
}

/// Stops any running microphone test and releases the device.
pub fn stop() {
    CURRENT_TEST.fetch_add(1, Ordering::SeqCst);
}

/// True while a test is holding the microphone open.
pub fn is_running() -> bool {
    ACTIVE_TEST.load(Ordering::SeqCst) != 0
}

fn level_update(device_name: &str, samples: &[f32]) -> AudioLevelUpdate {
    let rms = db_fraction(rms_db(samples));
    let peak_sample = samples.iter().fold(0.0f32, |peak, s| peak.max(s.abs()));
    let peak = db_fraction(20.0 * peak_sample.max(f32::MIN_POSITIVE).log10());
    AudioLevelUpdate {
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64,
        levels: vec![AudioLevelData {
            device_name: device_name.to_string(),
            device_type: "input".to_string(),
            rms_level: rms,
            peak_level: peak,
            is_active: rms > ACTIVE_FRACTION,
        }],
    }
}

fn build_stream(
    device: &cpal::Device,
    config: &cpal::SupportedStreamConfig,
    window: Arc<Mutex<Window>>,
) -> Result<cpal::Stream> {
    let stream_config = config.config();
    let on_error = |e| warn!("Mic test stream error: {}", e);
    let stream = match config.sample_format() {
        SampleFormat::F32 => device.build_input_stream(
            &stream_config,
            move |data: &[f32], _| push(&window, data.iter().copied()),
            on_error,
            None,
        )?,
        SampleFormat::I16 => device.build_input_stream(
            &stream_config,
            move |data: &[i16], _| push(&window, data.iter().map(|s| *s as f32 / i16::MAX as f32)),
            on_error,
            None,
        )?,
        SampleFormat::U16 => device.build_input_stream(
            &stream_config,
            move |data: &[u16], _| push(&window, data.iter().map(|s| (*s as f32 - 32768.0) / 32768.0)),
            on_error,
            None,
        )?,
        other => return Err(anyhow!("unsupported microphone sample format: {other:?}")),
    };
    Ok(stream)
}

fn push(window: &Mutex<Window>, samples: impl Iterator<Item = f32>) {
    if let Ok(mut window) = window.try_lock() {
        window.samples.extend(samples);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn silence_is_inactive_and_speech_is_active() {
        let quiet = level_update("Mic", &[0.0; 4800]);
        assert_eq!(quiet.levels[0].rms_level, 0.0);
        assert!(!quiet.levels[0].is_active);

        let speech: Vec<f32> = (0..4800).map(|i| 0.1 * (i as f32 * 0.05).sin()).collect();
        let loud = level_update("Mic", &speech);
        assert!(loud.levels[0].rms_level > 0.5);
        assert!(loud.levels[0].is_active);
        assert_eq!(loud.levels[0].device_name, "Mic");
    }
}
