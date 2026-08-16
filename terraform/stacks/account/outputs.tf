output "security_alert_topic_arn" {
  description = "Account-level SNS topic carrying GuardDuty and Security Hub findings."
  value       = aws_sns_topic.security_alerts.arn
}

output "guardduty_detector_id" {
  description = "The account's single GuardDuty detector."
  value       = aws_guardduty_detector.this.id
}
