# Troubleshooting and support

Preserve the error and context before retrying so support can distinguish a
service failure from invalid input.

| Problem | First checks |
| --- | --- |
| Toolkit command missing | Confirm the bot is present; try `/toolkit-help` |
| Toolkit error or timeout | Run `/toolkit-status`; check the Attio name; avoid repeated write attempts |
| Match has low confidence | Review records and use `/enrich-*` before matching again |
| Scribe records only one side | Recheck **Devices**, system audio, permissions, and levels |
| Scribe has no transcript | Confirm the model downloaded and check model, language, and microphone |
| Scribe push fails | Verify **Push Destination**, connectivity, organization, and meeting status |
| Attio change is missing elsewhere | Confirm it saved and allow for synchronization delay |
| Website tool fails | Save the tool name, time, company domain, and exact error; retry once |
| n8n execution fails | Capture the workflow, execution ID, failed node, and error before retrying |

## Request support

Send the engineering or product owner the product and environment, expected
and actual result, time with time zone, organization or workflow name, and
exact error. Include a screenshot when useful. For Scribe, include the
**Install ID** from **Settings → Push Destination**. For n8n, include the
workflow name and execution ID.

Use approved private channels for email addresses, meeting content, CRM URLs,
and other client data. Never send passwords, API keys, Slack tokens, or n8n
credentials. Support can identify Scribe from its Install ID and does not need
the API key.

## Before retrying

Retrying a search or read-only check is usually harmless. Retrying a create,
CRM push, website submission, or n8n workflow can make duplicates or repeat
an external action. If the first attempt may have completed, check Attio,
Scribe status, or the n8n execution first.
