# Architecture

## Server modules

The server is organized as modules, each layered `domain → application →
persistence → providers → api`, with Ports (`typing.Protocol`s) at the
application boundary that never expose ORM types. Architecture fitness tests
enforce this on every change.

| Module | Responsibility |
| --- | --- |
| `matching_engine` | `/find-match` — requirement extraction, filtering, scoring, reasoning, persistence, Slack delivery. |
| `ddl_commands` | `/edit-seller`, `/edit-buyer`, `/add-seller`, `/add-buyer`, the inbound Attio webhook, and the nightly resync job. |
| `enrichment` | `/enrich-seller`, `/enrich-buyer` — researches missing buyer/seller fields from public sources and hands the proposal to `ddl_commands`' own edit form for review; never writes to Attio or the database itself. |
| `discovery` | Finds sellers outside the CRM via a public search when `/find-match` has no strong CRM candidate, and hands a chosen lead to `ddl_commands`' `/add-seller` flow; never writes to Attio or the database itself. |
| `meetings` | Ingests transcripts pushed by WusoolScribe, summarizes via Bedrock, and files the result as an Attio note. |
| `organizations` | Shared organization search and persistence, used by `ddl_commands` and `matching_engine`. |
| `attio` | Attio vendor client, webhook payload types, value extraction. |
| `notifications` | Cross-module Slack notifier and Slack text formatting. |
| `utilities` | Cross-cutting infrastructure: logging, retry, money handling, database wiring, shared Slack app construction. |

`enrichment` and `discovery` each declare a Port for the one write they need
(opening a prefilled edit/add form) rather than importing `ddl_commands`
directly — `ddl_commands` implements the adapter, and the process entrypoint
wires the two together at startup. The dependency edge points
`ddl_commands → {enrichment, discovery}`, never the reverse.

One process is the deployed entrypoint: it builds a single Slack app,
registers every module's Slack handlers, and serves one Slack request URL.

## Why modules, not microservices

Everything runs as one process — simpler to deploy and operate at this
scale — but each module is internally decoupled the way a service would be:
a clean interface (a Port) between it and everything else, so a module can
be extracted into its own service later without a rewrite. Dependencies
point inward only (`api → providers → persistence → application → domain`),
never the other way, and this is enforced automatically rather than by
convention alone.

## Where things live

- Each module's own module documentation covers its structure, its public
  contract, and its own known limitations in depth.
- Cross-module rules (which module owns what, how a Slack command becomes a
  database write) are covered in [Business rules](business-rules.md).
