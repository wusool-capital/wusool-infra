# Delivery status and open items

This register separates repository-confirmed capability from production claims
that require live verification. Update it at each client handover or material
release.

| Capability | Repository evidence | Handover status |
| --- | --- | --- |
| Development and production AWS environments | Separate environment configuration, networks, databases, secrets, repositories, and deployment roles | Delivered; confirm live state |
| Branch-based continuous deployment | `Deploy dev` and `Deploy prod` workflows build, apply, migrate, roll out, and health-check | Delivered |
| Toolkit and Slack workflows | Application modules and production Toolkit infrastructure are present | Delivered; verify Slack routing live |
| PostgreSQL | Private encrypted RDS, deletion protection, managed credentials, seven-day backups | Delivered; restore test outstanding |
| Attio real-time sync | Signed webhook implementation | Delivered; verify current webhook subscription live |
| Attio nightly full resync | Scheduled production workflow | Delivered; automatic failure notification outstanding |
| n8n | Dev/prod infrastructure, HTTPS configuration, pinned images, logs and alarms | Delivered; recovery procedure outstanding |
| WusoolScribe | Application integration and update infrastructure are documented | Production environment and release state require live verification |
| Website lead tools | Production hostname and Toolkit hosting configuration are present | Production DNS, secret, deploy, and end-to-end status require live verification |
| Monitoring baseline | Toolkit/n8n alarms, logs, security findings, email/chat routing configuration | Delivered in code; recipients and live delivery require verification |

## Open handover items

| Priority | Item | Completion evidence |
| --- | --- | --- |
| High | Assign primary and backup client owners and document access/escalation routes | Completed ownership register and access review |
| High | Add failure notification for the nightly Attio resync | Deliberately failed test run produces an acknowledged alert |
| High | Define recovery targets and test PostgreSQL restore | Approved RTO/RPO and dated restore-test record |
| High | Define, implement, and test n8n data backup/recovery | Successful isolated restore with documented data coverage |
| High | Reconcile Attio and PostgreSQL and confirm all current migrations in production | Signed reconciliation and migration evidence |
| Medium | Bring the production n8n re-provisioning procedure in line with the current module | Reviewed drill using current configuration |
| Medium | Verify production lead-tool DNS, secret, deployment, and each end-to-end submission | Dated production smoke-test evidence |
| Medium | Verify Scribe production release, update path, and client access | Dated install/update/CRM submission test |
| Medium | Confirm People Data Labs response handling against an authorized live account | Recorded successful enrichment test |
| Medium | Verify operational and security alert subscriptions and chat authorization | Dated alert-delivery drill |

## Sign-off rule

Do not describe an item as live from repository configuration alone. Mark it
verified only when an operator records the environment, date, evidence, and
result. Any failed critical check remains open with an owner and target date.
