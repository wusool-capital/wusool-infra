# Environment

The platform runs in a single AWS account in the Frankfurt (`eu-central-1`)
region.

| Item | Value |
| --- | --- |
| n8n | `https://n8n.wusoolcapital.com/` |
| Toolkit bot Slack Request URL | Provisioned — confirm the current live hostname before handover. |
| DNS | Managed in Cloudflare, pointing at each service's address. |
| Region | `eu-central-1` (Frankfurt) |

## Infrastructure as code

All infrastructure is defined in OpenTofu and applied automatically from
source control — see [Deployment](../technical/deployment.md).
