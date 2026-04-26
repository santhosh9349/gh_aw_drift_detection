# AWS Infrastructure Drift Detection with GitHub Agentic Workflows

[![Terraform Drift Detection](https://github.com/santhosh9349/gh_aw_drift_detection/actions/workflows/drift-detection.yml/badge.svg)](https://github.com/santhosh9349/gh_aw_drift_detection/actions/workflows/drift-detection.yml)
[![Drift Analysis & Notification Agent](https://github.com/santhosh9349/gh_aw_drift_detection/actions/workflows/ai-analysis-notification.lock.yml/badge.svg)](https://github.com/santhosh9349/gh_aw_drift_detection/actions/workflows/ai-analysis-notification.lock.yml)
[![Terraform](https://img.shields.io/badge/Terraform-1.5.x-7B42BC?logo=terraform)](https://www.terraform.io/)
[![AWS Provider](https://img.shields.io/badge/AWS_Provider-5.x-FF9900?logo=amazon-aws)](https://registry.terraform.io/providers/hashicorp/aws/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Detect, attribute, and report AWS infrastructure drift automatically — powered by GitHub Agentic Workflows and AI analysis.**

This repository manages multi-VPC AWS infrastructure with Terraform and runs a daily agentic workflow that detects when AWS resources have been changed outside of Terraform, queries CloudTrail to find who made the change, and uses an AI agent to classify risk, create a GitHub issue, and send a Telegram notification.

---

## Table of Contents

1. [About GitHub Agentic Workflows](#about-github-agentic-workflows)
2. [Why Agentic Drift Detection](#why-agentic-drift-detection)
3. [How It Works](#how-it-works)
4. [Prerequisites](#prerequisites)
5. [Setup & Configuration](#setup--configuration)
6. [Infrastructure Architecture](#infrastructure-architecture)
7. [Project Structure](#project-structure)
8. [Contributing](#contributing)
9. [Costs](#costs)
10. [Getting Help](#getting-help)
11. [License](#license)

---

## About GitHub Agentic Workflows

[GitHub Agentic Workflows](https://github.github.com/gh-aw/) (`gh-aw`) extend standard GitHub Actions by embedding an AI agent directly inside a workflow step. Instead of scripting every decision, the agent receives context (artifacts, repository data, tool access) and autonomously decides what to do — such as creating a GitHub issue with a risk-classified analysis or triggering a Telegram notification.

> For a full overview of the platform, see the [GitHub Agentic Workflows documentation](https://github.github.com/gh-aw/).

This project uses the `gh-aw` CLI to compile a human-readable Markdown workflow definition ([`ai-analysis-notification.md`](.github/workflows/ai-analysis-notification.md)) into a locked, reproducible workflow file ([`ai-analysis-notification.lock.yml`](.github/workflows/ai-analysis-notification.lock.yml)).

**Key properties of Agentic Workflows used here:**
- `safe-outputs` — constrains what the agent can do (create one issue, send one notification)
- `tools` — grants GitHub toolsets (`actions`, `default`) so the agent can read artifacts
- `network: defaults` — restricts outbound traffic to a known-safe domain allowlist

---

## Why Agentic Drift Detection

Infrastructure drift — when live AWS resources diverge from their Terraform state — is hard to triage with static scripts alone because:

| Challenge | Classic Workflow Limitation | Agentic Solution |
|---|---|---|
| Severity varies by resource type | Script treats all drift identically | AI classifies risk (critical/high/medium/low) |
| Root cause requires context | Script reports _what_ changed | Agent correlates CloudTrail _who/when_ with plan diff |
| Issue quality degrades over time | Template issues go stale | Agent writes a fresh, context-aware issue each run |
| Multi-signal reasoning | Script can't join plan + audit data | Agent reads both artifacts together |

The agentic layer sits _after_ the deterministic data-collection jobs, so the structured pipeline remains reliable while the AI handles the judgment call on impact and remediation guidance.

---

## How It Works

The end-to-end pipeline is orchestrated by two workflows:

1. **`drift-detection.yml`** — deterministic data collection (Terraform plan → CloudTrail lookup → artifact upload → trigger agent)
2. **`ai-analysis-notification.lock.yml`** — agentic analysis (download artifacts → AI risk analysis → create GitHub issue → send Telegram notification)

```mermaid
flowchart TD
    A([Schedule: Daily 6 AM UTC\nor workflow_dispatch]) --> B

    subgraph JOB1["Job 1 · Terraform Drift Scan"]
        B[Configure AWS via OIDC] --> C[terraform init]
        C --> D["terraform plan -detailed-exitcode\n+ retry on state lock"]
        D --> E{Exit Code}
        E -- "0 · No drift" --> F[✅ Write job summary]
        E -- "2 · Drift found" --> G[Parse plan JSON stream\nExtract resource IDs & ARNs]
        G --> H[Upload Artifacts\nplan_output.txt · plan_stream.jsonl\ndrift_resources.txt]
    end

    H --> JOB2

    subgraph JOB2["Job 2 · CloudTrail Lookup"]
        I[Download drift scan artifacts] --> J[query-cloudtrail.sh\nper drifted resource]
        J --> KA{"Strategy A:\nidentifier is an ARN?"}
        KA -- "Yes → ARN lookup" --> L[CloudTrail: AttributeKey=ResourceName\nusing ARN]
        KA -- "No + action = create\n(resource manually deleted)" --> KB{"Strategy B1:\nold resource ID known?"}
        KB -- "Yes → resource ID lookup" --> M[CloudTrail: AttributeKey=ResourceName\nusing old resource ID]
        KB -- "No result" --> MC[Strategy B2 fallback\nCloudTrail: AttributeKey=EventName\ne.g. DeleteVpc · TerminateInstances]
        L & M & MC --> N[Build attribution table\nactor · ARN · timestamp]
        N --> O[Upload Artifacts\ndrift_resources_attributed.txt\nattribution_table.md]
    end

    O --> JOB3

    subgraph JOB3["Job 3 · Trigger AI Agent"]
        P["gh workflow run\nai-analysis-notification.lock.yml"]
    end

    P --> JOB4

    subgraph JOB4["Agentic Workflow · AI Analysis & Notification"]
        Q[Download all artifacts\nfrom latest drift-detection run] --> R[AI: Severity classification\nRoot-cause attribution\nRemediation guidance]
        R --> S[create_issue tool\n🔴 Drift · infrastructure · ai-analysis]
        R --> T[send_telegram_notification tool\nDrift summary + run link]
    end

    style JOB4 fill:#1a1a2e,color:#e0e0ff,stroke:#6c63ff
```

### Artifact Chain

```
terraform plan (text + JSON stream)
        │
        ▼
plan_stream.jsonl            raw JSON stream from terraform plan -json
        │
        ▼
drift_resources.txt          address | action | resource_type | identifier
        │
        ▼
drift_resources_attributed.txt   + actor_name | actor_arn | event_time
        │
        ├─────────────────────────────────────┐
        ▼                                     ▼
attribution_table.md                   drift_report.json
Markdown table for GitHub issue        Structured report for Telegram
        │                                     │
        └──────────────┬──────────────────────┘
                       ▼
          Telegram message + GitHub Issue (AI-written)
```

---

## Prerequisites

### 1. Terraform Cloud

State is managed exclusively in [Terraform Cloud](https://app.terraform.io). Local state is prohibited.

- Create a Terraform Cloud organization and workspace linked to this repository
- Generate an API token: **User Settings → Tokens → Create an API token**
- Store it as the repository secret `TF_API_TOKEN`

### 2. AWS — Read-Only OIDC Role

The workflow authenticates to AWS using OpenID Connect (OIDC), read-only is enough for testing, more restrictive role for Organizational use.

Store the role ARN as the repository variable `AWS_OIDC_ROLE_ARN`.

### 3. GitHub Agentic Workflows — Copilot Token

The AI analysis step requires a GitHub Copilot-enabled token:

- Generate a **fine-grained personal access token** with `co-pilot requests: read` scope or use a GitHub App token
- Store it as the repository secret `COPILOT_GITHUB_TOKEN`

### 4. Telegram Bot

Follow [docs/drift-detection/telegram-setup.md](docs/drift-detection/telegram-setup.md) to create a bot via [@BotFather](https://t.me/botfather) and obtain the channel ID.

| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from BotFather (e.g., `1234567890:ABCdef...`) |
| `TELEGRAM_CHANNEL_ID` | Channel username (`@channel`) or numeric ID (`-100...`) |

### 5. Repository Variables

| Variable | Description | Example |
|---|---|---|
| `AWS_REGION` | AWS region for all operations | `us-east-1` |
| `AWS_OIDC_ROLE_ARN` | ARN of the read-only OIDC role | `arn:aws:iam::123:role/drift-readonly` |
| `TF_VERSION` | Terraform version to pin | `1.5.7` |

---

## Setup & Configuration

### 1. Clone & Install the gh-aw CLI

```bash
git clone https://github.com/santhosh9349/gh_aw_drift_detection.git
cd gh_aw_drift_detection

# Install the gh-aw GitHub CLI extension
gh extension install github/gh-aw
```
> For detailed guidance on configuring a repository for Agentic Workflows, refer to the [Agentic Authoring Guide](https://github.github.com/gh-aw/guides/agentic-authoring/).

### 2. Configure GitHub Secrets and Variables

Navigate to **Settings → Secrets and variables → Actions** in your repository and add all secrets and variables listed in [Prerequisites](#prerequisites).

### 3. Deploy the Terraform Infrastructure (optional)

The `terraform/dev/` directory contains a working multi-VPC environment used to demonstrate and test drift detection.

```bash
cd terraform/dev
terraform init          # connects to Terraform Cloud remote backend
terraform plan          # preview infrastructure changes
terraform apply         # provision resources
```

> State is managed remotely in Terraform Cloud. Never run `terraform apply` without first reviewing the plan output.

### 4. Trigger a Drift Check

```bash
# Manual trigger via GitHub CLI
gh workflow run drift-detection.yml --ref main -f environment=dev

# Or via the GitHub UI: Actions → Terraform Drift Detection → Run workflow
```

The workflow also runs automatically every day at **06:00 UTC**.

### 5. Editing the Agentic Workflow

The agent prompt lives in the human-readable source file. After editing(If customization needed), compile it:

```bash
gh aw compile .github/workflows/ai-analysis-notification.md
```

This regenerates `ai-analysis-notification.lock.yml`. Commit both files.

---

## Project Structure

```text
.
├── .github/
│   ├── workflows/
│   │   ├── drift-detection.yml              # Main drift detection pipeline
│   │   ├── ai-analysis-notification.md      # Agentic workflow source (editable)
│   │   ├── ai-analysis-notification.lock.yml # Compiled agentic workflow (auto-generated)
│   │   ├── issue-cleanup.md                 # Issue cleanup agentic workflow source
│   │   ├── issue-cleanup.lock.yml           # Compiled issue cleanup workflow (auto-generated)
│   │   ├── agentics-maintenance.yml         # Maintenance workflow for agentic workflows
│   │   └── copilot-setup-steps.yml          # Copilot environment setup
│   ├── agents/                              # SpecKit agent definitions
│   ├── instructions/                        # Copilot instruction files
│   ├── prompts/                             # Prompt templates
│   ├── aw/                                  # gh-aw configuration and reference files
│   ├── ISSUE_TEMPLATE/                      # GitHub issue templates
│   ├── pull_request_template.md             # PR template
│   └── copilot-instructions.md             # Repository-wide Copilot instructions
├── terraform/
│   ├── dev/                                # Dev environment — VPCs, subnets, EC2
│   │   ├── terraform.tf                    # Terraform Cloud backend + provider config
│   │   ├── variables.tf                    # Add new VPCs/subnets here to scale
│   │   ├── vpc.tf                          # Dynamic VPC creation
│   │   ├── subnets.tf                      # Dynamic subnet creation
│   │   ├── ec2.tf                          # EC2 instance configuration
│   │   ├── outputs.tf                      # Environment outputs
│   │   └── user_data/                      # EC2 user data scripts
│   └── modules/                            # Reusable modules: vpc, subnet, ec2
├── scripts/
│   └── drift-detection/
│       ├── query-cloudtrail.sh             # CloudTrail attribution (3-strategy lookup)
│       ├── generate-drift-report.sh        # Converts attributed data to drift_report.json
│       ├── generate-plan-json.sh           # Generates plan JSON stream from terraform plan
│       ├── parse-terraform-plan.sh         # Extracts resource IDs from plan JSON stream
│       ├── notify_telegram.py              # Sends formatted Telegram message (async)
│       ├── message_formatter.py            # MarkdownV2 message formatting + splitting
│       ├── models.py                       # Pydantic models (DriftDetectionEvent, ResourceChange, etc.)
│       ├── config.py                       # Configuration loader (env vars → NotificationConfig)
│       ├── retry_handler.py                # Exponential backoff retry logic (tenacity)
│       ├── env.example                     # Template for local development env vars
│       ├── requirements.txt                # Python deps (python-telegram-bot, pydantic, tenacity)
│       └── REFACTORING_README.md           # Notes on script architecture and refactoring
└── docs/
    └── drift-detection/
        └── telegram-setup.md              # Step-by-step Telegram bot and channel setup
```

---

## Contributing

Enhancement contribution are welcome.

1. Fork the repository and create a branch from `main` or `dev`
2. For infrastructure changes: run `terraform fmt` and `terraform validate` before committing
3. For agentic workflow changes: edit the `.md` source and run `gh aw compile`
4. Open a pull request with a description of what changed and why

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

---

## Costs

GitHub Agentic Workflows use coding agents at runtime, which incur billing costs.

When using Copilot with default settings, **each workflow run typically incurs two [premium requests](https://docs.github.com/en/billing/concepts/product-billing/github-copilot-premium-requests)**:

| Request | Purpose |
|---|---|
| 1st premium request | Agentic work (reasoning, tool calls, analysis) |
| 2nd premium request | Guardrail check through safe outputs (threat detection) |

**Key points:**

- Automated uses of Copilot are associated with the **user account** whose `COPILOT_GITHUB_TOKEN` is used — premium requests are drawn from that account's monthly quota
- The model used by the agent can be configured to help manage costs (e.g. switching to a lighter model for simpler workflows)
- This project runs agentic workflows `ai-analysis-notification`, which consumes approximately **2 premium requests** in total
- For other coding agent engines (Claude Code, OpenAI Codex, etc.), refer to the [gh-aw engine documentation](https://github.github.com/gh-aw/reference/engines/) for billing details

> Source: [Automate repository tasks with GitHub Agentic Workflows](https://github.blog/ai-and-ml/automate-repository-tasks-with-github-agentic-workflows/) — GitHub Blog, February 2026

---

## Getting Help

- **Workflow logs**: Navigate to **Actions → Terraform Drift Detection** in the GitHub UI
- **Telegram setup**: [docs/drift-detection/telegram-setup.md](docs/drift-detection/telegram-setup.md)
- **Bug reports / feature requests**: Open a [GitHub Issue](https://github.com/santhosh9349/gh_aw_drift_detection/issues)

---

## License

This project is licensed under the [MIT License](LICENSE).
