# Technical Documentation

For engineers maintaining or extending this system. This page is the map;
the detail lives in the pages linked from each section.

## System overview

The platform delivers three connected planes:

| Plane | What it is |
| --- | --- |
| **AWS infrastructure** | OpenTofu-managed AWS resources running the whole platform. |
| **Slack bot server** | One FastAPI + Slack Bolt process (a modular monolith) running the nine slash commands and the meeting-summarization API. |
| **CRM data platform** | Attio (the CRM) kept in sync with the `wusool_crm` PostgreSQL database: a nightly full resync, a real-time webhook, and operator scripts. |

n8n (workflow automation) runs as its own service and is infrastructure-managed
only — the application itself is a vendor product.

```text
Slack ──/commands──▶ server ──▶ wusool_crm (PostgreSQL)
                        │  ▲              ▲
                        ▼  │              │
                  AWS Bedrock    └── Attio ◀──webhook + nightly resync
                  (matching, summarization)
                        ▲
                        │
              WusoolScribe (desktop app) ──pushes transcripts──┘
```

## Pages

| Topic | Page |
| --- | --- |
| Server modules, module layering | [Architecture](architecture.md) |
| The four public lead-magnet tools (Valuation, Readiness, Benchmark, Buyer Network) | [Lead Magnets](lead-magnets.md) |
| Database, schema authority | [Data model](data-model.md) |
| Bedrock pipeline for matching and summarization | [AI / LLM architecture](ai-architecture.md) |
| Attio, Slack, Bedrock, Firecrawl, n8n and other vendors | [Integrations](integrations.md) |
| Slack commands, `/desktop/*`, webhooks | [API reference](api-reference.md) |
| Auth boundaries, secrets, access model | [Security](security.md) |
| CI/CD, stacks, configuration | [Deployment](deployment.md) |
| Attio-first writes, schema authority, editable fields | [Business rules](business-rules.md) |
| The WusoolScribe desktop app | [WusoolScribe desktop app](scribe-desktop.md) |
