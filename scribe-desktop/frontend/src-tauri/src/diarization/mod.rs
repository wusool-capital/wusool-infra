// diarization/mod.rs
//
// Speaker attribution: who said each transcript segment.

pub mod assign;
pub mod commands;
pub mod engine;
pub mod label;
pub mod service;

pub use label::SpeakerLabel;
