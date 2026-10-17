# Single EC2 instance used to demo drift detection.
# Change it out-of-band (e.g. edit a tag or the instance type in the AWS console),
# then run the Terraform Drift Detection workflow to see the drift reported.

# Uses the account's default VPC so no networking resources need to be managed
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "demo" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = var.instance_type
  subnet_id     = data.aws_subnets.default.ids[0]

  tags = {
    Name        = "drift-demo-instance"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }

  lifecycle {
    # Newer AMI releases must not show up as drift
    ignore_changes = [ami]
  }
}
