# Matching Engine

Placeholder — the matching-engine backend lives in its own repository. This
folder exists only so the `workflows/matching-engine/` path is present in
`wusool-infra`, matching the layout of the other `workflows/*` directories
(each of which owns the scripts/docs for one workflow: `n8n`, `bedrock-ai`,
`crm-sync`).

See `workflows/crm-sync/docs/PHASE3_MATCH_RESULTS_HANDOVER.md` for the
matching-engine's one dependency on this repo: the `match_results` table in
`database/sql/006_match_results.sql`.
