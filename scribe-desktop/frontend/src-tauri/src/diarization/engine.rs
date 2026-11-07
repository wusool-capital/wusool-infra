// diarization/engine.rs
//
// Thin wrapper over speakrs: audio in, speaker turns and one voice embedding per speaker out.

use std::path::{Path, PathBuf};

use anyhow::{anyhow, Context, Result};
use log::info;
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

/// Downloads missing model files via a temp name, so an interrupted download never looks complete.
pub async fn ensure_models(dir: &Path, backend: DiarizationBackend) -> Result<()> {
    let client = reqwest::Client::new();
    for file in backend.model_files() {
        let target = dir.join(&file);
        if target.exists() {
            continue;
        }
        if let Some(parent) = target.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }
        info!("Downloading diarization model file {}", file);
        let url = format!("{MODEL_BASE_URL}/{MODEL_REVISION}/{file}");
        let bytes = client
            .get(&url)
            .send()
            .await
            .and_then(reqwest::Response::error_for_status)
            .with_context(|| format!("downloading {file}"))?
            .bytes()
            .await?;
        let partial = dir.join(format!("{file}.part"));
        tokio::fs::write(&partial, &bytes).await?;
        tokio::fs::rename(&partial, &target).await?;
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
