"""Unit tests for queue data models."""

from datetime import datetime

import pytest

from meshcore_api.queue.models import (
    CommandResult,
    CommandType,
    QueuedCommand,
    QueueFullBehavior,
    QueueInfo,
    QueueStats,
)


class TestCommandType:
    """Test CommandType enum."""

    def test_command_types_exist(self):
        """Test all expected command types exist."""
        assert CommandType.SEND_MESSAGE.value == "send_message"
        assert CommandType.SEND_CHANNEL_MESSAGE.value == "send_channel_message"
        assert CommandType.SEND_ADVERT.value == "send_advert"
        assert CommandType.SEND_TRACE_PATH.value == "send_trace_path"
        assert CommandType.PING.value == "ping"
        assert CommandType.SEND_TELEMETRY_REQUEST.value == "send_telemetry_request"

    def test_command_type_is_string_enum(self):
        """Test CommandType inherits from str."""
        assert isinstance(CommandType.SEND_MESSAGE, str)
        assert CommandType.SEND_MESSAGE == "send_message"


class TestQueueFullBehavior:
    """Test QueueFullBehavior enum."""

    def test_behaviors_exist(self):
        """Test both queue full behaviors exist."""
        assert QueueFullBehavior.REJECT.value == "reject"
        assert QueueFullBehavior.DROP_OLDEST.value == "drop_oldest"


class TestQueuedCommand:
    """Test QueuedCommand dataclass."""

    def test_create_queued_command(self):
        """Test creating a QueuedCommand."""
        cmd = QueuedCommand(
            command_type=CommandType.SEND_MESSAGE,
            parameters={"destination": "abc123", "text": "Hello"},
        )
        assert cmd.command_type == CommandType.SEND_MESSAGE
        assert cmd.parameters == {"destination": "abc123", "text": "Hello"}
        assert cmd.request_id is not None
        assert cmd.enqueued_at is not None
        assert cmd.command_hash is None

    def test_queued_command_with_hash(self):
        """Test QueuedCommand with command hash."""
        cmd = QueuedCommand(
            command_type=CommandType.SEND_MESSAGE,
            parameters={"text": "Hello"},
            command_hash="abc123hash",
        )
        assert cmd.command_hash == "abc123hash"

    def test_queued_command_auto_request_id(self):
        """Test QueuedCommand generates unique request IDs."""
        cmd1 = QueuedCommand(command_type=CommandType.PING, parameters={})
        cmd2 = QueuedCommand(command_type=CommandType.PING, parameters={})
        assert cmd1.request_id != cmd2.request_id

    def test_queued_command_to_dict(self):
        """Test QueuedCommand serialization."""
        cmd = QueuedCommand(
            command_type=CommandType.SEND_CHANNEL_MESSAGE,
            parameters={"text": "Hello", "flood": False},
        )
        result = cmd.to_dict()
        assert result["command_type"] == "send_channel_message"
        assert result["parameters"] == {"text": "Hello", "flood": False}
        assert "request_id" in result
        assert "enqueued_at" in result

    def test_queued_command_to_dict_datetime_format(self):
        """Test QueuedCommand to_dict produces ISO format datetime."""
        cmd = QueuedCommand(command_type=CommandType.PING, parameters={})
        result = cmd.to_dict()
        # Should be ISO format string
        assert isinstance(result["enqueued_at"], str)
        # Should be parseable as ISO datetime
        datetime.fromisoformat(result["enqueued_at"])


class TestCommandResult:
    """Test CommandResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful CommandResult."""
        result = CommandResult(
            success=True,
            message="Command executed successfully",
            request_id="test-123",
        )
        assert result.success is True
        assert result.message == "Command executed successfully"
        assert result.request_id == "test-123"
        assert result.executed_at is not None
        assert result.error is None
        assert result.details is None

    def test_create_failure_result(self):
        """Test creating a failed CommandResult."""
        result = CommandResult(
            success=False,
            message="Command failed",
            request_id="test-456",
            error="Connection timeout",
        )
        assert result.success is False
        assert result.error == "Connection timeout"

    def test_result_with_details(self):
        """Test CommandResult with details."""
        result = CommandResult(
            success=True,
            message="Done",
            request_id="test-789",
            details={"hops": 3, "latency_ms": 150},
        )
        assert result.details == {"hops": 3, "latency_ms": 150}

    def test_command_result_to_dict_success(self):
        """Test CommandResult to_dict for success."""
        result = CommandResult(
            success=True,
            message="Success",
            request_id="test-1",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["message"] == "Success"
        assert "error" not in d

    def test_command_result_to_dict_with_error(self):
        """Test CommandResult to_dict includes error."""
        result = CommandResult(
            success=False,
            message="Failed",
            request_id="test-2",
            error="Network error",
        )
        d = result.to_dict()
        assert d["error"] == "Network error"

    def test_command_result_to_dict_with_details(self):
        """Test CommandResult to_dict merges details."""
        result = CommandResult(
            success=True,
            message="Done",
            request_id="test-3",
            details={"extra_field": "value"},
        )
        d = result.to_dict()
        assert d["extra_field"] == "value"


class TestQueueStats:
    """Test QueueStats dataclass."""

    def test_create_queue_stats(self):
        """Test creating QueueStats."""
        stats = QueueStats(
            queue_size=10,
            max_queue_size=100,
            rate_limit_tokens_available=4.5,
            debounce_cache_size=50,
            commands_processed_total=1000,
            commands_dropped_total=5,
            commands_debounced_total=200,
        )
        assert stats.queue_size == 10
        assert stats.max_queue_size == 100
        assert stats.rate_limit_tokens_available == 4.5
        assert stats.debounce_cache_size == 50
        assert stats.commands_processed_total == 1000
        assert stats.commands_dropped_total == 5
        assert stats.commands_debounced_total == 200

    def test_queue_stats_to_dict(self):
        """Test QueueStats serialization."""
        stats = QueueStats(
            queue_size=5,
            max_queue_size=50,
            rate_limit_tokens_available=2.333333,
            debounce_cache_size=25,
            commands_processed_total=500,
            commands_dropped_total=2,
            commands_debounced_total=100,
        )
        d = stats.to_dict()
        assert d["queue_size"] == 5
        assert d["max_queue_size"] == 50
        # Should be rounded to 2 decimal places
        assert d["rate_limit_tokens_available"] == 2.33
        assert d["debounce_cache_size"] == 25
        assert d["commands_processed_total"] == 500
        assert d["commands_dropped_total"] == 2
        assert d["commands_debounced_total"] == 100


class TestQueueInfo:
    """Test QueueInfo dataclass."""

    def test_create_queue_info(self):
        """Test creating QueueInfo."""
        info = QueueInfo(
            position=3,
            estimated_wait_seconds=1.5,
            queue_size=10,
        )
        assert info.position == 3
        assert info.estimated_wait_seconds == 1.5
        assert info.queue_size == 10
        assert info.debounced is False
        assert info.original_request_time is None

    def test_queue_info_debounced(self):
        """Test QueueInfo for debounced command."""
        original_time = datetime.utcnow()
        info = QueueInfo(
            position=1,
            estimated_wait_seconds=0.5,
            queue_size=5,
            debounced=True,
            original_request_time=original_time,
        )
        assert info.debounced is True
        assert info.original_request_time == original_time

    def test_queue_info_to_dict(self):
        """Test QueueInfo serialization."""
        info = QueueInfo(
            position=2,
            estimated_wait_seconds=1.2345,
            queue_size=8,
        )
        d = info.to_dict()
        assert d["position"] == 2
        # Should be rounded
        assert d["estimated_wait_seconds"] == 1.23
        assert d["queue_size"] == 8
        assert d["debounced"] is False
        assert "original_request_time" not in d

    def test_queue_info_to_dict_with_original_time(self):
        """Test QueueInfo serialization includes original time."""
        original_time = datetime(2024, 1, 15, 10, 30, 0)
        info = QueueInfo(
            position=1,
            estimated_wait_seconds=0.5,
            queue_size=5,
            debounced=True,
            original_request_time=original_time,
        )
        d = info.to_dict()
        assert d["debounced"] is True
        assert d["original_request_time"] == "2024-01-15T10:30:00Z"
