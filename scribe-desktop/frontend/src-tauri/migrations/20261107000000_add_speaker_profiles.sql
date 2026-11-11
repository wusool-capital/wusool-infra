-- Migration: voice library for speaker diarization
-- speaker_profiles holds people the user has named, with a voice embedding used to
-- recognise them automatically in later meetings. Embeddings never leave the device.
-- meeting_speakers maps each diarized label in a meeting (speaker_0, speaker_1, ...)
-- to a profile, and keeps that voice's embedding from this meeting so naming it later
-- can enrol or refine the profile.

CREATE TABLE IF NOT EXISTS speaker_profiles (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE,
    embedding BLOB NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meeting_speakers (
    meeting_id TEXT NOT NULL,
    label TEXT NOT NULL,
    profile_id TEXT,
    embedding BLOB NOT NULL,
    PRIMARY KEY (meeting_id, label),
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES speaker_profiles(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_meeting_speakers_profile_id ON meeting_speakers(profile_id);
