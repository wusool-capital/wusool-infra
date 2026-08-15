output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.matching_engine.id
}

output "public_ip" {
  description = "Elastic IP address assigned to the matching-engine instance."
  value       = aws_eip.matching_engine.public_ip
}

output "security_group_id" {
  description = "Security group ID attached to the matching-engine instance."
  value       = aws_security_group.matching_engine.id
}

output "app_urls" {
  description = "Map of app name to its HTTPS URL served by Caddy. Each app's Slack Events/interactivity Request URL is its value plus /slack/events."
  value       = { for app in local.apps_resolved : app.name => app.url }
}

output "ssm_instance_id" {
  description = "Instance ID usable with AWS Systems Manager Session Manager."
  value       = aws_instance.matching_engine.id
}

output "iam_role_name" {
  description = "Name of the IAM role attached to the matching-engine EC2 instance profile."
  value       = aws_iam_role.matching_engine.name
}

output "redeploy_command" {
  description = "AWS CLI command to trigger a redeploy (git pull + rebuild + restart) without replacing the instance."
  value       = "aws ssm send-command --document-name ${aws_ssm_document.bootstrap.name} --instance-ids ${aws_instance.matching_engine.id}"
}
