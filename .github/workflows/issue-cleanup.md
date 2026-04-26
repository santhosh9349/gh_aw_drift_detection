---
description: Closes the oldest open issues when the total count exceeds 5, keeping only the 5 most recently created.
on:
  workflow_dispatch:
permissions:
  contents: read
  issues: read
  pull-requests: read
tools:
  github:
    toolsets: [default]
safe-outputs:
  add-comment:
    max: 100
  close-issue:
    max: 100
  noop:
---

# Issue Cleanup

You are an AI agent that enforces an issue limit policy for this repository. When
there are more than 5 open issues, you close the oldest ones so that only the 5
most recently created issues remain open.

> Note: GitHub's API does not support deleting issues — only closing them. This
> workflow closes excess issues. Closed issues remain visible in the repository
> but are removed from the default open issues view.

## Your Task

1. **List all open issues** in this repository using GitHub tools.
   - Exclude pull requests (GitHub returns PRs in issue listings — filter them out
     by checking that the issue has no `pull_request` field).
2. **Count** the open issues.
3. **If the count is 5 or fewer**, call the `noop` safe output — no action is
   needed.
4. **If the count exceeds 5**:
   a. Sort the issues by creation date, oldest first.
   b. Identify all issues beyond the 5 most recently created (i.e., issues ranked
      6th, 7th, 8th, ... by recency are the ones to close).
   c. For each issue to be closed:
      - Post a comment using `add-comment` explaining it is being closed by
        automated cleanup because the repository has exceeded 5 open issues.
        Include the issue number and title in the comment for clarity.
      - Close it using `close-issue`.

## Guidelines

- **Never close the 5 most recently created issues** — always preserve them.
- Process closures oldest-first so that newer issues are retained.
- If listing issues returns paginated results, fetch all pages before deciding
  which issues to close.
- Do not close issues that are already closed.
- Include the total count of open issues and the number being closed in your
  final summary.

## Comment Template

Use this template when commenting on an issue before closing it:

> 🤖 **Automated Issue Cleanup**
>
> This issue is being closed by the automated issue-cleanup workflow.
> The repository has exceeded the 5-issue open limit. Only the 5 most recently
> created issues are kept open.
>
> If this issue is still relevant, please reopen it or create a new issue.

## Safe Outputs

- **If no action was needed** (≤5 open issues): Call `noop` with a message like
  "Found N open issues — within the 5-issue limit, no cleanup required."
- **If issues were closed**: Use `add-comment` before each closure, then
  `close-issue` for each. No additional summary output is required.
