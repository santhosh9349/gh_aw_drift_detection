# Telegram Bot Setup Guide for Drift Detection

This guide walks you through setting up Telegram notifications for infrastructure drift detection alerts.

## Prerequisites

- Telegram account
- Access to GitHub repository secrets
- Admin access to create a Telegram channel (optional, can use existing)

## Step 1: Create a Telegram Bot

1. **Open Telegram** and search for [@BotFather](https://t.me/botfather)

2. **Start a conversation** and send the `/newbot` command

3. **Follow the prompts**:
   - Choose a **display name** for your bot (e.g., "AWS Infra Drift Bot")
   - Choose a **username** ending in `bot` (e.g., `aws_infra_drift_bot`)

4. **Save the bot token** - BotFather will provide a token like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   
   ⚠️ **Keep this token secret!** Anyone with this token can control your bot.

## Step 2: Create or Configure a Telegram Channel

### Option A: Create a New Channel

1. In Telegram, tap the **menu** icon and select **New Channel**
2. Enter a **channel name** (e.g., "DevOps Drift Alerts")
3. Choose **Public** or **Private**:
   - **Public**: Use the channel username (e.g., `@devops_drift_alerts`)
   - **Private**: You'll need to get the numeric channel ID

### Option B: Use an Existing Channel/Group

If using an existing channel or group, you can use:
- Public channel username: `@channel_name`
- Private channel/group: Numeric ID (e.g., `-1001234567890`)

### Get Channel ID for Private Channels

For private channels, you need the numeric ID:

1. Add your bot to the channel as an **administrator**
2. Send a message to the channel
3. Run this command to get the channel ID:

```bash
# Replace YOUR_BOT_TOKEN with your actual token
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates" | python3 -m json.tool
```

Look for the `chat.id` field in the response.

## Step 3: Add Bot to Channel

1. Open your Telegram channel settings
2. Go to **Administrators** → **Add Administrator**
3. Search for your bot username
4. Grant **"Post Messages"** permission
5. Save changes

## Step 4: Configure GitHub Secrets

Add these secrets to your GitHub repository:

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

### Required Secrets

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather | `1234567890:ABCdefGHI...` |
| `TELEGRAM_CHANNEL_ID` | Channel ID or username | `@devops_alerts` or `-1001234567890` |

## Step 5: Test the Configuration

### Manual Test via Workflow

1. Go to **Actions** tab in your repository
2. Select **Infrastructure Drift Detection** workflow
3. Click **Run workflow**
4. Choose the environment (dev/prod)
5. Optionally enable "Send notification even if no drift detected"
6. Click **Run workflow**

### Verify Notification

If configured correctly, you should receive a message in your Telegram channel:

```
🚨 Infrastructure Drift Detected

Environment: dev
Branch: main
Time: 2026-01-29 14:30:00 UTC
Resources Affected: 2

━━━━━━━━━━━━━━━━

📝 aws_instance.web_server
  • instance_type: t2.micro → t2.small

View Full Report
```

## Troubleshooting

### Common Issues

#### "Chat not found" Error

- Verify the channel ID is correct
- Ensure the bot is added to the channel as administrator
- For private channels, use the numeric ID (starts with `-100`)

#### "Invalid token" Error

- Double-check the bot token from BotFather
- Ensure no extra spaces or characters in the token
- Regenerate the token if compromised

#### "Bot not in channel" Error

- Add the bot to your channel/group
- Give the bot "Post Messages" permission
- For groups, the bot needs to be a member (not just admin invite)

#### Rate Limit Errors

Telegram limits bots to ~30 messages per second. The notification system:
- Uses exponential backoff (2s, 4s, 8s delays)
- Handles `RetryAfter` exceptions automatically
- Logs retry attempts for debugging

#### Message Formatting Issues

If messages appear broken:
- Check for unescaped special characters in resource names
- The system escapes MarkdownV2 characters automatically
- Review logs for formatting errors

### Viewing Logs

GitHub Actions logs show detailed information:

1. Go to **Actions** → Select workflow run
2. Click on **Send Telegram Notification** job
3. Expand the **Send Telegram Notification** step
4. Look for log entries with `drift_run_id` for tracing

### Testing Locally

For local development testing:

```bash
# Navigate to repository root
cd aws_infra

# Create a test environment file
cat > scripts/drift-detection/.env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=@your_channel_or_-1001234567890
EOF

# Create a test drift report
cat > test_report.json << EOF
{
  "timestamp": "2026-01-29T14:30:00Z",
  "environment": "dev",
  "branch": "main",
  "workflow_run_id": "12345",
  "workflow_run_url": "https://github.com/org/aws_infra/actions/runs/12345",
  "drift_detected": true,
  "resource_changes": [
    {
      "resource_type": "aws_instance",
      "resource_name": "web_server",
      "action": "update",
      "before": {"instance_type": "t2.micro"},
      "after": {"instance_type": "t2.small"}
    }
  ]
}
EOF

# Install dependencies
pip install -r scripts/drift-detection/requirements.txt

# Run the notification script
python -m scripts.drift-detection.notify_telegram --report test_report.json --environment dev

# Clean up
rm test_report.json scripts/drift-detection/.env
```

## Security Best Practices

1. **Never commit tokens** - Use GitHub secrets or environment variables
2. **Rotate tokens periodically** - Regenerate via BotFather if compromised
3. **Use private channels** - For sensitive drift information
4. **Limit channel access** - Only add necessary team members
5. **Review logs** - Tokens are automatically sanitized in logs