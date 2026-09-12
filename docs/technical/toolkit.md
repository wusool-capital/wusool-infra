# Wusool Toolkit

## Purpose

Wusool Toolkit is the internal Slack interface for finding acquisition
matches, maintaining buyer and seller profiles, and researching missing
profile data. It runs in the shared FastAPI backend and is not a separate
Slack service per command.

## Components

| Module | Responsibility |
| --- | --- |
| `matching_engine` | Resolves a buyer, extracts requirements, filters and scores sellers, explains the shortlist, and stores the run. |
| `ddl_commands` | Adds and edits buyer/seller profiles through Attio-first writes. |
| `enrichment` | Researches proposed profile values; an operator must review them before the normal edit flow saves them. |
| `discovery` | Searches public sources for sellers and hands a selected result to the normal add-seller flow. |
| `organizations` | Shared organization search and persistence. |
| `attio` | Attio API client, value conversion, notes, and webhook helpers. |
| `notifications` / `utilities` | Shared Slack formatting, notifications, database wiring, logging, retry, and money handling. |

## Data flow

### Matching

1. `/find-match` resolves the buyer by fuzzy organization search.
2. Bedrock extracts confirmed hard requirements and soft preferences from CRM
   fields, free text, and recent meeting notes.
3. Deterministic rules reject only confirmed hard failures, then score the
   remaining sellers. Missing data is neutral rather than disqualifying.
4. Bedrock writes narrative reasoning for the configured top candidates; it
   cannot alter their scores.
5. The run and candidate results are committed atomically, then posted to
   Slack with review actions.
6. A weak result can trigger Firecrawl seller discovery. Selecting a result
   opens the ordinary, prefilled add-seller form.

### Profile changes and enrichment

Add/edit requests search for the organization, collect fields in Slack, write
Attio first, and then update PostgreSQL. This order prevents the scheduled CRM
sync from overwriting a Slack-originated change. Enrichment uses optional
Diffbot, People Data Labs, and Firecrawl sources, then Bedrock normalizes the
evidence. It only proposes values; saving still follows the edit flow.

## Dependencies and configuration

The runtime requires PostgreSQL, Slack credentials, Attio credentials, and
Bedrock access. Matching model IDs, scoring weights, confidence penalties,
meeting-note limits, and discovery thresholds are configured in the server
environment. Firecrawl enables discovery and free-text enrichment; Diffbot and
People Data Labs are optional enrichment tiers.

Use the standard AWS credential provider chain in deployed environments.
`ATTIO_IS_TEST` separates test and production records inside the shared SOURCE
Attio workspace; development stamps test records and refuses production
records.

## Interfaces

| Interface | Behavior |
| --- | --- |
| `/find-match <buyer>` | Creates and explains a ranked seller shortlist. |
| `/add-buyer <organization>` / `/add-seller <organization>` | Attaches a new role or creates an organization and role. |
| `/edit-buyer <name>` / `/edit-seller <name>` | Selects and updates eligible fields. |
| `/enrich-buyer <name>` / `/enrich-seller <name>` | Produces a reviewable research proposal. |
| `/toolkit-help` | Lists usage guidance. |
| `/toolkit-status` | Reports uptime, database reachability, and Attio mode. |
| `POST /slack/events` | Receives Slack events and interactions; Slack Bolt verifies signatures. |
| `GET /health` | Process liveness. |
| `GET /readiness` and `GET /ready` | Database readiness. |

There are no remove commands and no public REST endpoints for match or profile
data.

### Example matching trace

For `/find-match Example Holdings`, Slack first asks the user to confirm the
buyer. After confirmation, the service creates a run, extracts requirements,
filters and scores eligible sellers deterministically, and generates narrative
reasoning for the shortlist. It commits the run and candidate results together
before posting review actions to Slack.

If requirement extraction or reasoning fails, the run stops and reports an
error instead of inventing a result. If every CRM candidate scores below the
discovery threshold, public seller discovery can offer unverified leads.
None becomes a CRM seller until an operator completes the add-seller flow.

## Processing rules and failures

- Attio failures before any remote write leave PostgreSQL unchanged. If an
  earlier Attio sub-write succeeded, Slack identifies the partial write.
- Concurrent add requests for the same organization are not protected by a
  cross-request lock. Both can succeed and create a duplicate, so operators
  should avoid parallel submissions and reconcile duplicates in Attio.
- Bedrock extraction or reasoning failures stop the matching run and surface an
  operator-facing error; deterministic scoring cannot invent missing facts.
- Discovery is unavailable without Firecrawl and enrichment skips any missing
  optional provider.
- Slack forms exclude system-managed, reference, and pipeline-owned fields that
  the interface cannot safely update.
