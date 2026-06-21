output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.n8n.id
}

output "public_ip" {
  description = "Elastic IP address assigned to the n8n instance."
  value       = aws_eip.n8n.public_ip
}

output "security_group_id" {
  description = "Security group ID attached to the n8n instance."
  value       = aws_security_group.n8n.id
}

output "n8n_url" {
  description = "HTTPS URL served by Caddy."
  value       = "https://${local.public_hostname}"
}

output "ssm_instance_id" {
  description = "Instance ID usable with AWS Systems Manager Session Manager."
  value       = aws_instance.n8n.id
}
