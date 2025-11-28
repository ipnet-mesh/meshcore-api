"""
Data models for the command queue system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class CommandType(str, Enum):
    """Types of commands that can be queued."""
    SEND_MESSAGE = "send_message"
    SEND_CHANNEL_MESSAGE = "send_channel_message"
    SEND_ADVERT = "send_advert"
    SEND_TRACE_PATH = "send_trace_path"
    PING = "ping"
    SEND_TELEMETRY_REQUEST = "send_telemetry_request"


class QueueFullBehavior(str, Enum):
    """Behavior when the queue is full."""
    REJECT = "reject"  # Reject new commands with error
    DROP_OLDEST = "drop_oldest"  # Drop oldest command to make room


@dataclass
class QueuedCommand:
    """A command waiting in the queue to be executed."""

    command_type: CommandType
    parameters: dict[str, Any]
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enqueued_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "command_type": self.command_type.value,
            "parameters": self.parameters,
            "request_id": self.request_id,
            "enqueued_at": self.enqueued_at.isoformat(),
        }


@dataclass
class CommandResult:
    """Result of executing a command."""

    success: bool
    message: str
    request_id: str
    executed_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    details: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "success": self.success,
            "message": self.message,
        }
        if self.error:
            result["error"] = self.error
        if self.details:
            result.update(self.details)
        return result


@dataclass
class QueueStats:
    """Statistics about the command queue."""

    queue_size: int
    max_queue_size: int
    rate_limit_tokens_available: float
    debounce_cache_size: int
    commands_processed_total: int
    commands_dropped_total: int
    commands_debounced_total: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "queue_size": self.queue_size,
            "max_queue_size": self.max_queue_size,
            "rate_limit_tokens_available": round(self.rate_limit_tokens_available, 2),
            "debounce_cache_size": self.debounce_cache_size,
            "commands_processed_total": self.commands_processed_total,
            "commands_dropped_total": self.commands_dropped_total,
            "commands_debounced_total": self.commands_debounced_total,
        }


@dataclass
class QueueInfo:
    """Information about a command's position in the queue."""

    position: int
    estimated_wait_seconds: float
    queue_size: int
    debounced: bool = False
    original_request_time: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "position": self.position,
            "estimated_wait_seconds": round(self.estimated_wait_seconds, 2),
            "queue_size": self.queue_size,
            "debounced": self.debounced,
        }
        if self.original_request_time:
            result["original_request_time"] = self.original_request_time.isoformat() + "Z"
        return result
