# Ownership and service dependencies

The repository defines technical boundaries but doesn't name the people
accountable for them. Fill in the owner and billing columns during handover,
and keep them current in the client's operations register.

## Systems

| System | Responsibility | Client owner |
| --- | --- | --- |
| GitHub and Actions | Source control, checks, deployment and release history | Unassigned |
| AWS infrastructure | Network, compute, RDS, ECR, Systems Manager, logs, alarms, secrets | Unassigned |
| Toolkit application | Slack commands, matching, enrichment, discovery, lead tools, reports | Unassigned |
| PostgreSQL and CRM sync | Schema, migrations, webhook and nightly reconciliation | Unassigned |
| Attio | CRM structure, data quality, users, webhooks | Unassigned |
| Slack | Toolkit app, workspace access, alerts channel | Unassigned |
| Sanity Reports Studio | Report and article content, editors, webhooks | Unassigned |
| Webflow | The website and its CMS collections | Unassigned |
| n8n | Users, workflows, credentials, execution history | Unassigned |
| Cloudflare | Public DNS for service hostnames | Unassigned |
| WusoolScribe | Desktop releases, update feed, signing key, CRM submission | Unassigned |

## Paid and external services

Billing owners and plans aren't recorded in the repository unless stated.

| Service | Used for | Plan or billing |
| --- | --- | --- |
| AWS (EC2, RDS, S3, CloudFront, SES, SNS, Chatbot, GuardDuty, Security Hub) | All hosting, email, alerts, and security monitoring | Unknown |
| Amazon Bedrock | AI for matching, discrepancy checks, enrichment, summaries, and the lead tools | Billed through AWS |
| Attio | CRM of record | Unknown |
| Sanity | Report and article content | Free plan |
| Webflow | Website and CMS | Unknown |
| Google Cloud (Places, Geocoding) | Seller discovery | Unknown |
| Firecrawl | Web search for enrichment and Valuation | Unknown |
| Diffbot | Structured company data | Free tier, 10,000 credits a month |
| People Data Labs | Structured company data | Free tier, 100 lookups a month |
| Slack | Toolkit bot and alerts | Unknown |
| Cloudflare | DNS | Unknown |
| GitHub | Source control and Actions | Unknown |

## Dependency map

See the infrastructure diagram on
[Platform architecture](../technical-documentation/technical.md#infrastructure-at-a-glance).

An incident owner should follow the first failed boundary:

- Failed Slack commands while the Toolkit is healthy: start with Slack
  request routing.
- Toolkit database errors: start with RDS reachability and credentials.
- Missing CRM updates: start with the webhook, the nightly run, and
  reconciliation.
- A report not updating on the website: start with the Sanity webhook and the
  Toolkit's sync logs.

## Handover checklist

- Assign a primary and backup owner for every system.
- Record the access-request and emergency-contact route outside these public
  pages.
- Confirm billing and renewal ownership for every service above.
- Confirm alert recipients and how quickly alerts must be acknowledged.
- Confirm where incident, change, recovery-test, and reconciliation records
  are kept.
- Remove departing suppliers and staff from every system, and rotate shared
  credentials, including the desktop API key and the Scribe signing key.

**Expected outcome:** an incident can be routed to a named person and supplier
without relying on the original delivery team.
