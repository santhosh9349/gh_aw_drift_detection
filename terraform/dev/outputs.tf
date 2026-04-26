# VPC Outputs - ACTIVE
output "vpc_ids" {
  description = "IDs of the created VPCs"
  value       = { for k, v in module.vpc : k => v.vpc_id }
}

output "vpc_cidrs" {
  description = "CIDR blocks of the created VPCs"
  value       = { for k, v in module.vpc : k => v.vpc_cidr_block }
}

# Internal Web Server Outputs
output "internal_web_server_instance_id" {
  description = "The ID of the internal web server EC2 instance"
  value       = module.internal_web_server.instance_id
}

output "internal_web_server_private_ip" {
  description = "The private IP address of the internal web server"
  value       = module.internal_web_server.private_ip
}
