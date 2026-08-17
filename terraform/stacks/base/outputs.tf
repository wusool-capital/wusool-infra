output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_id" {
  value = module.network.public_subnet_id
}

output "private_subnet_id" {
  value = module.network.private_subnet_id
}

output "database_private_subnet_ids" {
  value = module.network.database_private_subnet_ids
}

output "public_route_table_id" {
  value = module.network.public_route_table_id
}

output "private_route_table_id" {
  value = module.network.private_route_table_id
}

output "vpc_cidr" {
  value = module.network.vpc_cidr
}

output "alarm_topic_arn" {
  description = "SNS topic for this environment's CloudWatch alarms."
  value       = aws_sns_topic.alerts.arn
}
