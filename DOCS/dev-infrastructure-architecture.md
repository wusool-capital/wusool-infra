# Wusool n8n Development Infrastructure

This diagram is derived from the Terraform in `environments/dev`,
`modules/network`, `modules/n8n-ec2`, and `bootstrap-frankfurt`.

![Wusool development AWS network architecture](wusool-dev-network-diagram.svg)

For a Markdown-only version, see
[Wusool development network diagram](wusool-dev-network-diagram.md).

```mermaid
flowchart TB
  user([n8n users])
  admin([Administrator / Terraform])

  subgraph aws["AWS account 030179310793 - eu-central-1"]
    direction TB

    state[("S3 Terraform state<br/>encrypted - versioned - private<br/>native state locking")]

    subgraph vpc["Development VPC"]
      direction TB
      igw[Internet Gateway]

      subgraph public["Public subnet"]
        eip["Elastic IP + sslip.io DNS"]
        sg["n8n security group<br/>80/443 inbound - 5678 closed"]

        subgraph ec2["Amazon Linux 2023 EC2 - t3.small"]
          direction TB
          caddy["Caddy container<br/>TLS termination + reverse proxy"]
          n8n["n8n container<br/>port 5678 internal only"]
          data[("Docker n8n_data volume<br/>on encrypted gp3 EBS")]
          cwagent[CloudWatch Agent]
          ssmagent[SSM Agent]

          caddy -->|HTTP :5678| n8n
          n8n --- data
        end
      end

      subgraph private["Private subnet · reserved"]
        privateRT["Private route table<br/>no internet route / no workload"]
      end

      igw --> eip
      eip --> sg --> caddy
    end

    iam["EC2 IAM role<br/>SSM + CloudWatch policies"]
    ssm["AWS Systems Manager<br/>bootstrap document + association"]
    logs["CloudWatch Logs<br/>30-day retention"]
    alarms["CloudWatch alarms<br/>instance status + CPU > 85%"]
    sns["SNS topic<br/>email notifications"]

    trail["Multi-region CloudTrail<br/>log validation enabled"]
    audit[("S3 CloudTrail logs<br/>encrypted - versioned - private")]
    guard[GuardDuty]
    hub[Security Hub]

    iam --- ec2
    ssm -->|bootstrap/configure| ssmagent
    cwagent --> logs
    ec2 --> alarms --> sns
    trail --> audit
  end

  user -->|HTTPS :443| igw
  admin -->|Terraform plan/apply| state
  admin -->|Session Manager - no public SSH| ssm
```

## Request and operations flow

```mermaid
sequenceDiagram
  actor User
  participant DNS as sslip.io / Elastic IP
  participant Caddy as Caddy :443
  participant N8N as n8n :5678
  participant Data as Persistent Docker volume
  participant CW as CloudWatch / SNS

  User->>DNS: Open HTTPS endpoint
  DNS->>Caddy: TLS request through security group
  Caddy->>N8N: Reverse proxy over Docker network
  N8N->>Data: Read/write users, workflows and credentials
  N8N-->>User: n8n UI/API response
  CW-->>CW: Monitor EC2 status and CPU
  CW-->>User: Alert email when alarm changes state
```

## Security boundaries

- Only HTTP and HTTPS are normally public; n8n port `5678` is not exposed.
- Administration uses AWS Systems Manager. Public SSH is disabled when
  `ssh_cidr_blocks` is empty, as in the supplied development configuration.
- The EC2 root disk, Terraform state, and CloudTrail logs are encrypted.
- Instance Metadata Service v2 tokens are required.
- The private subnet currently has no workload and no outbound internet route.
- GuardDuty, Security Hub, CloudTrail, CloudWatch alarms, and SNS provide
  detection, audit, monitoring, and notification coverage.
