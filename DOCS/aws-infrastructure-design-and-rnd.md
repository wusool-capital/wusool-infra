![Document preview](images/document-thumbnail.jpeg)

> Preview thumbnail exported from the source Word document (`DOCS/AWS_Infrastructure_Design_and_RnD_Document_v2.docx`).

# AWS Infrastructure Design & R&D Document

| Field | Value |
| ----- | ----- |
| **Project** | AWS Infrastructure Setup & n8n Deployment (Development & Production) |
| **Version** | 1.0 |
| **Status** | Draft for Review |

---

## 1. Objective

Design a secure, scalable, and maintainable AWS infrastructure for hosting n8n using separate Development and Production environments. The infrastructure will follow AWS best practices, Infrastructure as Code (Terraform), and the principle of least privilege.

## 2. Scope

- Two environments: Development and Production
- Two separate VPCs
- One EC2 instance per environment for hosting n8n
- AWS Region: Middle East (UAE) (`me-central-1`)
- Terraform for infrastructure provisioning
- IAM-based access control

## 3. Proposed Architecture

**Single AWS Account**

```
Single AWS Account
├── Development VPC
│   ├── Public Subnet
│   ├── Private Subnet
│   └── EC2 (n8n Dev)
└── Production VPC
    ├── Public Subnet
    ├── Private Subnet
    └── EC2 (n8n Prod)
```

## 4. Region Selection

**Region:** Middle East (UAE) — `me-central-1`

**Reason:** Low latency for UAE users, future compliance, and keeping all workloads close to customers.

## 5. Network Design

### Development VPC

| Component | CIDR |
| --------- | ---- |
| VPC | `10.10.0.0/16` |
| Public Subnet | `10.10.1.0/24` |
| Private Subnet | `10.10.2.0/24` |

### Production VPC

| Component | CIDR |
| --------- | ---- |
| VPC | `10.20.0.0/16` |
| Public Subnet | `10.20.1.0/24` |
| Private Subnet | `10.20.2.0/24` |

## 6. Compute Design

- Development EC2 hosts development n8n.
- Production EC2 hosts production n8n.
- Amazon Linux 2023 + Docker + Docker Compose.

## 7. Security Design

- Root account only for emergencies.
- IAM roles for Admin and Developer.
- MFA enabled.
- CloudTrail enabled.
- Least privilege access.
- Separate Security Groups for ALB and EC2.

## 8. Infrastructure as Code

Terraform repository layout:

```
terraform/
├── dev/
└── prod/
modules/
├── vpc/
├── ec2/
└── security-groups/
```

## 9. Future Enhancements

- Application Load Balancer
- RDS PostgreSQL
- Redis
- Route53
- ACM SSL
- CloudWatch
- AWS Backup
- Secrets Manager

## 10. Implementation Phases

1. Finalize architecture
2. Review with team
3. Create Terraform
4. Deploy Dev
5. Test
6. Deploy Production
7. Configure monitoring and backups

## 11. Key Decisions

- Region: `me-central-1`
- Two VPCs (Dev & Prod)
- Separate EC2 per environment
- Docker-based deployment
- Terraform-managed infrastructure
- Secure IAM access model

## 12. End-to-End Deployment Flow

AWS Account Creation → Secure Root User (MFA) → Create IAM Admin User → Login as IAM User → Create IAM Developer User → Create Dev & Prod VPCs → Public & Private Subnets → Internet Gateway → Route Tables → NAT Gateway (optional initially) → Security Groups → EC2 → Connect → Install Docker → Install Docker Compose → Deploy n8n → Domain → HTTPS → CloudWatch → Backups → Production.

## 13. What Happens After EC2?

- Connect to EC2.
- Update OS.
- Install Docker.
- Install Docker Compose.
- Create persistent n8n volume.
- Create `docker-compose.yml`.
- Configure environment variables.
- Start n8n.
- Verify with `docker ps`.
- View logs.
- Upgrade containers safely.

## 14. Domain & HTTPS

Configure DNS, Nginx reverse proxy, Let's Encrypt SSL (Certbot), expose only ports 80/443, and close public access to port 5678.

## 15. Terraform Workflow

Write code → `terraform init` → `terraform plan` → `terraform apply`.

Covers providers, resources, variables, outputs, modules, and state files.

## 16. AWS Console vs Terraform

| AWS Console | Terraform |
| ----------- | --------- |
| VPC | `aws_vpc` |
| Subnet | `aws_subnet` |
| Internet Gateway | `aws_internet_gateway` |
| Security Group | `aws_security_group` |
| EC2 | `aws_instance` |

## 17. Production Best Practices

- Private EC2 behind ALB
- PostgreSQL
- Secrets Manager
- CloudWatch & CloudTrail
- Backups
- Least-privilege IAM
- Resource tagging
- Separate Dev & Prod
