# No stable instance_id output anymore — the ASG can replace the instance at
# any time, so this ID is a snapshot the moment `apply` ran, not a durable
# handle. Consumers that need the CURRENT instance (CI's SSM send-command
# steps) must look it up live by the "Name" tag propagated to every instance
# this ASG launches ("${var.project}-${var.environment}-toolkit" — NOT this
# ASG's own name, which uses name_prefix and carries a random suffix):
#   aws ec2 describe-instances --filters \
#     "Name=tag:Name,Values=${var.project}-${var.environment}-toolkit" \
#     "Name=instance-state-name,Values=running"
output "autoscaling_group_name" {
  description = "Name of the ASG itself (has a random suffix from name_prefix) — for direct ASG API calls, not for finding the current instance."
  value       = aws_autoscaling_group.wusool_toolkit.name
}

output "public_ip" {
  description = "Elastic IP address assigned to the wusool-toolkit instance."
  value       = aws_eip.wusool_toolkit.public_ip
}

output "security_group_id" {
  description = "Security group ID attached to the wusool-toolkit instance."
  value       = aws_security_group.wusool_toolkit.id
}

output "app_urls" {
  description = "Map of app name to its HTTPS URL served by Caddy. Each app's Slack Events/interactivity Request URL is its value plus /slack/events."
  value       = { for app in local.apps_resolved : app.name => app.url }
}

output "iam_role_name" {
  description = "Name of the IAM role attached to the wusool-toolkit EC2 instance profile."
  value       = aws_iam_role.wusool_toolkit.name
}

output "redeploy_command" {
  description = "Shell one-liner to look up the current instance and trigger a redeploy (docker pull the pinned digest + restart) without replacing it — no stable instance ID to bake in ahead of time now that the instance is ASG-managed."
  value       = "aws ec2 describe-instances --filters Name=tag:Name,Values=${var.project}-${var.environment}-toolkit Name=instance-state-name,Values=running --query 'Reservations[0].Instances[0].InstanceId' --output text | xargs -I{} aws ssm send-command --document-name ${aws_ssm_document.bootstrap.name} --instance-ids {}"
}

output "bootstrap_document_name" {
  description = "SSM document name to trigger a redeploy via send-command."
  value       = aws_ssm_document.bootstrap.name
}
