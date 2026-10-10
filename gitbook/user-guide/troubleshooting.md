# Troubleshooting and support

Note the exact error and what you were doing before retrying, so support can
tell a service failure from invalid input.

| Problem | First checks |
| --- | --- |
| Toolkit doesn't respond | Make sure the bot is added to the channel; it doesn't work in direct messages. Try `/toolkit-help` |
| Toolkit error or timeout | Run `/toolkit-status` and check the Attio name; don't resubmit a change repeatedly |
| Match has low confidence | Review the records and run `/enrich-*` before matching again |
| Website check shows no website | The lead's only web presence is a social or shop page, so it counts as having no website |
| Scribe only captures your voice | Recheck the system-audio device in **Settings → Recordings → Default Audio Devices** and the screen-recording permission |
| Scribe is silent after an update | macOS removed its access; allow microphone and screen recording again |
| Scribe stopped recording too early | Auto-stop ended it with the call; press **Keep** next time, or turn it off in **Settings → Recordings** |
| Scribe has no transcript | Confirm the model downloaded, then check the model, language, and microphone |
| Scribe push fails | Check **Settings → Scribe Push**, your connection, and the selected organization |
| Report code never arrives | Check spam, then use **Resend code**; codes expire after 10 minutes. If it still fails, send support the reader's email and the report link |
| Attio change is missing elsewhere | Confirm it saved, then allow a few minutes |
| Website tool fails | Note the tool name, time, company domain, and exact error; retry once |
| n8n execution fails | Note the workflow, execution ID, failed node, and error before retrying |

## Request support

Send the product owner the product and environment, expected and actual
result, time with time zone, organization or workflow name, and exact error.
Include a screenshot when useful. For Scribe, include the **Install ID** from
**Settings → Scribe Push**. For n8n, include the workflow name and execution
ID.

Use approved private channels for email addresses, meeting content, CRM URLs,
and other client data. Never send passwords, API keys, or n8n credentials.
Support can identify Scribe from its Install ID and doesn't need the API key.

## Before retrying

Retrying a search or read-only check is usually harmless. Retrying a create,
CRM push, website submission, or n8n workflow can create duplicates or repeat
an external action. If the first attempt may have completed, check Attio,
the Scribe meeting status, or the n8n execution first.
