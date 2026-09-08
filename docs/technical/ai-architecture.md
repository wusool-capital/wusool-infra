# AI / LLM architecture

All LLM calls run through **AWS Bedrock**, in-region, for two purposes:
buyer–seller matching (`matching_engine`) and meeting summarization
(`meetings`).

## Matching pipeline (`/find-match`)

1. **Extraction call** — the buyer's structured fields, free text, and
   recent meeting notes are turned into structured hard requirements and
   soft preferences.
2. **Deterministic filtering and scoring** — a fixed, reviewable set of
   criteria. A candidate is only dropped on a *confirmed* hard-requirement
   failure; missing data never eliminates anyone. The score is a weighted
   average, and a separate confidence signal (how much of the assessment
   rests on real CRM data vs. inference) is tracked alongside it, never
   folded into the ranking.
3. **Reasoning call** — a narrative explanation for the top-ranked
   shortlist only. It cannot change scores or introduce facts that weren't
   given to it.

Not implemented, by design: semantic/vector retrieval, document ingestion,
seller-financial enrichment, PDF generation, or outreach — out of scope for
this system.

## Meeting summarization

WusoolScribe transcribes locally on the user's machine; the server's role
starts only once a finished transcript is pushed to it. The server then:

1. Sends the transcript to Bedrock for summarization.
2. Writes the summary as a CRM note, linked to the meeting's organization
   and buyer/seller role when one is resolved.

This step runs in the background after the desktop app's push is
acknowledged, so the user isn't kept waiting on the summarization call.

## Models

Model selection is infrastructure-managed and can change without a code
change. As of this writing: a fast model for extraction, and a stronger
model for reasoning and summarization — see
[Integrations](integrations.md) for the current model IDs.
