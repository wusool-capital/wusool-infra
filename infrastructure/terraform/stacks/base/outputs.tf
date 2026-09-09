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

output "us_east_1_alarm_topic_arn" {
  description = "us-east-1 twin of alarm_topic_arn, for alarms that must live in that region (e.g. Route 53 health check alarms). Empty when slack_team_id/slack_channel_id aren't set — try(..., \"\") not try(..., null), see the header comment on stacks/toolkit/outputs.tf for why."
  value       = try(aws_sns_topic.alerts_us_east_1[0].arn, "")
}
