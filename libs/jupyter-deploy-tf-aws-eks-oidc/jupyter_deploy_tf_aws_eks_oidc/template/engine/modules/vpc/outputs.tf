output "vpc_id" {
  value = aws_vpc.this.id
}

output "igw_id" {
  value = aws_internet_gateway.this.id
}

# The subnet IDs are the only networking outputs a consumer (EKS cluster, node
# group) references — so by default a consumer depends on the subnets but NOT on
# the route tables, associations, NAT gateways or IGW that make those subnets
# actually route traffic. Those are siblings with no external reference, so on
# destroy Terraform is free to remove them in the first wave — tearing down
# routing out from under still-running nodes, ELBs and pods (e.g. route table
# associations destroyed while the NLB and node groups are still live).
#
# depends_on on the subnet outputs pulls the whole networking set into every
# consumer's dependency closure:
#   - on create: routing exists before nodes/ELBs come up;
#   - on destroy: nodes/cluster/ELBs are torn down before routing is removed.
# (The IGW also has its own NLB-cleanup ordering via the igw_id output; this is
# the complementary guarantee for subnet-consuming resources.)
output "public_subnet_ids" {
  value = aws_subnet.public[*].id
  depends_on = [
    aws_route_table_association.public,
    aws_route_table_association.private,
    aws_route_table.public,
    aws_route_table.private,
    aws_nat_gateway.this,
    aws_internet_gateway.this,
  ]
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
  depends_on = [
    aws_route_table_association.public,
    aws_route_table_association.private,
    aws_route_table.public,
    aws_route_table.private,
    aws_nat_gateway.this,
    aws_internet_gateway.this,
  ]
}
