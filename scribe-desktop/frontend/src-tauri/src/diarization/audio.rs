// diarization/audio.rs
//
// Streams ffmpeg's 16 kHz mono output, so memory peaks at ~230 MB per hour, not a 48 kHz decode.

use std::io::Read;
use std::path::Path;
use std::process::{Command, Stdio};

use anyhow::{anyhow, Context, Result};

use crate::audio::ffmpeg::find_ffmpeg_path;

const SAMPLE_RATE: &str = "16000";
const READ_CHUNK_BYTES: usize = 64 * 1024;

/// Blocking: call from `spawn_blocking`.
pub fn decode_16k_mono(path: &Path) -> Result<Vec<f32>> {
    let ffmpeg = find_ffmpeg_path().ok_or_else(|| anyhow!("FFmpeg not found"))?;
    let mut command = Command::new(ffmpeg);
    command
        .arg("-nostdin")
        .args(["-loglevel", "error", "-i"])
        .arg(path)
        .args(["-vn", "-ac", "1", "-ar", SAMPLE_RATE, "-f", "f32le", "-"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    // Prevents a console window flashing up on Windows while decoding.
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        command.creation_flags(CREATE_NO_WINDOW);
    }

    let mut child = command.spawn().context("starting ffmpeg")?;
    let mut stdout = child.stdout.take().context("ffmpeg stdout unavailable")?;
    // Drained on its own thread so a chatty ffmpeg can't block on a full stderr pipe.
    let mut stderr = child.stderr.take().context("ffmpeg stderr unavailable")?;
    let stderr_reader = std::thread::spawn(move || {
        let mut message = String::new();
        let _ = stderr.read_to_string(&mut message);
        message
    });

    let samples = read_f32le(&mut stdout)?;
    let status = child.wait()?;
    let errors = stderr_reader.join().unwrap_or_default();
    if !status.success() {
        return Err(anyhow!("ffmpeg failed to decode {}: {}", path.display(), errors.trim()));
    }
    Ok(samples)
}

fn read_f32le(reader: &mut impl Read) -> Result<Vec<f32>> {
    let mut samples = Vec::new();
    let mut buffer = vec![0u8; READ_CHUNK_BYTES];
    let mut carry = 0usize;
    loop {
        let read = reader.read(&mut buffer[carry..])?;
        if read == 0 {
            break;
        }
        let filled = carry + read;
        let whole = filled - filled % 4;
        samples.extend(
            buffer[..whole]
                .chunks_exact(4)
                .map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]])),
        );
        // A read can end mid-sample; keep the partial bytes for the next read.
        buffer.copy_within(whole..filled, 0);
        carry = filled - whole;
    }
    Ok(samples)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Delivers bytes in awkward sizes so samples straddle read boundaries.
    struct Trickle {
        bytes: Vec<u8>,
        position: usize,
    }

    impl Read for Trickle {
        fn read(&mut self, out: &mut [u8]) -> std::io::Result<usize> {
            let n = out.len().min(3).min(self.bytes.len() - self.position);
            out[..n].copy_from_slice(&self.bytes[self.position..self.position + n]);
            self.position += n;
            Ok(n)
        }
    }

    #[test]
    fn reassembles_samples_split_across_reads() {
        let expected = vec![0.5f32, -0.25, 1.0, f32::MIN_POSITIVE];
        let bytes = expected.iter().flat_map(|x| x.to_le_bytes()).collect();
        let decoded = read_f32le(&mut Trickle { bytes, position: 0 }).unwrap();
        assert_eq!(decoded, expected);
    }
}
