# Telegram Bot Setup Guide for Drift Detection

Setup guide for Telegram notifications from the infrastructure drift detection system.

## Prerequisites

- Telegram account
- GitHub repository admin access (to add secrets)

---

## Step 1: Create a Telegram Bot

1. Open Telegram and start a chat with [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the prompts:
   - **Display name**: e.g., `AWS Infra Drift Bot`
   - **Username**: must end in `bot`, e.g., `aws_infra_drift_bot`
3. Copy the bot token BotFather returns:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   > ⚠️ Treat this token like a password — anyone with it can control your bot.

---

## Step 2: Create or Identify a Channel

### Public channel
Use the channel username directly as the channel ID: `@your_channel_name`

### Private channel
You need the numeric channel ID. Do this **after** completing Step 3:

1. Add the bot as a channel admin (Step 3 first)
2. Send any message to the channel
3. Fetch recent updates for the bot:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates" | python3 -m json.tool
   ```
4. Find the `channel_post` object in the response and copy `channel_post.chat.id`:
   ```json
   {
     "channel_post": {
       "chat": {
         "id": -1001234567890,
         "type": "channel"
       }
     }
   }
   ```
   Private channel IDs always start with `-100`.

> If `getUpdates` returns an empty array, re-send a message to the channel and try again.

---

## Step 3: Add the Bot to the Channel

1. Open the channel → **Administrators** → **Add Administrator**
2. Search for your bot username and select it
3. Enable the **Post Messages** permission
4. Save

---

## Step 4: Add GitHub Secrets

Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret** and add:

| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |
| `TELEGRAM_CHANNEL_ID` | `@channel_name` or `-1001234567890` |

---

## Step 5: Test

1. Go to **Actions** → **Infrastructure Drift Detection** → **Run workflow**
2. Select an environment (dev/prod) and click **Run workflow**
3. A notification should appear in your Telegram channel within seconds

---

## Testing Locally

```bash
# From repository root
cd scripts/drift-detection

# Configure credentials
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=@your_channel_or_-1001234567890
EOF

# Install dependencies
pip install -r requirements.txt

# Create a minimal test report
cat > /tmp/test_report.json << EOF
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

# Send test notification
python notify_telegram.py --report /tmp/test_report.json --environment dev

# Clean up
rm /tmp/test_report.json .env
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Chat not found` | Wrong channel ID or bot not in channel | Verify channel ID; confirm bot is admin |
| `Invalid token` | Malformed or incorrect token | Copy token again from BotFather; check for spaces |
| `Forbidden` | Bot lacks permission | Ensure bot has "Post Messages" admin permission |
| Rate limit hit | >30 msg/sec to Telegram | System handles this automatically with exponential backoff |

### Viewing GitHub Actions logs

**Actions** → select workflow run → **Send Telegram Notification** job → expand step → filter by `drift_run_id`.

---

## Security

- Never commit tokens — use GitHub secrets or a `.env` file (already in `.gitignore`)
- Regenerate the token via BotFather if it is ever exposed
- Prefer private channels for sensitive drift alerts
- Tokens are automatically redacted in all log output