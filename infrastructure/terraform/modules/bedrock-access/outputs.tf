output "model_arns" {
  description = "Foundation model ARNs granted to the IAM role."
  value       = local.model_arns
}

output "policy_name" {
  description = "Name of the inline IAM role policy granting Bedrock access."
  value       = aws_iam_role_policy.bedrock_invoke.name
}
