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
| Firecrawl | Web-lead fallback in matching, the free-text research tier for `/enrich-seller`/`/enrich-buyer`, and the Valuation lead magnet's comparable-company search | API key optional for matching/enrichment (disables cleanly without it); required for the Valuation lead magnet's `/compare` |
| Diffbot | Structured company-data lookups for `/enrich-seller` | API key optional; free tier is 10,000 credits/month |
| People Data Labs | Second structured company-data source for `/enrich-seller` | API key optional; free tier is 100 lookups/month |
| n8n (self-hosted) | Workflow automation | Runs on Wusool's own infrastructure; the application itself is a vendor product |
