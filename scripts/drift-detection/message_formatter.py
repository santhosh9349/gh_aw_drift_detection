"""
Message Formatter for Telegram Drift Notifications

This module formats drift detection events into Telegram-compatible
MarkdownV2 messages with support for message splitting.
"""

import re
from typing import List, Tuple
from datetime import datetime

from models import DriftDetectionEvent, ResourceChange, NotificationPart


# Maximum message length for Telegram
MAX_MESSAGE_LENGTH = 4096
# Buffer for part headers
MESSAGE_BUFFER = 100


def escape_markdown(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2 format.
    
    Characters that need escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
    
    Args:
        text: Raw text to escape
        
    Returns:
        Text with special characters escaped
    """
    # Characters that need escaping in MarkdownV2
    special_chars = r'_*[]()~`>#+-=|{}.!'
    
    # Escape each special character with backslash
    escaped = text
    for char in special_chars:
        escaped = escaped.replace(char, f'\\{char}')
    
    return escaped


def format_resource_change(change: ResourceChange) -> str:
    """
    Format a single resource change for Telegram message.
    
    Args:
        change: ResourceChange object to format
        
    Returns:
        Formatted string for the resource change
    """
    # Action emoji mapping
    action_emoji = {
        "create": "➕",
        "update": "📝",
        "delete": "❌",
        "replace": "🔄",
        "no-op": "✓",
    }
    
    emoji = action_emoji.get(change.action.value, "•")
    resource_display = escape_markdown(change.display_name)
    
    lines = [f"{emoji} *{resource_display}*"]
    
    for summary in change.change_summary:
        escaped_summary = escape_markdown(summary)
        lines.append(f"  • {escaped_summary}")
    
    return "\n".join(lines)


def format_drift_message(event: DriftDetectionEvent) -> str:
    """
    Format a drift detection event into a Telegram message.
    
    Args:
        event: DriftDetectionEvent to format
        
    Returns:
        Formatted Telegram message in MarkdownV2 format
    """
    # Header with emoji
    lines = ["🚨 *Infrastructure Drift Detected*", ""]
    
    # Metadata section
    timestamp_str = event.timestamp.strftime("%Y\\-m\\-%d %H:%M:%S UTC")
    lines.append(f"*Branch:* {escape_markdown(event.branch)}")
    lines.append(f"*Time:* {timestamp_str}")
    lines.append(f"*Resources Affected:* {event.total_changes}")
    lines.append("")
    
    # Changes summary by action
    if event.changes_by_action:
        changes_summary = ", ".join(
            f"{action}: {count}"
            for action, count in sorted(event.changes_by_action.items())
        )
        lines.append(f"*Changes:* {escape_markdown(changes_summary)}")
        lines.append("")
    
    # Separator
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("")
    
    # Resource changes
    for change in event.resource_changes:
        lines.append(format_resource_change(change))
        lines.append("")
    
    # Footer with link
    if event.workflow_run_url:
        escaped_url = event.workflow_run_url  # URLs don't need full escaping
        lines.append(f"[View Full Report]({escaped_url})")
    
    return "\n".join(lines)


def split_message(
    message: str,
    event: DriftDetectionEvent,
    max_length: int = MAX_MESSAGE_LENGTH
) -> List[NotificationPart]:
    """
    Split a message into multiple parts if it exceeds Telegram's limit.
    
    Splits on resource boundaries to maintain readability.
    Adds part indicators (e.g., "Message 1/3") to each part.
    
    Args:
        message: Full formatted message
        event: Original drift event (for resource-aware splitting)
        max_length: Maximum length per message (default: 4096)
        
    Returns:
        List of NotificationPart objects
    """
    effective_max = max_length - MESSAGE_BUFFER
    
    # If message fits in one part, return single part
    if len(message) <= effective_max:
        return [
            NotificationPart(
                part_number=1,
                total_parts=1,
                content=message
            )
        ]
    
    # Split message into parts
    parts = []
    
    # Find header section (up to separator)
    separator = "━━━━━━━━━━━━━━━━"
    separator_idx = message.find(separator)
    
    if separator_idx > 0:
        header = message[:separator_idx + len(separator) + 1]
        content = message[separator_idx + len(separator) + 1:]
    else:
        header = ""
        content = message
    
    # Split content on double newlines (resource boundaries)
    sections = content.split("\n\n")
    
    current_part = header
    part_contents = []
    
    for section in sections:
        if not section.strip():
            continue
            
        test_content = current_part + "\n\n" + section if current_part else section
        
        if len(test_content) > effective_max:
            if current_part:
                part_contents.append(current_part)
            current_part = section
        else:
            current_part = test_content
    
    # Add remaining content
    if current_part:
        part_contents.append(current_part)
    
    # If still only one part but too long, force split by character
    if len(part_contents) == 1 and len(part_contents[0]) > effective_max:
        long_content = part_contents[0]
        part_contents = []
        
        while long_content:
            # Find a good break point (newline)
            if len(long_content) <= effective_max:
                part_contents.append(long_content)
                break
            
            # Find last newline before limit
            break_point = long_content.rfind('\n', 0, effective_max)
            if break_point == -1:
                break_point = effective_max
            
            part_contents.append(long_content[:break_point])
            long_content = long_content[break_point:].lstrip('\n')
    
    total_parts = len(part_contents)
    
    # Create NotificationPart objects with part indicators
    for i, content in enumerate(part_contents, 1):
        if total_parts > 1:
            part_header = f"🔔 *Drift Alert \\(Part {i}/{total_parts}\\)*\n\n"
            final_content = part_header + content
        else:
            final_content = content
        
        # Ensure we don't exceed max length
        if len(final_content) > max_length:
            final_content = final_content[:max_length - 3] + "\\.\\.\\."
        
        parts.append(
            NotificationPart(
                part_number=i,
                total_parts=total_parts,
                content=final_content
            )
        )
    
    return parts


def format_no_drift_message(event: DriftDetectionEvent) -> str:
    """
    Format a message for when no drift is detected.
    
    Args:
        event: DriftDetectionEvent with drift_detected=False
        
    Returns:
        Formatted Telegram message
    """
    timestamp_str = event.timestamp.strftime("%Y\\-m\\-%d %H:%M:%S UTC")
    
    lines = [
        "✅ *No Infrastructure Drift Detected*",
        "",
        f"*Branch:* {escape_markdown(event.branch)}",
        f"*Time:* {timestamp_str}",
        "",
        "All infrastructure resources match their expected state\\.",
    ]
    
    if event.workflow_run_url:
        lines.append("")
        lines.append(f"[View Details]({event.workflow_run_url})")
    
    return "\n".join(lines)
