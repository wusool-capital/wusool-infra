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
| `meetings` | Ingests transcripts pushed by WusoolScribe, summarizes via Bedrock, and files the result as an Attio note. |
| `organizations` | Shared organization search and persistence, used by both `ddl_commands` and `matching_engine`. |
| `attio` | Attio vendor client, webhook payload types, value extraction. |
| `notifications` | Cross-module Slack notifier and Slack text formatting. |
| `utilities` | Cross-cutting infrastructure: logging, retry, money handling, database wiring, shared Slack app construction. |

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
