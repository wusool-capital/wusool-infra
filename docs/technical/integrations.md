# Integrations

| Service | Used for |
| --- | --- |
| **Attio** | Business CRM of record; matching source data; meeting notes are filed here. |
| **Slack** | The Wusool Toolkit bot's only interface. |
| **AWS Bedrock** | LLM calls for `/find-match` (Claude Haiku, extraction; Claude Sonnet, reasoning) and meeting summarization. |
| **Firecrawl** | Optional Google-Maps web-lead fallback when no seller matches in `/find-match`. Disables cleanly without an API key. |
| **n8n** | Self-hosted workflow automation. Its own login; not managed from this documentation. |
| **AWS SES** | Password-reset / invite email for n8n. |
| **Cloudflare** | DNS. |
| **GitHub Actions** | Source control and CI/CD, using short-lived credentials rather than static keys. |
| **Ollama / Claude / Groq / OpenRouter / custom endpoint** | WusoolScribe's own AI-summary providers — separate from the server's Bedrock path, chosen per install. |
