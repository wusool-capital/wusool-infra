output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_id" {
  description = "ID of the public subnet."
  value       = aws_subnet.public.id
}

output "private_subnet_id" {
  description = "ID of the private subnet."
  value       = aws_subnet.private.id
}

output "database_private_subnet_id" {
  description = "ID of the second private subnet used by database subnet groups, when enabled."
  value       = try(aws_subnet.database_private[0].id, null)
}

output "database_private_subnet_ids" {
  description = "Private subnet IDs suitable for database subnet groups."
  value       = compact([aws_subnet.private.id, try(aws_subnet.database_private[0].id, null)])
}

output "public_route_table_id" {
  description = "ID of the public route table."
  value       = aws_route_table.public.id
}

output "private_route_table_id" {
  description = "ID of the private route table."
  value       = aws_route_table.private.id
}
