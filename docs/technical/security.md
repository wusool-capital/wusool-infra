# Security and data handling

## Trust boundaries

| Boundary | Control |
| --- | --- |
| Slack → Toolkit | Slack Bolt validates request signatures with the signing secret. |
| WusoolScribe → Toolkit | Every `/desktop/*` call requires a shared bearer API key. |
| Attio → Toolkit | Webhook signature verification; optional expected-workspace enforcement. |
| Browser → lead tools | HTTPS, CORS, iframe `frame-ancestors`, validation, idempotency, and rate limiting. |
| Internet → AWS | Security-group allowlists and Caddy HTTPS termination. |
| Runtime → services | Scoped instance roles and runtime-supplied third-party secrets. |
| Operators → instances | Systems Manager normally; SSH only when explicitly configured. |

## Credentials and access

Application secrets live in AWS Secrets Manager and are read by the relevant
instance role. GitHub Actions uses AWS OIDC roles rather than committed AWS
keys. Local `.env` files and optional local AWS credentials are development
mechanisms and must never be committed. n8n maintains its own users and stored
workflow credentials.

The Toolkit has no separate Slack-user allowlist beyond membership and
permissions in the configured Slack workspace/app. Treat app installation
scope and channel access as part of the authorization boundary.

## Data handling by product

### Wusool Toolkit

Buyer, seller, meeting-note, and match data is read from PostgreSQL and Attio.
Requirement extraction, shortlist reasoning, enrichment normalization, and
server-side meeting summaries go to configured Bedrock models. Firecrawl,
Diffbot, and People Data Labs receive only enabled lookup inputs.

### WusoolScribe

Recording and Whisper transcription run locally. Content leaves the device
when the user selects a remote summary provider or pushes a meeting. Remote
providers receive summary content; CRM push sends transcript and metadata to
the Wusool backend, which uses Bedrock and Attio. Update checks contact the
distribution feed.

### Website lead tools

The backend records submitted identity, company, financial, questionnaire, and
consent data in `tool_runs` before downstream processing. Relevant inputs may
go to Bedrock or Firecrawl, then approved fields go to Attio and PostgreSQL.
Test submissions are stamped `is_test`.

### n8n

n8n workflow data and credentials persist in its application volume. A
workflow can send data to any service its owner configures, so each client
workflow needs an explicit data-flow and credential review.

## Storage, logging, and examples

RDS and EC2 root volumes are encrypted through infrastructure definitions;
OpenTofu state uses an encrypted, versioned S3 backend. CloudWatch receives
selected system/bootstrap and access logs. Application logs must avoid bearer
tokens, provider keys, transcript bodies, and personal/financial payloads.
Bootstrap disables shell tracing before reading the n8n secret so values do not
enter SSM command history or CloudWatch.

Documentation, tests, screenshots, and support messages must use synthetic or
redacted people, organizations, credentials, transcripts, and financial data.

## Security failure behavior

- Authentication and signature failures are rejected before processing.
- Missing optional provider credentials disable that provider; missing core
  Slack, database, Attio, or desktop credentials stop the affected feature.
- An incorrect `ATTIO_IS_TEST` value is a data-isolation incident. Stop writes,
  preserve evidence, correct the environment, and reconcile affected records.
- Host/process alarms do not guarantee successful CRM sync, n8n workflows,
  Bedrock calls, or lead completion; operations must check those separately.
