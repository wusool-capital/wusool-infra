# VPC peering between dev (scribe's instance) and prod (wusool-prod-postgres).
# Both route tables in stacks/base's modules/network are Terraform-managed
# with authoritative route declarations of their own (dev's inline default
# route, prod's authoritatively-empty table) — a route added anywhere else
# would be deleted on the next stacks/base apply. These are standalone
# aws_route resources instead, so this stack owns them without touching
# modules/network or colliding with normal stacks/base applies.
#
# auto_accept = true is safe here: same account, same region, no
# cross-account handshake needed. Reachability past the route is still
# gated by security groups on the receiving side (stacks/postgres's
# extra_allowed_security_group_ids) — this stack only opens the network path.

resource "aws_vpc_peering_connection" "dev_to_prod" {
  vpc_id      = data.terraform_remote_state.base_dev.outputs.vpc_id
  peer_vpc_id = data.terraform_remote_state.base_prod.outputs.vpc_id
  auto_accept = true

  tags = { Name = "wusool-dev-to-prod" }
}

# dev's public route table (scribe's subnet) -> prod VPC, via the peering
resource "aws_route" "dev_to_prod" {
  route_table_id            = data.terraform_remote_state.base_dev.outputs.public_route_table_id
  destination_cidr_block    = data.terraform_remote_state.base_prod.outputs.vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.dev_to_prod.id
}

# prod's private route table (the RDS's subnets) -> dev VPC, via the peering
resource "aws_route" "prod_to_dev" {
  route_table_id            = data.terraform_remote_state.base_prod.outputs.private_route_table_id
  destination_cidr_block    = data.terraform_remote_state.base_dev.outputs.vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.dev_to_prod.id
}
