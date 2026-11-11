// diarization/mod.rs
//
// Speaker attribution: who said each transcript segment.

pub mod assign;
pub mod audio;
pub mod commands;
pub mod engine;
pub mod label;
pub mod overview;
pub mod service;
pub mod speed;
pub mod worker;

pub use label::SpeakerLabel;
