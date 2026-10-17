"""
Data Models for Drift Detection Telegram Notifications

This module defines Pydantic models for drift detection events,
Telegram notifications, and configuration management.
"""

from typing import List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    """Terraform action types"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"
    NO_OP = "no-op"


class DeliveryStatus(str, Enum):
    """Notification delivery status"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class ResourceChange(BaseModel):
    """Individual resource change detected in drift"""
    resource_type: str = Field(..., description="AWS resource type (e.g., aws_instance)")
    resource_name: str = Field(..., description="Resource name in Terraform")
    action: ActionType = Field(..., description="Type of change detected")
    before: Optional[dict] = Field(None, description="Attribute values before change")
    after: Optional[dict] = Field(None, description="Attribute values after change")
    
    # CloudTrail attribution fields
    actor_name: Optional[str] = Field(None, description="IAM user or role that made the change")
    actor_arn: Optional[str] = Field(None, description="ARN of the actor (IAM user/role/service)")
    event_time: Optional[str] = Field(None, description="Timestamp when the change was made")
    
    @property
    def display_name(self) -> str:
        """Human-readable resource identifier"""
        return f"{self.resource_type}.{self.resource_name}"
    
    @property
    def has_attribution(self) -> bool:
        """Check if CloudTrail attribution is available"""
        return self.actor_name is not None and self.actor_name not in ["*(unavailable)*", "-", ""]
    
    @property
    def change_summary(self) -> List[str]:
        """List of changed attributes with before/after values"""
        if not self.before or not self.after:
            summary = [f"Action: {self.action.value}"]
            if self.has_attribution:
                summary.append(f"Actor: {self.actor_name}")
                if self.event_time and self.event_time != "-":
                    summary.append(f"Time: {self.event_time}")
            return summary
        
        changes = []
        all_keys = set(self.before.keys()) | set(self.after.keys())
        for key in sorted(all_keys):
            before_val = self.before.get(key, "[not set]")
            after_val = self.after.get(key, "[not set]")
            if before_val != after_val:
                changes.append(f"{key}: {before_val} → {after_val}")
        
        if self.has_attribution:
            changes.append(f"Actor: {self.actor_name}")
            if self.event_time and self.event_time != "-":
                changes.append(f"Time: {self.event_time}")
        
        return changes if changes else [f"Action: {self.action.value}"]


class DriftDetectionEvent(BaseModel):
    """Complete drift detection event"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    branch: str = Field(..., description="Git branch where detection ran")
    workflow_run_id: str = Field(..., description="GitHub Actions run ID")
    workflow_run_url: str = Field(..., description="URL to view workflow run")
    
    drift_detected: bool = Field(..., description="Whether any drift was found")
    resource_changes: List[ResourceChange] = Field(default_factory=list)
    
    @property
    def total_changes(self) -> int:
        """Total number of resource changes"""
        return len(self.resource_changes)
    
    @property
    def changes_by_action(self) -> dict:
        """Count changes grouped by action type"""
        from collections import Counter
        return dict(Counter(change.action.value for change in self.resource_changes))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return self.model_dump(mode='json')


class NotificationPart(BaseModel):
    """Individual message part for split messages"""
    part_number: int = Field(..., ge=1)
    total_parts: int = Field(..., ge=1)
    content: str = Field(..., max_length=4096)
    telegram_message_id: Optional[int] = Field(
        None, description="Telegram message ID after sending"
    )


class TelegramNotification(BaseModel):
    """Telegram notification attempt with delivery tracking"""
    notification_id: str = Field(..., description="Unique notification identifier")
    drift_event: DriftDetectionEvent = Field(..., description="Associated drift event")
    
    channel_id: str = Field(..., description="Telegram channel/chat ID")
    message_parts: List[NotificationPart] = Field(default_factory=list)
    
    status: DeliveryStatus = Field(default=DeliveryStatus.PENDING)
    retry_count: int = Field(default=0, ge=0, le=3)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    
    def mark_sent(self, sent_at: datetime = None):
        """Mark notification as successfully sent"""
        self.status = DeliveryStatus.SENT
        self.sent_at = sent_at or datetime.utcnow()
    
    def mark_failed(self, error: Exception):
        """Mark notification as failed"""
        self.status = DeliveryStatus.FAILED
        self.error_message = str(error)
        self.error_type = type(error).__name__
    
    def mark_retrying(self):
        """Mark notification as retrying"""
        self.status = DeliveryStatus.RETRYING
        self.retry_count += 1
    
    def should_retry(self) -> bool:
        """Check if notification should be retried"""
        return (
            self.status in (DeliveryStatus.FAILED, DeliveryStatus.RETRYING) and
            self.retry_count < 3 and
            self.is_retryable_error()
        )
    
    def is_retryable_error(self) -> bool:
        """Check if error is retryable (network/timeout)"""
        retryable_types = ["NetworkError", "TimedOut", "RetryAfter"]
        return self.error_type in retryable_types
    
    @property
    def total_message_length(self) -> int:
        """Total character count across all parts"""
        return sum(len(part.content) for part in self.message_parts)


class NotificationConfig(BaseModel):
    """Configuration for Telegram notification system"""
    
    # Telegram credentials
    bot_token: str = Field(..., description="Telegram bot token from BotFather")
    channel_id: str = Field(..., description="Target Telegram channel/chat ID")
    
    # Retry configuration
    max_retries: int = Field(default=3, ge=1, le=5)
    initial_retry_delay: int = Field(default=2, ge=1, description="Initial delay in seconds")
    retry_multiplier: int = Field(default=2, ge=1, description="Exponential backoff multiplier")
    
    # Message formatting
    enable_markdown: bool = Field(default=True)
    max_message_length: int = Field(default=4096, ge=1, le=4096)
    split_on_resource_boundary: bool = Field(default=True)
    
    # Notification behavior
    notify_on_no_drift: bool = Field(default=False)
    include_workflow_link: bool = Field(default=True)
    
    @field_validator('bot_token')
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate bot token format"""
        if not v or len(v) < 20:
            raise ValueError("Invalid bot token format")
        if ':' not in v:
            raise ValueError("Bot token must contain ':' separator")
        return v
    
    @field_validator('channel_id')
    @classmethod
    def validate_channel_id(cls, v: str) -> str:
        """Validate channel ID format"""
        if not v:
            raise ValueError("Channel ID cannot be empty")
        # Channel IDs start with @ for public channels or - for groups/numeric
        if not (v.startswith('@') or v.startswith('-') or v.lstrip('-').isdigit()):
            raise ValueError("Invalid channel ID format")
        return v
    
    def sanitize_for_logging(self) -> dict:
        """Return config with sensitive data masked (first/last 4 chars only)"""
        if len(self.bot_token) > 8:
            masked_token = f"{self.bot_token[:4]}...{self.bot_token[-4:]}"
        else:
            masked_token = "[REDACTED]"
        
        return {
            "bot_token": masked_token,
            "channel_id": self.channel_id,
            "max_retries": self.max_retries,
            "initial_retry_delay": self.initial_retry_delay,
            "retry_multiplier": self.retry_multiplier,
            "enable_markdown": self.enable_markdown,
            "notify_on_no_drift": self.notify_on_no_drift,
        }
