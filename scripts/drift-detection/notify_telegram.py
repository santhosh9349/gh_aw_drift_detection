"""
Telegram Notifier for Infrastructure Drift Detection

This module provides the main notification functionality for sending
drift detection alerts to Telegram channels.

Usage:
    python notify_telegram.py --report drift_report.json
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from uuid import uuid4

# Configure logging before other imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Import telegram library
try:
    from telegram import Bot
    from telegram.error import TelegramError, InvalidToken, BadRequest
    from telegram.constants import ParseMode
except ImportError:
    logger.error("python-telegram-bot is not installed. Run: pip install python-telegram-bot==20.7")
    sys.exit(1)

from models import (
    DriftDetectionEvent,
    ResourceChange,
    ActionType,
    TelegramNotification,
    NotificationPart,
    DeliveryStatus,
    NotificationConfig,
)
from config import load_config
from message_formatter import format_drift_message, format_no_drift_message, split_message
from retry_handler import RetryHandler


def sanitize_for_logging(text: str, show_chars: int = 4) -> str:
    """
    Sanitize sensitive data for logging, showing only first and last N characters.
    
    Args:
        text: Text to sanitize
        show_chars: Number of characters to show at start and end
        
    Returns:
        Sanitized string with middle portion redacted
    """
    if not text or len(text) <= show_chars * 2 + 3:
        return "[REDACTED]"
    return f"{text[:show_chars]}...{text[-show_chars:]}"


class TelegramNotifier:
    """
    Handles sending drift detection notifications to Telegram.
    """
    
    def __init__(self, config: NotificationConfig):
        """
        Initialize the Telegram notifier.
        
        Args:
            config: NotificationConfig with bot credentials and settings
        """
        self.config = config
        self.bot: Optional[Bot] = None
        self.retry_handler = RetryHandler(
            max_retries=config.max_retries,
            initial_delay=config.initial_retry_delay,
            multiplier=config.retry_multiplier,
        )
        
        # Log sanitized config
        logger.info(
            "Initializing TelegramNotifier",
            extra={"config": config.sanitize_for_logging()}
        )
    
    async def initialize(self) -> bool:
        """
        Initialize the Telegram bot and verify connection.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.bot = Bot(token=self.config.bot_token)
            
            # Verify bot token by getting bot info
            bot_info = await self.bot.get_me()
            logger.info(
                f"Bot initialized successfully: @{bot_info.username}",
                extra={"bot_id": bot_info.id, "bot_username": bot_info.username}
            )
            return True
            
        except InvalidToken as e:
            logger.error(
                f"Invalid bot token: {sanitize_for_logging(self.config.bot_token)}",
                extra={"error_type": "InvalidToken", "error_message": str(e)}
            )
            return False
        except TelegramError as e:
            logger.error(
                f"Failed to initialize bot: {e}",
                extra={"error_type": type(e).__name__, "error_message": str(e)}
            )
            return False
    
    async def send_notification(
        self,
        event: DriftDetectionEvent,
        drift_run_id: Optional[str] = None
    ) -> TelegramNotification:
        """
        Send a drift detection notification to Telegram.
        
        Args:
            event: DriftDetectionEvent to notify about
            drift_run_id: Optional unique ID for this drift run
            
        Returns:
            TelegramNotification with delivery status
        """
        drift_run_id = drift_run_id or str(uuid4())[:8]
        notification_id = f"drift_{drift_run_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Create notification object
        notification = TelegramNotification(
            notification_id=notification_id,
            drift_event=event,
            channel_id=self.config.channel_id,
        )
        
        # Log start of notification
        logger.info(
            "Starting notification send",
            extra={
                "drift_run_id": drift_run_id,
                "notification_id": notification_id,
                "drift_detected": event.drift_detected,
                "total_changes": event.total_changes,
            }
        )
        
        # Skip notification if no drift and config says not to notify
        if not event.drift_detected and not self.config.notify_on_no_drift:
            logger.info(
                "Skipping notification - no drift detected and notify_on_no_drift=False",
                extra={"drift_run_id": drift_run_id}
            )
            notification.status = DeliveryStatus.SENT
            notification.sent_at = datetime.utcnow()
            return notification
        
        # Format message
        if event.drift_detected:
            message = format_drift_message(event)
        else:
            message = format_no_drift_message(event)
        
        # Split message if needed
        message_parts = split_message(message, event, self.config.max_message_length)
        notification.message_parts = message_parts
        
        logger.info(
            f"Message formatted: {len(message)} chars, {len(message_parts)} part(s)",
            extra={
                "drift_run_id": drift_run_id,
                "message_length": len(message),
                "parts_count": len(message_parts),
            }
        )
        
        # Ensure bot is initialized
        if not self.bot:
            if not await self.initialize():
                notification.mark_failed(Exception("Bot initialization failed"))
                return notification
        
        # Send each part
        try:
            for part in message_parts:
                await self._send_message_part(part, drift_run_id)
                
                # Small delay between parts to maintain order
                if part.part_number < part.total_parts:
                    await asyncio.sleep(0.1)
            
            notification.mark_sent()
            logger.info(
                "Notification sent successfully",
                extra={
                    "drift_run_id": drift_run_id,
                    "notification_id": notification_id,
                    "status": notification.status.value,
                    "parts_sent": len(message_parts),
                }
            )
            
        except TelegramError as e:
            notification.mark_failed(e)
            logger.error(
                f"Failed to send notification: {e}",
                extra={
                    "drift_run_id": drift_run_id,
                    "notification_id": notification_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "status": notification.status.value,
                }
            )
        
        return notification
    
    async def _send_message_part(
        self,
        part: NotificationPart,
        drift_run_id: str
    ) -> None:
        """
        Send a single message part with retry logic.
        
        Args:
            part: NotificationPart to send
            drift_run_id: Drift run ID for logging
        """
        async def send():
            result = await self.bot.send_message(
                chat_id=self.config.channel_id,
                text=part.content,
                parse_mode=ParseMode.MARKDOWN_V2 if self.config.enable_markdown else None,
            )
            part.telegram_message_id = result.message_id
            return result
        
        logger.debug(
            f"Sending message part {part.part_number}/{part.total_parts}",
            extra={
                "drift_run_id": drift_run_id,
                "part_number": part.part_number,
                "total_parts": part.total_parts,
                "content_length": len(part.content),
            }
        )
        
        await self.retry_handler.execute_with_retry(send)
        
        logger.debug(
            f"Message part {part.part_number} sent",
            extra={
                "drift_run_id": drift_run_id,
                "part_number": part.part_number,
                "telegram_message_id": part.telegram_message_id,
            }
        )
    
    async def close(self) -> None:
        """Close the bot connection."""
        if self.bot:
            await self.bot.shutdown()
            self.bot = None


def parse_drift_report(report_path: str) -> DriftDetectionEvent:
    """
    Parse a drift report JSON file into a DriftDetectionEvent.
    
    Args:
        report_path: Path to the drift report JSON file
        
    Returns:
        DriftDetectionEvent parsed from the report
        
    Raises:
        FileNotFoundError: If report file doesn't exist
        ValueError: If report format is invalid
    """
    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"Drift report not found: {report_path}")
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    # Parse resource changes
    resource_changes = []
    for change_data in data.get("resource_changes", []):
        resource_changes.append(
            ResourceChange(
                resource_type=change_data.get("resource_type", "unknown"),
                resource_name=change_data.get("resource_name", "unknown"),
                action=ActionType(change_data.get("action", "update")),
                before=change_data.get("before"),
                after=change_data.get("after"),
                actor_name=change_data.get("actor_name"),
                actor_arn=change_data.get("actor_arn"),
                event_time=change_data.get("event_time"),
            )
        )
    
    return DriftDetectionEvent(
        timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
        branch=data.get("branch", "unknown"),
        workflow_run_id=data.get("workflow_run_id", "unknown"),
        workflow_run_url=data.get("workflow_run_url", ""),
        drift_detected=data.get("drift_detected", len(resource_changes) > 0),
        resource_changes=resource_changes,
    )


async def main(args: argparse.Namespace) -> int:
    """
    Main entry point for the notification script.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Load configuration
        config = load_config()
        logger.info(
            "Configuration loaded",
            extra={"config": config.sanitize_for_logging()}
        )
        
        # Parse drift report
        event = parse_drift_report(args.report)
        
        logger.info(
            f"Drift report parsed: {event.total_changes} changes detected",
            extra={
                "drift_detected": event.drift_detected,
                "total_changes": event.total_changes,
            }
        )
        
        # Send notification
        notifier = TelegramNotifier(config)
        notification = await notifier.send_notification(
            event,
            drift_run_id=args.run_id
        )
        await notifier.close()
        
        # Return based on notification status
        if notification.status == DeliveryStatus.SENT:
            return 0
        else:
            logger.error(
                f"Notification failed: {notification.error_message}",
                extra={
                    "error_type": notification.error_type,
                    "retry_count": notification.retry_count,
                }
            )
            return 1
            
    except FileNotFoundError as e:
        logger.error(f"Report file not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


def cli():
    """Command line interface entry point."""
    parser = argparse.ArgumentParser(
        description="Send drift detection notifications to Telegram"
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to drift report JSON file"
    )
    parser.add_argument(
        "--run-id",
        help="Unique identifier for this drift run"
    )
    
    args = parser.parse_args()
    
    # Run async main
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
