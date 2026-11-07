// diarization/engine.rs
//
// Thin wrapper over speakrs: audio in, speaker turns and one voice embedding per speaker out.

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::LazyLock;

use anyhow::{anyhow, Context, Result};
use futures_util::StreamExt;
use log::info;
use tokio::io::AsyncWriteExt;
use serde::{Deserialize, Serialize};
use speakrs::{DiarizationResult, ExecutionMode, OwnedDiarizationPipeline};

use super::assign::SpeakerTurn;

/// Pinned so a model update upstream can never silently change results or break loading.
const MODEL_REVISION: &str = "67f963b6a1d94fcd4678948237b3cc8bd69bf1d8";
const MODEL_BASE_URL: &str = "https://huggingface.co/avencera/speakrs-models/resolve";

/// Files the native CPU backend loads (about 32 MB in total).
const CPU_MODEL_FILES: &[&str] = &[
    "segmentation-3.0.safetensors",
    "wespeaker-multimask-tail.safetensors",
    "wespeaker-voxceleb-resnet34.min_num_samples.txt",
    "plda_lda.npy",
    "plda_mean1.npy",
    "plda_mean2.npy",
    "plda_mu.npy",
    "plda_phi.npy",
    "plda_psi.npy",
    "plda_tr.npy",
];

/// The CoreML bundles speakrs 0.7 loads (~263 MB); recheck this list when upgrading speakrs.
const COREML_MODEL_STEMS: &[&str] = &[
    "segmentation-3.0",
    "segmentation-3.0-b32",
    "segmentation-3.0-b64",
    "wespeaker-fbank",
    "wespeaker-fbank-b32",
    "wespeaker-fbank-30s",
    "wespeaker-multimask-tail-b32",
    "wespeaker-voxceleb-resnet34-tail",
    "wespeaker-voxceleb-resnet34-tail-b3",
    "wespeaker-voxceleb-resnet34-tail-b32",
    "wespeaker-chunk-emb-p1s-w21",
    "wespeaker-chunk-emb-p1s-w36",
    "wespeaker-chunk-emb-p1s-w51",
    "wespeaker-chunk-emb-p1s-w81",
    "wespeaker-chunk-emb-p1s-w111",
];
const MLMODELC_FILES: &[&str] = &["model.mil", "coremldata.bin", "weights/weight.bin", "analytics/coremldata.bin"];

/// CPU is the default; CoreML is about 6x faster but peaks near 2.7 GB of RAM, against 0.5 GB.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DiarizationBackend {
    #[default]
    Cpu,
    CoreMl,
}

impl DiarizationBackend {
    pub const fn coreml_available() -> bool {
        cfg!(target_os = "macos")
    }

    /// The backend that will actually run: CoreML falls back to CPU off macOS.
    pub fn effective(self) -> Self {
        if self == Self::CoreMl && Self::coreml_available() { Self::CoreMl } else { Self::Cpu }
    }

    fn execution_mode(self) -> ExecutionMode {
        match self.effective() {
            #[cfg(target_os = "macos")]
            Self::CoreMl => ExecutionMode::CoreMl,
            _ => ExecutionMode::Cpu,
        }
    }

    fn model_files(self) -> Vec<String> {
        let mut files: Vec<String> = CPU_MODEL_FILES.iter().map(|f| f.to_string()).collect();
        if self.effective() == Self::CoreMl {
            for stem in COREML_MODEL_STEMS {
                files.extend(MLMODELC_FILES.iter().map(|f| format!("{stem}.mlmodelc/{f}")));
            }
        }
        files
    }
}

pub struct Diarization {
    pub turns: Vec<SpeakerTurn>,
    /// Indexed by `SpeakerTurn::speaker`.
    pub centroids: Vec<Vec<f32>>,
}

pub fn models_dir(app_data_dir: &Path) -> PathBuf {
    app_data_dir.join("models").join("diarization").join(MODEL_REVISION)
}

/// Bytes fetched so far against the total, for a download progress bar.
#[derive(Debug, Clone, Copy, Serialize)]
pub struct DownloadProgress {
    pub downloaded: u64,
    pub total: u64,
}

// One downloader at a time, so a meeting finishing mid-download never writes the same files.
static MODEL_DOWNLOAD: LazyLock<tokio::sync::Mutex<()>> = LazyLock::new(|| tokio::sync::Mutex::new(()));

fn model_url(file: &str) -> String {
    format!("{MODEL_BASE_URL}/{MODEL_REVISION}/{file}")
}

/// Model files this backend needs that are not on disk yet.
pub fn missing_files(dir: &Path, backend: DiarizationBackend) -> Vec<String> {
    backend.model_files().into_iter().filter(|file| !dir.join(file).exists()).collect()
}

pub fn models_ready(dir: &Path, backend: DiarizationBackend) -> bool {
    missing_files(dir, backend).is_empty()
}

/// Downloads missing model files, with no progress reporting.
pub async fn ensure_models(dir: &Path, backend: DiarizationBackend) -> Result<()> {
    download_models(dir, backend, &AtomicBool::new(false), |_| {}).await
}

/// Downloads missing model files, reporting progress and stopping early when `cancel` is set.
/// Each file lands under a temp name first, so an interrupted download never looks complete.
pub async fn download_models(
    dir: &Path,
    backend: DiarizationBackend,
    cancel: &AtomicBool,
    mut on_progress: impl FnMut(DownloadProgress),
) -> Result<()> {
    let _guard = MODEL_DOWNLOAD.lock().await;
    let missing = missing_files(dir, backend);
    if missing.is_empty() {
        return Ok(());
    }

    let client = reqwest::Client::new();
    // Sizes up front, so progress is one honest bar rather than file-by-file jumps.
    let requests: Vec<reqwest::RequestBuilder> = missing.iter().map(|file| client.head(model_url(file))).collect();
    let sizes: Vec<u64> = futures_util::stream::iter(requests)
        .map(|request| async move { request.send().await.ok().and_then(|r| r.content_length()).unwrap_or(0) })
        .buffered(8)
        .collect()
        .await;
    let total: u64 = sizes.iter().sum();
    let mut downloaded = 0u64;
    on_progress(DownloadProgress { downloaded, total });

    for file in &missing {
        let target = dir.join(file);
        if let Some(parent) = target.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }
        info!("Downloading diarization model file {}", file);
        let response = client
            .get(model_url(file))
            .send()
            .await
            .and_then(reqwest::Response::error_for_status)
            .with_context(|| format!("downloading {file}"))?;

        let partial = dir.join(format!("{file}.part"));
        let mut out = tokio::fs::File::create(&partial).await?;
        let mut body = response.bytes_stream();
        while let Some(chunk) = body.next().await {
            if cancel.load(Ordering::SeqCst) {
                drop(out);
                let _ = tokio::fs::remove_file(&partial).await;
                return Err(anyhow!("download cancelled"));
            }
            let chunk = chunk.with_context(|| format!("downloading {file}"))?;
            out.write_all(&chunk).await?;
            downloaded += chunk.len() as u64;
            on_progress(DownloadProgress { downloaded, total: total.max(downloaded) });
        }
        out.flush().await?;
        drop(out);
        tokio::fs::rename(&partial, &target).await?;
    }
    Ok(())
}

/// Removes the CoreML bundles only; the CPU model stays because CPU separation still needs it.
pub async fn delete_coreml_models(dir: &Path) -> Result<()> {
    let _guard = MODEL_DOWNLOAD.lock().await;
    for stem in COREML_MODEL_STEMS {
        let bundle = dir.join(format!("{stem}.mlmodelc"));
        if bundle.exists() {
            tokio::fs::remove_dir_all(&bundle).await?;
        }
    }
    Ok(())
}

/// Blocking and CPU-heavy: call from `spawn_blocking`.
pub fn diarize(models_dir: &Path, backend: DiarizationBackend, audio_16k_mono: &[f32]) -> Result<Diarization> {
    let mut pipeline = OwnedDiarizationPipeline::from_dir(models_dir, backend.execution_mode())
        .map_err(|e| anyhow!("loading diarization models: {e}"))?;
    let result = pipeline
        .run(audio_16k_mono)
        .map_err(|e| anyhow!("running diarization: {e}"))?;

    let turns = result
        .exclusive_segments
        .iter()
        .map(|segment| {
            let speaker = parse_speaker_index(&segment.speaker)?;
            Ok(SpeakerTurn { start: segment.start, end: segment.end, speaker })
        })
        .collect::<Result<Vec<_>>>()?;

    let centroids = cluster_centroids(&result);
    Ok(Diarization { turns, centroids })
}

fn parse_speaker_index(label: &str) -> Result<u32> {
    label
        .strip_prefix("SPEAKER_")
        .and_then(|n| n.parse().ok())
        .ok_or_else(|| anyhow!("unexpected speaker label from speakrs: {label}"))
}

/// Averages the per-chunk embeddings assigned to each cluster into one voice embedding.
fn cluster_centroids(result: &DiarizationResult) -> Vec<Vec<f32>> {
    let embeddings = &result.embeddings.0;
    let clusters = &result.hard_clusters.0;
    let (chunks, local_speakers, dim) = embeddings.dim();
    let cluster_count = clusters.iter().copied().max().map_or(0, |max| (max + 1).max(0) as usize);
    let mut sums = vec![vec![0.0f32; dim]; cluster_count];
    let mut counts = vec![0u32; cluster_count];

    for chunk in 0..chunks {
        for local in 0..local_speakers.min(clusters.ncols()) {
            let Ok(cluster) = usize::try_from(clusters[[chunk, local]]) else { continue };
            let vector: Vec<f32> = (0..dim).map(|j| embeddings[[chunk, local, j]]).collect();
            // Inactive chunk-speaker slots hold NaN embeddings.
            if vector.iter().any(|x| !x.is_finite()) {
                continue;
            }
            for (sum, value) in sums[cluster].iter_mut().zip(&vector) {
                *sum += value;
            }
            counts[cluster] += 1;
        }
    }

    sums.into_iter()
        .zip(counts)
        .map(|(sum, count)| sum.into_iter().map(|x| x / count.max(1) as f32).collect())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn coreml_needs_cpu_files_too_and_falls_back_off_macos() {
        let cpu = DiarizationBackend::Cpu.model_files();
        let coreml = DiarizationBackend::CoreMl.model_files();
        assert!(cpu.iter().all(|f| coreml.contains(f)));
        if DiarizationBackend::coreml_available() {
            assert_eq!(coreml.len(), cpu.len() + COREML_MODEL_STEMS.len() * MLMODELC_FILES.len());
        } else {
            assert_eq!(DiarizationBackend::CoreMl.effective(), DiarizationBackend::Cpu);
        }
    }

    #[test]
    fn backend_serializes_for_the_settings_store() {
        assert_eq!(serde_json::to_string(&DiarizationBackend::CoreMl).unwrap(), "\"coreml\"");
        assert_eq!(serde_json::from_str::<DiarizationBackend>("\"cpu\"").unwrap(), DiarizationBackend::Cpu);
    }

    /// Downloads the real CoreML models (~263 MB), so it runs only with `--ignored`.
    #[tokio::test]
    #[ignore]
    async fn downloads_reports_progress_and_deletes_coreml_only() {
        let dir = tempfile::tempdir().unwrap();
        let mut seen: Vec<DownloadProgress> = Vec::new();
        download_models(dir.path(), DiarizationBackend::CoreMl, &AtomicBool::new(false), |p| seen.push(p))
            .await
            .unwrap();

        assert!(seen.windows(2).all(|w| w[1].downloaded >= w[0].downloaded));
        let last = seen.last().unwrap();
        assert_eq!(last.downloaded, last.total);
        assert!(models_ready(dir.path(), DiarizationBackend::CoreMl));

        delete_coreml_models(dir.path()).await.unwrap();
        assert!(!models_ready(dir.path(), DiarizationBackend::CoreMl));
        assert!(models_ready(dir.path(), DiarizationBackend::Cpu));
    }

    #[tokio::test]
    #[ignore]
    async fn a_cancelled_download_leaves_no_partial_file() {
        let dir = tempfile::tempdir().unwrap();
        let result = download_models(dir.path(), DiarizationBackend::Cpu, &AtomicBool::new(true), |_| {}).await;
        assert!(result.unwrap_err().to_string().contains("cancelled"));
        let leftovers = std::fs::read_dir(dir.path()).unwrap().filter_map(|e| e.ok())
            .filter(|e| e.file_name().to_string_lossy().ends_with(".part")).count();
        assert_eq!(leftovers, 0);
    }

    /// Needs network and a real recording, so it runs only with `--ignored` and these env vars:
    /// DIARIZATION_FIXTURE=meeting.wav DIARIZATION_SPEAKERS=3 [DIARIZATION_BACKEND=coreml]
    #[tokio::test]
    #[ignore]
    async fn diarizes_fixture() {
        let fixture = PathBuf::from(std::env::var("DIARIZATION_FIXTURE").expect("DIARIZATION_FIXTURE"));
        let expected: usize = std::env::var("DIARIZATION_SPEAKERS").expect("DIARIZATION_SPEAKERS").parse().unwrap();
        let models = tempfile::tempdir().unwrap();

        let backend = match std::env::var("DIARIZATION_BACKEND").as_deref() {
            Ok("coreml") => DiarizationBackend::CoreMl,
            _ => DiarizationBackend::Cpu,
        };

        ensure_models(models.path(), backend).await.unwrap();
        let audio = crate::diarization::audio::decode_16k_mono(&fixture).unwrap();
        let result = diarize(models.path(), backend, &audio).unwrap();

        assert_eq!(result.centroids.len(), expected);
        assert!(result.turns.iter().all(|t| (t.speaker as usize) < expected));
        assert!(result.centroids.iter().all(|c| c.len() == 256 && c.iter().all(|x| x.is_finite())));
    }
}
