// diarization/engine.rs
//
// Thin wrapper over speakrs: audio in, speaker turns and one voice embedding per speaker out.

use std::path::{Path, PathBuf};

use anyhow::{anyhow, Context, Result};
use log::info;
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

pub struct Diarization {
    pub turns: Vec<SpeakerTurn>,
    /// Indexed by `SpeakerTurn::speaker`.
    pub centroids: Vec<Vec<f32>>,
}

pub fn models_dir(app_data_dir: &Path) -> PathBuf {
    app_data_dir.join("models").join("diarization").join(MODEL_REVISION)
}

/// Downloads any missing model file. Each file lands under a temp name first so an
/// interrupted download is never mistaken for a complete one.
pub async fn ensure_models(dir: &Path) -> Result<()> {
    tokio::fs::create_dir_all(dir).await?;
    let client = reqwest::Client::new();
    for file in CPU_MODEL_FILES {
        let target = dir.join(file);
        if target.exists() {
            continue;
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
pub fn diarize(models_dir: &Path, audio_16k_mono: &[f32]) -> Result<Diarization> {
    let mut pipeline = OwnedDiarizationPipeline::from_dir(models_dir, ExecutionMode::Cpu)
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

    /// Needs network and a real multi-speaker recording, so it only runs on demand:
    /// DIARIZATION_FIXTURE=meeting.wav DIARIZATION_SPEAKERS=3 cargo test -- --ignored diarizes_fixture
    #[tokio::test]
    #[ignore]
    async fn diarizes_fixture() {
        let fixture = PathBuf::from(std::env::var("DIARIZATION_FIXTURE").expect("DIARIZATION_FIXTURE"));
        let expected: usize = std::env::var("DIARIZATION_SPEAKERS").expect("DIARIZATION_SPEAKERS").parse().unwrap();
        let models = tempfile::tempdir().unwrap();

        ensure_models(models.path()).await.unwrap();
        let audio = crate::audio::decoder::decode_audio_file(&fixture).unwrap().to_whisper_format();
        let result = diarize(models.path(), &audio).unwrap();

        assert_eq!(result.centroids.len(), expected);
        assert!(result.turns.iter().all(|t| (t.speaker as usize) < expected));
        assert!(result.centroids.iter().all(|c| c.len() == 256 && c.iter().all(|x| x.is_finite())));
    }
}
