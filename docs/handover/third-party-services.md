# Third-party services

| Service | Used for | Ownership |
| --- | --- | --- |
| AWS | All compute, database, AI, secrets, and monitoring | Wusool's AWS account |
| Attio | Business CRM of record; matching source data | Wusool Capital's Attio workspace |
| Slack | The Toolkit bot's only interface | One Slack app, one bot token |
| Cloudflare | DNS | Wusool |
| GitHub / GitHub Actions | Source control and CI/CD | Wusool's GitHub organization |
| AWS SES | n8n password-reset / invite email | Sandbox mode — see [Known limitations](limitations.md) |
| AWS Bedrock | LLM calls for matching and meeting summarization | `eu-central-1` |
| Firecrawl | Optional web-lead fallback in matching | API key optional; the feature disables cleanly without it |
| n8n (self-hosted) | Workflow automation | Runs on Wusool's own infrastructure; the application itself is a vendor product |
