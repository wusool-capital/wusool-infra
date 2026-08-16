variable "project" {
  type    = string
  default = "wusool"
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "owner" {
  type    = string
  default = "wusool-infra"
}

variable "key_name" {
  type    = string
  default = ""
}

variable "create_instance" {
  description = "Whether to create the EC2 instance for this environment. false lets ECR + the secret exist (e.g. prepared ahead of time) without a running, billable instance — used for prod until the instance is deliberately created."
  type        = bool
  default     = true
}

# NOT named "instance_type" — stacks/n8n also declares a same-named variable,
# and both stacks read the same shared envs/<env>.tfvars file. A generic name
# here would silently pick up n8n's value (discovered live: n8n's t3.small
# leaked into toolkit's plan during the Phase D migration).
variable "toolkit_instance_type" {
  description = "EC2 instance type for the wusool-toolkit app."
  type        = string
  default     = "t2.micro"
}

variable "ami_architecture" {
  type    = string
  default = "x86_64"
}

variable "root_volume_size" {
  type    = number
  default = 30
}

variable "ssh_cidr_blocks" {
  type    = list(string)
  default = []
}

variable "web_cidr_blocks" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "git_repo_url" {
  type    = string
  default = "https://github.com/wusool-capital/wusool-infra.git"
}

variable "git_ref" {
  description = "Branch to deploy. MUST contain workflows/wusool-toolkit/ — the stale `main` branch does not."
  type        = string
  default     = "dev"
}

variable "public_url" {
  description = "Public HTTPS URL for the app. Empty derives an sslip.io hostname from its Elastic IP."
  type        = string
  default     = ""
}

variable "enable_bedrock" {
  type    = bool
  default = false
}

variable "bedrock_models" {
  type = list(object({
    model_id             = string
    region               = string
    inference_profile_id = optional(string)
  }))
  default = []
}

variable "alert_email" {
  type    = string
  default = ""
}
