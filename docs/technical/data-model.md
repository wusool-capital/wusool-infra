# Data model

- **Source of truth:** the server's ORM models and its migration history.
  The server never creates or alters tables at runtime — every schema
  change goes through a reviewed migration.
- **Schema authority is the data engineering team, not the bot** — a
  migration is never generated or applied on the bot's own initiative. See
  [Business rules](business-rules.md).
- A continuous-integration check fails any change whose models and
  migrations disagree, so the two can never drift apart silently.

## Core tables

| Table | Owned by | Purpose |
| --- | --- | --- |
| `organizations` | `organizations` (shared) | The company behind a buyer or seller role. |
| `buyer_roles` / `seller_roles` | `ddl_commands` | Buyer/seller profile data, editable via Slack. |
| `match_scores` / `match_results` | `matching_engine` | Persisted `/find-match` runs and their scored candidates. |
| `meetings` / `notes` | `meetings` | Meeting transcripts pushed from WusoolScribe and the CRM notes generated from them. |

## Attio ↔ PostgreSQL mapping

Attio (the CRM) and PostgreSQL (`wusool_crm`) hold the same organizations,
buyer/seller roles, and notes, kept in sync by:

- A real-time webhook, for changes made directly in Attio.
- A nightly full resync, as a consistency backstop.
- Attio-first writes from the bot itself (see
  [Business rules](business-rules.md)).
