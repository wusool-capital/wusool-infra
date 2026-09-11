# Integrations

| Service | Used for |
| --- | --- |
| **Attio** | Business CRM of record; matching source data; meeting notes are filed here. |
| **Slack** | The Wusool Toolkit bot's only interface. |
| **AWS Bedrock** | LLM calls for `/find-match` (Claude Haiku, extraction; Claude Sonnet, reasoning), `/enrich-seller`/`/enrich-buyer` (extraction from search results), and meeting summarization. |
| **Firecrawl** | Google-Maps web-lead fallback when no seller matches in `/find-match` (now owned by the `discovery` module — see [Architecture](architecture.md) — rather than inline in `matching_engine`), and the free-text research tier for `/enrich-seller`/`/enrich-buyer`. Disables cleanly without an API key. |
| **Diffbot** | Structured company data (revenue, employee count, founding date, etc.) for `/enrich-seller` — tried before the Firecrawl free-text tier. Free tier: 10,000 credits/month. Optional; disables cleanly without an API key. |
| **People Data Labs** | Second structured company-data source for `/enrich-seller`, filling in whatever Diffbot didn't resolve. Free tier: 100 lookups/month. Optional; disables cleanly without an API key. |
| **n8n** | Self-hosted workflow automation. Its own login; not managed from this documentation. |
| **AWS SES** | Password-reset / invite email for n8n. |
| **Cloudflare** | DNS. |
| **GitHub Actions** | Source control and CI/CD, using short-lived credentials rather than static keys. |
| **Ollama / Claude / Groq / OpenRouter / custom endpoint** | WusoolScribe's own AI-summary providers — separate from the server's Bedrock path, chosen per install. |
