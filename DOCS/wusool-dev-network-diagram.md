# Wusool Development Network Diagram

This diagram is derived from the Terraform configuration in
`environments/dev`, `modules/network`, and `modules/n8n-ec2`.

```mermaid
flowchart LR
  user([n8n users])
  admin([Administrator])

  subgraph aws["AWS · eu-central-1 (Frankfurt)"]
    direction LR

    igw[Internet Gateway]

    subgraph vpc["Development VPC · 10.10.0.0/16"]
      direction LR

      subgraph public["Public subnet · 10.10.1.0/24"]
        direction LR
        eip[Elastic IP<br/>sslip.io hostname]
        sg[Security group<br/>80/443 allowed<br/>5678 and SSH closed]

        subgraph ec2["EC2 · t3.small · Amazon Linux 2023"]
          direction TB
          caddy[Caddy<br/>TLS and reverse proxy]
          n8n[n8n container<br/>internal port 5678]
          ebs[(Encrypted gp3 EBS<br/>30 GiB)]
          cwagent[CloudWatch Agent]
          ssmagent[SSM Agent]

          caddy -->|HTTP :5678| n8n
          n8n --- ebs
        end
      end

      subgraph private["Private subnet · 10.10.2.0/24"]
        reserved[Reserved<br/>No workload<br/>No internet route]
      end
    end

    ssm[AWS Systems Manager<br/>Session and bootstrap]
    cloudwatch[CloudWatch<br/>Logs and alarms]
    sns[SNS<br/>Email notifications]
    cloudtrail[CloudTrail]
    audit[(Private encrypted S3<br/>Audit logs)]
    guardduty[GuardDuty]
    securityhub[Security Hub]
    state[(S3 Terraform state<br/>Encrypted and versioned<br/>Native lock file)]

    igw --> eip
    eip --> sg
    sg -->|HTTPS :443| caddy

    ssm --> ssmagent
    cwagent --> cloudwatch
    cloudwatch --> sns
    cloudtrail --> audit
  end

  user -->|HTTPS :443| igw
  admin -. Terraform plan/apply .-> state
  admin -. Session Manager .-> ssm
```

## Traffic flow

1. Users connect to the public `sslip.io` hostname over HTTPS.
2. The Internet Gateway routes traffic to the EC2 Elastic IP.
3. The security group permits HTTP and HTTPS traffic.
4. Caddy terminates TLS and proxies requests to n8n on internal port `5678`.
5. n8n stores persistent data on the encrypted EC2 root volume.

## Administration and monitoring

- Administrators connect through AWS Systems Manager; public SSH is disabled.
- CloudWatch collects logs and monitors EC2 status and CPU usage.
- SNS sends alarm notifications by email.
- CloudTrail stores audit logs in an encrypted, private, versioned S3 bucket.
- GuardDuty and Security Hub provide threat detection and security findings.

> This represents the architecture declared in Terraform, not a live AWS
> inventory.
