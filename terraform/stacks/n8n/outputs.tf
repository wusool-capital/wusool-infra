output "instance_id" {
  value = module.n8n.instance_id
}

output "public_ip" {
  value = module.n8n.public_ip
}

output "n8n_url" {
  value = module.n8n.n8n_url
}

output "ssm_instance_id" {
  value = module.n8n.ssm_instance_id
}

output "security_group_id" {
  value = module.n8n.security_group_id
}

output "secret_name" {
  value = aws_secretsmanager_secret.n8n.name
}

output "secret_arn" {
  value = aws_secretsmanager_secret.n8n.arn
}

output "bedrock_model_arns" {
  description = "Bedrock foundation model ARNs this instance's role can invoke, when enable_bedrock is true."
  value       = var.enable_bedrock ? module.bedrock[0].model_arns : []
}

output "bootstrap_document_name" {
  value = module.n8n.bootstrap_document_name
}
