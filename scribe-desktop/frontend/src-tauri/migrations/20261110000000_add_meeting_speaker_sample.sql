-- Migration: each voice's playback clip, taken from its longest uninterrupted diarized turn.
-- Transcript lines can hold several people, so a clip cut from a line can play someone else.
-- NULL for voices added by hand or diarized before this, which fall back to their longest line.

ALTER TABLE meeting_speakers ADD COLUMN sample_start REAL;
ALTER TABLE meeting_speakers ADD COLUMN sample_end REAL;
