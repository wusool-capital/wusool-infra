# Handover — Overview

This section describes the **current delivered state** of the Wusool
platform.

## Overview

The delivered platform includes:

- **AWS infrastructure**, deployed automatically from source control.
- **The Wusool Toolkit Slack bot** — five slash commands for buyer–seller
  matching and for editing buyer/seller profiles.
- **WusoolScribe** — a desktop meeting assistant that transcribes locally
  and can push a summary into the CRM.
- **An Attio ↔ PostgreSQL data platform** — the business CRM (Attio) kept in
  sync with a structured database used for automation, enrichment, and the
  matching engine.
- **n8n** — a workflow-automation platform.

## Delivered components

| Component | Status | Notes |
| --- | --- | --- |
| Continuous deployment | Live | Merges to the main branches apply infrastructure changes and health-check the applications automatically. No static AWS keys involved. |
| n8n | Live | HTTPS, pinned image versions, email delivery working (sandbox mode — see [Known limitations](limitations.md)). |
| Wusool Toolkit Slack bot | {% hint style="warning" %}Verify before delivery{% endhint %} Live | One process, five commands. |
| PostgreSQL database | {% hint style="warning" %}Verify before delivery{% endhint %} Live | System of record for matching and CRM sync. |
| Schema management | Live | Migrations are the schema source of truth, applied automatically as part of deployment. |
| Attio → PostgreSQL sync | Live | Nightly full resync plus a real-time webhook, both verified end-to-end. |
| AI matching (AWS Bedrock) | Live | See [AI / LLM architecture](../technical/ai-architecture.md). |
| WusoolScribe → CRM (meeting summaries) | Live | The desktop app pushes a finished transcript to the server, which summarizes it and files a CRM note. |
| Security & monitoring baseline | Live | See [Ownership and support](ownership-and-support.md). |

## Where to look

| Need | Start here |
| --- | --- |
| How to use the bot or WusoolScribe | [User Guide](../user-guide/README.md) |
| Architecture, deployment, configuration | [Technical Documentation](../technical/README.md) |
| Environments and third-party services | [Environment](environment.md), [Third-party services](third-party-services.md) |
| What isn't finished yet | [Known limitations](limitations.md), [Outstanding items](outstanding.md) |
