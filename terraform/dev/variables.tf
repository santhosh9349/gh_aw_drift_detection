variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-west-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "vpcs" {
  description = "Map of VPC names to their CIDR blocks"
  type        = map(string)
  default = {
    "prod"       = "10.0.0.0/16"
    "dev"        = "172.0.0.0/16"
    "inspection" = "192.0.0.0/16"
  }
}

variable "subnets" {
  description = "Map of VPC names to their public subnet CIDRs"
  type        = map(map(string))
  default = {
    prod = {
      pub_sub1  = "10.0.100.0/24"
      pub_sub2  = "10.0.200.0/24"
      priv_sub1 = "10.0.1.0/24"
      priv_sub2 = "10.0.2.0/24"
    }
    dev = {
      pub_sub1  = "172.0.100.0/24"
      pub_sub2  = "172.0.200.0/24"
      priv_sub1 = "172.0.1.0/24"
      priv_sub2 = "172.0.2.0/24"
    }
    inspection = {
      pub_sub1  = "192.0.100.0/24"
      pub_sub2  = "192.0.200.0/24"
      priv_sub1 = "192.0.1.0/24"
      priv_sub2 = "192.0.2.0/24"
    }
  }
}
