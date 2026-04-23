# Internal Web Server for Client Dashboard
# User Story 1: Deploy Secure Internal Server in Dev VPC

module "internal_web_server" {
  source = "../modules/ec2"

  name          = "dev-internal-web-server"
  instance_type = "t3.small"
  subnet_id     = module.subnets["dev_priv_sub1"].subnet_id
  vpc_id        = module.vpc["dev"].vpc_id

  # HTTPS ingress from all internal VPC CIDRs
  ingress_cidrs = [
    "192.0.0.0/16", # Inspection VPC
    "172.0.0.0/16", # Dev VPC (intra-VPC)
    "10.0.0.0/16",  # Prod VPC
  ]

  # User data script for nginx setup
  user_data = file("${path.module}/scripts/ec2/user-data.sh")

  # Root volume configuration
  root_volume_size = 30

  # Mandatory tags per Constitution
  tags = {
    Name        = "dev-internal-web-server"
    Environment = var.environment
    Project     = "AWS Infrastructure"
    ManagedBy   = "Terraform"
    Owner       = "DevOps Team"
    CostCenter  = var.environment
    VPC         = "dev"
  }
}
