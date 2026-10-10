# Environments and access

The platform has isolated `dev` and `prod` AWS environments in the Frankfurt
region (`eu-central-1`). They share one AWS account and one Attio workspace,
but have separate networks, databases, secrets, container repositories, and
deployment roles. Attio's test flag separates development records from
production ones.

| Environment | Change path | n8n | Toolkit and lead tools |
| --- | --- | --- | --- |
| Development | Merge to `dev`, or run `Deploy dev` | `https://n8n-dev.wusoolcapital.com/` | A fixed `sslip.io` hostname set in the development `tfvars`; no tools hostname |
| Production | Merge to `prod`, or run `Deploy prod` | `https://n8n.wusoolcapital.com/` | `https://tools.wusoolcapital.com/` |

DNS is managed in Cloudflare, outside the repository.

## Architecture viewer

The interactive architecture diagram is served at `/architecture/` on the
Toolkit host, behind Caddy Basic Auth, in both environments. The username is
`architecture`; the password is the `env.ARCHITECTURE_BASIC_AUTH_PASSWORD`
field of the Toolkit secret. If that field is missing, the instance bootstrap
stops rather than serve the viewer unprotected.

## Required access

Give each operator the minimum role for the task.

| System | Needed for |
| --- | --- |
| GitHub repository and Actions | Review changes, inspect checks, deploy, and rerun workflows. Environments: `dev`, `prod`, and `scribe-release`. |
| AWS, through the approved sign-in | Logs, alarms, Systems Manager, RDS, Secrets Manager, and OpenTofu. Includes Bedrock model access and SES sending. |
| Slack administration | The Toolkit app, and the AWS Chatbot alerts channel |
| Attio administration | CRM attributes, lists, webhooks, and users |
| Sanity | The Reports Studio project: member invites, API tokens, and webhooks |
| Webflow | The site, and a CMS read/write API token |
| Cloudflare | Service DNS records |
| n8n owner or administrator | Users, credentials, workflows, and execution history |
| Google Cloud | The Places and Geocoding API key used by seller discovery |
| Firecrawl, Diffbot, People Data Labs | API keys for enrichment and the lead tools |

There is no Apple Developer account: Scribe is ad-hoc signed. Releasing Scribe
needs the Tauri update-signing key, held as GitHub secrets in the
`scribe-release` environment. Deploys need no stored AWS secrets; GitHub
signs in through OIDC.

SES sender identities and whether the account is out of the SES sandbox are
not managed in the repository; check them in the AWS console.

Named owners and the access-request route are **not recorded here**. Never
document account numbers, role identifiers, tokens, or personal credentials
in these pages.

## Verify access before a change

1. Confirm the intended environment and Git branch (`dev` or `prod`).
2. Confirm GitHub shows the matching deployment environment and recent runs.
3. Sign in to AWS and check your identity and the Frankfurt region.
4. For shell work, confirm the instance is online in Systems Manager.
5. For database work, use a Systems Manager tunnel or run from the Toolkit
   instance; direct internet access must fail.
6. Open the service URL and confirm it is healthy before changing it.

**If verification fails:** stop before deploying, and ask the system owner to
restore the missing least-privilege access. Escalate at once if a private
service is publicly reachable, or if development credentials can change
production.
