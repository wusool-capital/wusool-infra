variable "project" {
  description = "Project name used in resource names and log paths."
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the instance will be created."
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for the EC2 instance (public subnet)."
  type        = string
}

variable "key_name" {
  description = "Name of an existing EC2 key pair for SSH access. Leave empty when using SSM only."
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "EC2 instance type. t2.micro is the AWS Free Tier instance guaranteed available in every region (t3.micro is the fallback where t2.micro isn't offered)."
  type        = string
  default     = "t2.micro"
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB. 30 GiB gp2/gp3 is covered by the AWS Free Tier."
  type        = number
  default     = 20
}

variable "ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH into the instance. Leave empty to rely on SSM Session Manager only."
  type        = list(string)
  default     = []
}

variable "web_cidr_blocks" {
  description = "CIDR blocks allowed to reach HTTP/HTTPS (Slack's Events API needs to reach this instance)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "git_repo_url" {
  description = "HTTPS clone URL of the repo containing the app(s) (without credentials)."
  type        = string
  default     = "https://github.com/wusool-capital/wusool-infra.git"
}

variable "git_ref" {
  description = "Branch or tag to check out on deploy."
  type        = string
  default     = "main"
}

variable "apps" {
  description = "One entry per bot service hosted on this instance. Each gets its own Caddy virtual host (subdomain), Docker Compose service, and Secrets Manager secret; all run on the same EC2 instance behind the same Elastic IP."
  type = list(object({
    # Short slug used as the docker-compose service name, the Caddy access-log
    # filename, and the CloudWatch log-stream suffix.
    name = string
    # Path within the cloned repo to this app's Dockerfile.
    app_subdir = string
    # Secrets Manager secret ID/ARN holding this app's runtime secrets:
    # slack_bot_token, slack_signing_secret, database_url, github_token (a
    # fine-grained PAT with read-only access to git_repo_url), and an
    # optional env map of extra overrides.
    app_secret_id = string
    # Public HTTPS URL for this app (used as its Slack Request URL host).
    # Empty derives an sslip.io hostname from the shared Elastic IP, prefixed
    # with `name`.
    public_url = optional(string, "")
  }))

  validation {
    condition     = length(var.apps) > 0
    error_message = "At least one app must be configured."
  }
  validation {
    condition     = length(distinct([for a in var.apps : a.name])) == length(var.apps)
    error_message = "Each app's name must be unique."
  }
}

variable "secrets_manager_secret_arns" {
  description = "Secrets Manager secret ARNs the instance role can read (normally just app_secret_id's ARN)."
  type        = list(string)
  default     = []
}

variable "alarm_topic_arn" {
  description = "SNS topic ARN receiving EC2 alarms; empty disables alarm actions."
  type        = string
  default     = ""
}

variable "aws_region" {
  description = "AWS region the app calls Bedrock in (passed through as AWS_REGION)."
  type        = string
  default     = "eu-central-1"
}

variable "ami_id" {
  description = "AMI to launch. Pinned explicitly (H1) — see main.tf's comment above the removed data source for why. Set this to the AMI currently running before changing anything else, then treat any change to it as a deliberate, reviewed upgrade."
  type        = string
}
