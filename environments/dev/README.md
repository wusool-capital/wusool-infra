# Development environment

See the [development infrastructure architecture](../../DOCS/dev-infrastructure-architecture.md)
for diagrams of the deployed AWS resources, request path, and operational controls.

The development environment runs n8n on an Amazon Linux EC2 instance in
Frankfurt (`eu-central-1`). Terraform state is stored remotely in the S3
backend declared in `backend.tf`.

## Architecture

- VPC with public and private subnets
- EC2 with an encrypted root volume and Elastic IP
- Docker Compose running n8n and Caddy
- HTTPS through an IP-derived `sslip.io` hostname
- Port 5678 closed publicly; Caddy proxies HTTPS traffic to n8n internally
- EC2 IAM role for Systems Manager and CloudWatch Agent
- No public SSH ingress; administrators connect through Systems Manager
- CloudWatch logs, instance health alarm, and high-CPU alarm
- SNS email notifications
- CloudTrail with a private, encrypted, versioned S3 bucket
- GuardDuty and Security Hub

## Local configuration

Copy the example and fill in local values. The resulting file is ignored by
Git and must not be committed.

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
```

Required local values include the EC2 key-pair name, the administrator's
current public IP in CIDR notation, and the alert email address.

## Workflow

```powershell
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

After apply, use `terraform output n8n_url` for the HTTPS endpoint. Confirm the
SNS subscription email before expecting alerts. Use the `ssm_command` output
for shell access without exposing SSH more broadly.

Never commit `.terraform/`, `tfplan`, `terraform.tfvars`, state files, private
keys, or AWS credentials.
