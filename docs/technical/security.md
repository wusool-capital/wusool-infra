# Security

## Authentication and authorization

| Boundary | Mechanism |
| --- | --- |
| Slack → server | Every request's signature is verified against the Slack signing secret. |
| Attio → server webhook | HMAC signature check. |
| WusoolScribe → server | Shared API key (`Authorization: Bearer <key>`). |
| CI/CD → AWS | Short-lived, role-based credentials — no static AWS keys stored anywhere. |
| Server → AWS (Bedrock, etc.) | The server's own instance/task role. |
| Server → database | Credentials from AWS Secrets Manager. |
| End users → bot commands | None — any workspace member can run any command (see [Known limitations](../handover/limitations.md)). |

## Administrative access

- Shell access to servers is via **AWS Systems Manager Session Manager** —
  there is no SSH.
- The database is **not publicly reachable** — it's reached only from the
  server itself or via a secure port-forward tunnel.

## Secrets

Secrets live only in **AWS Secrets Manager**. They are never committed to
source control or stored in plain configuration files.

## Monitoring

CloudWatch logs and alarms, email alerts on operational issues, audit
logging, and account-wide threat detection are all in place across the
platform.
