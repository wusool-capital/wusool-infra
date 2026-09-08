# Ownership and support

## Deployment and ownership

- **Infrastructure as code:** OpenTofu, version-pinned in the repository.
- **Deploy trigger:** a merge to the main branch. The pipeline builds the
  application, applies any changed infrastructure, runs any pending
  database migration, rolls out the new application version, and confirms
  it's healthy before considering the deploy successful.
- **No manual approval gate** exists before a production deploy — this is a
  deliberate, documented choice, given every deploy is health-checked
  automatically and the impact of any one change is kept small.
- **Secrets** live only in AWS Secrets Manager. They are never stored in
  source control or in plain configuration files.
- **Alerts:** operational issues are emailed automatically to the
  engineering owner.

## Administrative access

- Shell access to servers is via **AWS Systems Manager Session Manager** —
  there is no SSH access by default.
- The database is **not publicly reachable** — it's reached only from the
  application server itself or through a secure tunnel.

## Support

| Need | Start here |
| --- | --- |
| How to use the bot | [User Guide — Wusool Toolkit](../user-guide/toolkit/README.md) |
| How to use WusoolScribe | [User Guide — WusoolScribe](../user-guide/scribe/README.md) |
| Architecture, deployment, configuration | [Technical Documentation](../technical/README.md) |

### Safety rules

- Infrastructure changes are made through source control, not by hand in
  the AWS console. Any emergency console change is reconciled back into
  source control immediately afterward.
