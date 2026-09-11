# API reference

## Slack commands

| Command | Module |
| --- | --- |
| `/find-match <buyer name>` | `matching_engine` |
| `/edit-seller <name>` | `ddl_commands` |
| `/edit-buyer <name>` | `ddl_commands` |
| `/add-seller <organization name>` | `ddl_commands` |
| `/add-buyer <organization name>` | `ddl_commands` |
| `/enrich-seller <name>` | `enrichment` |
| `/enrich-buyer <name>` | `enrichment` |
| `/help` | Answered directly in the process entrypoint (`main.py`) — not owned by any one module. |
| `/toolkit-status` | Same — reports uptime, database reachability, and Attio test/production mode. |

There is no bare `/enrich` — both enrichment commands are kind-scoped, so an
organization with both an active buyer and seller role never needs a
disambiguation step just to pick the kind.

Slack interactive components (buttons and modals) back each of these —
disambiguation modals, field pickers, edit/add forms, the
Approve/Reject/View Full Analysis/Enrich buttons on a match result, and the
"Review & Save" button on an enrichment proposal.

## WusoolScribe desktop API

All under `/desktop/*`, authenticated with a shared API key (`Authorization:
Bearer <key>`):

| Endpoint | Purpose |
| --- | --- |
| `POST /desktop/meetings` | Push a finished transcript for summarization. Acknowledges immediately; summarization runs in the background. |
| `GET /desktop/meetings/{meeting_id}` | Poll one meeting's summarization status. |
| `GET /desktop/meetings?install_id=` | List an install's meetings (sync). |
| `GET /desktop/companies/search` | Look up a CRM organization to tag a meeting. |
| `GET /desktop/verify` | Validate a server URL and API key before the desktop app saves its Push Destination settings. |

## Webhooks

| Endpoint | Purpose |
| --- | --- |
| `POST /webhooks/attio` | Real-time Attio → database sync. Signature-verified. |

## Operational

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness check. |
| `GET /readiness` (alias `/ready`) | Confirms database connectivity. |
