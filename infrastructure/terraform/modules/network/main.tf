data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project}-${var.environment}-vpc"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.project}-${var.environment}-igw"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[var.public_subnet_az_index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project}-${var.environment}-public"
    Tier = "public"
  }
}

resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[var.private_subnet_az_index]

  tags = {
    Name = "${var.project}-${var.environment}-private"
    Tier = "private"
  }
}

resource "aws_subnet" "database_private" {
  count = var.database_private_subnet_cidr != null ? 1 : 0

  vpc_id            = aws_vpc.this.id
  cidr_block        = var.database_private_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[var.database_private_subnet_az_index]

  tags = {
    Name = "${var.project}-${var.environment}-database-private"
    Tier = "private"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  # No inline `route` block, deliberately (2026-08-17): an inline block makes
  # this resource authoritative over EVERY route on the table, including ones
  # created elsewhere (e.g. stacks/peering's aws_route.dev_to_prod) — the next
  # apply of this stack would silently delete them. The default route below
  # is managed as a standalone aws_route instead, same pattern already used
  # for aws_route_table.private.
  #
  # MIGRATION NOTE for whoever applies this: the previous inline route already
  # exists in AWS. `tofu apply` on aws_route.internet below will fail with
  # "RouteAlreadyExists" unless it's imported into state first:
  #   tofu import 'aws_route.internet' <route-table-id>_0.0.0.0/0
  # (per stack/environment — do this for both dev and prod).

  tags = {
    Name = "${var.project}-${var.environment}-public-rt"
  }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.project}-${var.environment}-private-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "database_private" {
  count = length(aws_subnet.database_private)

  subnet_id      = aws_subnet.database_private[0].id
  route_table_id = aws_route_table.private.id
}
