# Documentation synchronization policy

## Managed-section markers

When a document needs a repeatedly generated structured section, wrap only
that section with:

```markdown
<!-- BEGIN TERRAFORM-DOCS: section-name -->
generated content
<!-- END TERRAFORM-DOCS: section-name -->
```

Replace content only between matching markers. Never put an entire document
inside one generated block.

Suggested section names:

- `current-architecture`
- `repository-structure`
- `environment-dev`
- `terraform-inputs`
- `terraform-outputs`
- `security-controls`

## Diagram conventions

- Show AWS region, VPC CIDR, subnet CIDRs and route behavior.
- Separate public, private, and AWS-managed-service boundaries.
- Label ingress ports and internal proxy ports.
- Show state storage, management access, monitoring, alerting, and audit flow.
- Use solid blue arrows for application traffic and dashed gray arrows for
  management or telemetry.
- Include a generated-from-Terraform note, but do not claim live-state proof.

## Review checklist

- Region and account references
- Backend bucket, state key, encryption, versioning, and locking method
- VPC/subnet CIDRs and routes
- Instance family, architecture, AMI family, disk type and size
- Public IP/EIP, DNS, TLS proxy, exposed ports, and SSH/SSM access
- IAM policies, CloudWatch, SNS, CloudTrail/S3, GuardDuty, Security Hub
- Terraform outputs and operator commands
- Repository tree contains only paths that really exist
- No ignored local values, secrets, personal emails, or public IPs copied
