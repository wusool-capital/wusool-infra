# Wusool Capital — Platform Documentation

This is the documentation for the software delivered to Wusool Capital:
the **Wusool Toolkit** Slack bot, the **WusoolScribe** meeting assistant, and
the AWS platform they run on.

| I want to... | Go to |
| --- | --- |
| Use the Slack bot or WusoolScribe day to day | [User Guide](user-guide/README.md) |
| Understand how the system is built | [Technical Documentation](technical/README.md) |
| See what was delivered, what's outstanding, and who to contact | [Handover](handover/README.md) |

## What's included

- **Wusool Toolkit** — a Slack bot for the deal team: finding buyer–seller
  matches, researching missing buyer/seller details, and keeping
  buyer/seller profiles up to date.
- **WusoolScribe** — a desktop meeting assistant that records, transcribes,
  and summarizes meetings, and can push a summary into the CRM.
- **The Attio ↔ database platform** — Attio (the CRM) kept in sync with a
  structured database that powers matching and automation.
- **Lead-magnet tools** — four public tools on wusoolcapital.com (Valuation,
  M&A Readiness, GCC SME Benchmark, Buyer Network) that feed leads into Attio.
- **n8n** — a workflow-automation platform for the team.

All of it runs on AWS infrastructure managed as code and deployed
automatically from source control.
