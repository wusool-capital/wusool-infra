// diarization/worker.rs
//
// Runs separation in a child copy of the app, so a run that hangs or balloons is killed and its memory freed.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;

use anyhow::{anyhow, bail, Context, Result};
use serde::{Deserialize, Serialize};

use super::assign::SpeakerTurn;
use super::engine::{self, Diarization, DiarizationBackend};

/// First argument that starts the app binary as a worker instead of the app.
pub const WORKER_FLAG: &str = "--diarize-worker";
// Room for model loading, and for a slow machine running well behind its learned speed.
const MIN_TIME_LIMIT: Duration = Duration::from_secs(180);
const TIME_LIMIT_FACTOR: f64 = 4.0;
// Exit code when the app is gone, so nothing is left using memory after Scribe quits or is force quit.
const EXIT_APP_GONE: i32 = 3;
// Enough of a failed worker's stderr to explain it without flooding the UI.
const STDERR_TAIL_CHARS: usize = 400;

/// What a worker prints on stdout: the parts of a diarization the app uses.
#[derive(Debug, Serialize, Deserialize)]
struct WorkerOutput {
    turns: Vec<SpeakerTurn>,
    centroids: Vec<Vec<f32>>,
}

/// How long a run may take before it is stopped.
pub fn time_limit(estimated_secs: f64) -> Duration {
    Duration::from_secs_f64(estimated_secs * TIME_LIMIT_FACTOR).max(MIN_TIME_LIMIT)
}

/// Worker entry point for `<app> --diarize-worker <audio> <models dir> <backend>`; returns the exit code.
pub fn run_from_args(args: &[String]) -> i32 {
    exit_when_app_gone();
    match run_worker(args) {
        Ok(()) => 0,
        Err(e) => {
            eprintln!("{e:#}");
            1
        }
    }
}

/// The OS closes our stdin however the app ends, even on force quit, so end-of-file means quit.
fn exit_when_app_gone() {
    std::thread::spawn(|| {
        let mut stdin = std::io::stdin();
        let mut byte = [0u8; 1];
        while matches!(stdin.read(&mut byte), Ok(n) if n > 0) {}
        std::process::exit(EXIT_APP_GONE);
    });
}

fn run_worker(args: &[String]) -> Result<()> {
    let [audio, models_dir, backend] = args else {
        bail!("usage: {WORKER_FLAG} <audio> <models dir> <backend>");
    };
    let backend: DiarizationBackend = serde_json::from_value(serde_json::Value::String(backend.clone()))
        .with_context(|| format!("unknown backend {backend}"))?;
    let audio = super::audio::decode_16k_mono(Path::new(audio))?;
    let diarization = engine::diarize(Path::new(models_dir), backend, &audio)?;
    let output = WorkerOutput { turns: diarization.turns, centroids: diarization.centroids };
    let mut stdout = std::io::stdout().lock();
    serde_json::to_writer(&mut stdout, &output)?;
    stdout.flush()?;
    Ok(())
}

/// Diarizes `audio` in a worker process, killing it when it outlives `limit`.
pub async fn diarize_in_worker(
    audio: &Path,
    models_dir: &Path,
    backend: DiarizationBackend,
    limit: Duration,
) -> Result<Diarization> {
    let exe: PathBuf = std::env::current_exe().context("locating the app binary")?;
    let backend_arg = serde_json::to_value(backend)?
        .as_str()
        .ok_or_else(|| anyhow!("backend did not serialize to a string"))?
        .to_string();
    let mut command = tokio::process::Command::new(exe);
    command.arg(WORKER_FLAG).arg(audio).arg(models_dir).arg(backend_arg);
    let output = run_with_limit(command, limit).await?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let tail: String = stderr.trim().chars().rev().take(STDERR_TAIL_CHARS).collect::<Vec<_>>().into_iter().rev().collect();
        bail!("worker exited with {}: {}", output.status, tail);
    }
    let parsed: WorkerOutput = serde_json::from_slice(&output.stdout).context("reading the worker's result")?;
    Ok(Diarization { turns: parsed.turns, centroids: parsed.centroids })
}

/// Runs `command` to completion, killing it if it outlives `limit`.
async fn run_with_limit(mut command: tokio::process::Command, limit: Duration) -> Result<std::process::Output> {
    let mut child = command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        // Dropping the wait on timeout drops the child, and this kills it.
        .kill_on_drop(true)
        .spawn()
        .context("starting the speaker separation worker")?;
    // Taken so waiting doesn't close it: the worker treats a closed stdin as the app having quit.
    let _app_alive = child.stdin.take();
    tokio::time::timeout(limit, child.wait_with_output())
        .await
        .map_err(|_| anyhow!("stopped after {} min without finishing", limit.as_secs().div_ceil(60)))?
        .context("waiting for the speaker separation worker")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn short_meetings_get_the_floor_and_long_ones_scale() {
        assert_eq!(time_limit(10.0), MIN_TIME_LIMIT);
        assert_eq!(time_limit(300.0), Duration::from_secs(1200));
    }

    #[test]
    fn worker_output_round_trips() {
        let output = WorkerOutput {
            turns: vec![SpeakerTurn { start: 0.5, end: 2.0, speaker: 1 }],
            centroids: vec![vec![0.25, -1.0]],
        };
        let parsed: WorkerOutput = serde_json::from_str(&serde_json::to_string(&output).unwrap()).unwrap();
        assert_eq!(parsed.turns, output.turns);
        assert_eq!(parsed.centroids, output.centroids);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn an_overrunning_worker_is_killed() {
        // A distinctive duration so the check below finds only this test's process.
        let marker = "31.4159";
        let mut command = tokio::process::Command::new("sleep");
        command.arg(marker);
        let started = std::time::Instant::now();
        let error = run_with_limit(command, Duration::from_millis(300)).await.unwrap_err();
        assert!(error.to_string().contains("stopped after"), "{error}");
        assert!(started.elapsed() < Duration::from_secs(5));

        tokio::time::sleep(Duration::from_millis(200)).await;
        let still_running = std::process::Command::new("pgrep").args(["-f", &format!("sleep {marker}")]).status().unwrap();
        assert!(!still_running.success(), "the timed-out worker is still running");
    }

    #[test]
    fn bad_arguments_fail_without_running() {
        assert_eq!(run_from_args(&["only-one".to_string()]), 1);
        let args = ["a.wav", "models", "gpu"].map(String::from);
        assert_eq!(run_from_args(&args), 1);
    }
}
