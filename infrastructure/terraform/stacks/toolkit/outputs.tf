# try(..., "") not try(..., null): OpenTofu silently OMITS null-valued outputs
# from state entirely (verified) — not stored as null, just absent, which
# breaks any consumer reading data.terraform_remote_state.toolkit.outputs.X
# with "Unsupported attribute". Empty string is always present and compact()
# (used by stacks/postgres) already treats "" the same as null.

# No stable instance_id — the instance is ASG-managed and can be replaced at
# any time. CI must look up the live instance instead:
#   aws ec2 describe-instances --filters \
#     "Name=tag:Name,Values=wusool-<env>-toolkit" "Name=instance-state-name,Values=running"
# (that tag value, NOT this ASG's own name — the ASG uses name_prefix and
# carries a random suffix; the instance Name tag it propagates does not).
# Kept mainly for direct `aws autoscaling describe-auto-scaling-groups` use.
output "autoscaling_group_name" {
  value = try(module.wusool_toolkit[0].autoscaling_group_name, "")
}

output "public_ip" {
  value = try(module.wusool_toolkit[0].public_ip, "")
}

output "security_group_id" {
  value = try(module.wusool_toolkit[0].security_group_id, "")
}

output "iam_role_name" {
  value = try(module.wusool_toolkit[0].iam_role_name, "")
}

output "app_urls" {
  value = try(module.wusool_toolkit[0].app_urls, {})
}

output "ssm_instance_id" {
  value = try(module.wusool_toolkit[0].ssm_instance_id, "")
}

output "redeploy_command" {
  value = try(module.wusool_toolkit[0].redeploy_command, "")
}

output "secret_name" {
  value = aws_secretsmanager_secret.wusool_toolkit.name
}

output "secret_arn" {
  value = aws_secretsmanager_secret.wusool_toolkit.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.wusool_toolkit.repository_url
}

output "bootstrap_document_name" {
  value = try(module.wusool_toolkit[0].bootstrap_document_name, "")
}
