# Terraform Infrastructure as Code Guidelines

This repository contains a minimal Terraform configuration (`terraform/dev/`) that deploys one EC2 instance to demo drift detection.

## General Principles
- **Keep it minimal**: Do not add networking, modules or extra resources unless asked.
- **Naming**: Use snake_case for filenames, resources and variables.
- **Tagging**: Tag resources with at least `Name`, `Environment` and `ManagedBy`.

## State Management
- Local state files are strictly prohibited.
- All state must be managed via **Terraform Cloud**.

## Validation & Deployment
- Always run `terraform fmt` and `terraform validate` before committing.
- A `terraform plan` must be reviewed and approved via Pull Request before application.
