# Terraform Drift Detection Demo Repository

This repository deploys a single demo EC2 instance with Terraform (state in Terraform Cloud) and uses GitHub Agentic Workflows to detect, attribute and report infrastructure drift.

## Tech Stack

### Infrastructure
- **Terraform** with the **AWS Provider 5.x**
- **State Management**: Terraform Cloud (remote state, no local state management)
- **Resources**: one EC2 instance in the account's default VPC (`terraform/dev/ec2.tf`); no custom VPCs, subnets or modules

### Development Tools
- Scripts for common tasks located in `scripts/` directory
- GitHub Actions for CI/CD workflows
- MCP servers for enhanced workflow automation
- SpecKit for feature specification and planning (`.specify/`, `.github/agents/`)

## Project Structure

```
├── terraform/
│   └── dev/                      # Demo environment
│       ├── terraform.tf          # Terraform Cloud backend and provider configuration
│       ├── variables.tf          # Region, environment, instance type
│       ├── ec2.tf                # EC2 instance
│       └── outputs.tf            # Instance ID and private IP
├── scripts/drift-detection/      # Drift detection scripts and Python modules
├── .github/workflows/            # drift-detection.yml and the ai-analysis-notification agentic workflow
├── docs/drift-detection/         # Drift detection setup guides
└── README.md
```

## Coding Guidelines

### Infrastructure as Code (Terraform) Guidelines
- **Keep it minimal**: this repo exists to demo drift detection; do not add networking, modules or extra resources unless asked
- **Variable naming**: Use snake_case for all Terraform variables and resources
- **State management**: Never manage state locally - all state in Terraform Cloud
- **Documentation**: Include description for every variable and output
- **Version pinning**: Pin provider versions in `terraform.tf` (AWS Provider 5.x)
- **Tagging**: Tag resources with at least `Name`, `Environment` and `ManagedBy`

### General Best Practices
- **Security first**: Never commit secrets, API keys, or sensitive data
- **Linting**: Code must pass all linters before commit
- **Documentation**: Update README.md when adding new features or infrastructure
- **Git commits**: Use conventional commit messages (feat:, fix:, docs:, refactor:, etc.)
- **PR requirements**: All changes require pull request with description and testing notes
- **SpecKit workflow**: Use SpecKit agents for feature specification, clarification, and planning before implementation

## MCP Server Integration

### GitHub MCP Server
- Use GitHub MCP server for all GitHub-related operations
- Always provide GitHub web links after operations for visibility
- When searching: use single words or minimal phrases for better results

### Terraform MCP Server
- Use Terraform MCP server for Terraform Cloud operations
- Provide Terraform Cloud links after operations
- Focus on configuration and modules - ignore state management

## SpecKit Integration

### Feature Development Workflow
1. **Specify**: Use `/speckit.specify` to create feature specifications in `.specify/memory/`
2. **Clarify**: Use `/speckit.clarify` to resolve ambiguities and add clarifications
3. **Plan**: Use `/speckit.plan` to create technical implementation plans
4. **Implement**: Use `/speckit.implement` to execute the plan with validation

### Agent Files
- Agents located in [.github/agents/](.github/agents/) define specialized workflows
- [`speckit.clarify.agent.md`](.github/agents/speckit.clarify.agent.md): Identifies and resolves specification ambiguities
- Additional agents available for specification, planning, and implementation phases

### Prerequisites Script
- Run `.specify/scripts/powershell/check-prerequisites.ps1` to validate feature branch environment
- Use `-Json -PathsOnly` flags for structured output during automated workflows

## Resources & Scripts

### Common Tasks
- **Deploy infrastructure**: Navigate to `terraform/dev/` and use Terraform commands (`terraform plan`, `terraform apply`)
- Scripts should be executable and include usage documentation in comments
- Create new scripts for repetitive tasks

## Security

- Never hardcode credentials or secrets; AWS access uses OIDC
- Run `terraform fmt` and `terraform validate` before committing

## Notes for Copilot

- Keep Terraform changes confined to `terraform/dev/`
- Validate Terraform with `terraform plan` before applying
- Update README.md when infrastructure changes

### SpecKit Workflow
- Use SpecKit agents for structured feature development
- Run clarification phase before creating implementation plans
- Validate prerequisites before starting implementation
- Follow the specify → clarify → plan → implement workflow for complex features

