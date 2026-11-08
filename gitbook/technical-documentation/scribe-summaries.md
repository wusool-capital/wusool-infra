# WusoolScribe summaries and proofread

How the Toolkit server writes a meeting summary and suggests transcript
fixes for Scribe. See [WusoolScribe](scribe.md) for the push flow and
interfaces.

## Summary format

The summary's `executive_summary` field holds a gist of 2–3 sentences and
60 words at most. The field keeps its old name, so installed apps still show
it; a later release can rename it. Detail goes in `notes`, sized by
`summary_budget` in `server/app/modules/meetings/domain/prompts.py` from the
transcript's word count:

| Transcript | Spoken time | Topics | Gist and notes |
| --- | --- | --- | --- |
| Up to 2,000 words | up to ~13 minutes | 1–2 | ~120 words at most |
| Up to 8,000 words | ~13–53 minutes | 3–4 | ~350 words at most |
| More | over ~53 minutes | 6–8 | ~700 words at most |

The budget is a ceiling: a long meeting with little substance still gets a
short summary. Decisions, action items and claims to verify are never cut to
fit it. The prompt also sets the writing style: British spelling, sentences
of 25 words or fewer, outcome first. It trusts speaker names a user
assigned, but not placeholders such as "Speaker 2", "Others" or "Me".

`render_summary_text` writes the plain text stored in `meetings.summary`,
filed as the Attio note and read by the matching engine. Its order is gist,
next steps, decisions, deal momentum, claims to verify, risks, keywords,
then notes by topic. The matching engine reads each summary whole, never
cut, as context for buyer and seller matching.
Summaries are not regenerated, so older ones keep their long opening.

The Bedrock calls run through Pydantic AI agents
(`server/app/modules/meetings/providers/bedrock/client.py`). Each agent's
output type is a schema, so Bedrock must answer through that tool and the
agent validates the result. A final summary whose gist runs over 75 words,
or with a note point over 35, gets one retry; after that it is accepted.
Transient AWS errors are retried up to three times. Logs and stored failure
reasons hold error codes only, never model output.

A push for the same install and recording always returns 409, so pushing
again doesn't recover a failed meeting. Instead, a meeting stalled for 10
minutes is reset the next time its status is read, which re-runs the
summary.

## Proofread

`CorrectionService` (`server/app/modules/meetings/application/corrections.py`)
splits a transcript into batches of about 12,000 characters, four at a time.
Each batch numbers its lines from 1, so the model returns short line numbers
instead of segment ids and never repeats the original text. The two lines
before a batch go along as read-only context.

The system prompt holds the rules and a default vocabulary of deal, finance
and GCC terms (`domain/vocabulary.py`). It is the same for every batch, so
Bedrock caches it. The user's own words, the speaker names and the meeting
title arrive per request, trimmed and capped.

The server drops a suggestion for an unknown line, a repeat or no change. It
also drops a rewrite: more than three changed words or 40% of the line, or a
switch between Arabic and Latin script. Letters spoken one at a time count as one
word. It reports the stored text as `original`, which the app checks before
applying a fix.

Each change must also sound like the words it replaces (`sounds_alike`), so a
fix can't swap one name for an unrelated one. A change that fails is put back,
and the rest of that line's fix is kept. Each batch's prompt carries only the
speaker names and user words that something in the batch sounds like. Common
names (`COMMON_NAMES`) are sent the same way, never in the cached system
prompt. Shown a name, the model tended to rename strangers to it.

`CORRECTION_MODEL_ID` and `CORRECTION_MAX_TOKENS` set the model and output
budget. `scripts/eval_proofread.py` scores models against labelled excerpts.
On 20 errors, Sonnet 4.6 caught 19 with no false fixes. Haiku 4.5 caught 18
with none, in about two thirds of the time. The set includes traps: user
words and speaker names that never occur in the meeting, beside unfamiliar
names that must stay.
