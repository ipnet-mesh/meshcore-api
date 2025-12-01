"""Unit tests for command debouncer."""

import asyncio
from datetime import datetime, timedelta

import pytest

from meshcore_api.queue.debouncer import CommandDebouncer
from meshcore_api.queue.models import CommandResult, CommandType


@pytest.mark.asyncio
class TestCommandDebouncerInit:
    """Test CommandDebouncer initialization."""

    async def test_init_default(self):
        """Test initialization with default values."""
        enabled_commands = {CommandType.SEND_MESSAGE, CommandType.SEND_CHANNEL_MESSAGE}
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands=enabled_commands,
            enabled=True,
        )
        assert debouncer.window_seconds == 60.0
        assert debouncer.max_cache_size == 100
        assert debouncer.enabled_commands == enabled_commands
        assert debouncer.enabled is True
        assert debouncer.get_cache_size() == 0

    async def test_init_disabled(self):
        """Test initialization with debouncing disabled."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
            enabled=False,
        )
        assert debouncer.enabled is False


@pytest.mark.asyncio
class TestCommandDebouncerHashing:
    """Test command hashing."""

    async def test_hash_same_command_same_hash(self):
        """Test same command produces same hash."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        params = {"destination": "abc123", "text": "Hello"}
        hash1 = debouncer._hash_command(CommandType.SEND_MESSAGE, params)
        hash2 = debouncer._hash_command(CommandType.SEND_MESSAGE, params)

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 produces 64 hex chars

    async def test_hash_different_params_different_hash(self):
        """Test different parameters produce different hashes."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        params1 = {"destination": "abc123", "text": "Hello"}
        params2 = {"destination": "abc123", "text": "Goodbye"}

        hash1 = debouncer._hash_command(CommandType.SEND_MESSAGE, params1)
        hash2 = debouncer._hash_command(CommandType.SEND_MESSAGE, params2)

        assert hash1 != hash2

    async def test_hash_param_order_irrelevant(self):
        """Test parameter order doesn't affect hash."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        # Same params, different order
        params1 = {"destination": "abc123", "text": "Hello"}
        params2 = {"text": "Hello", "destination": "abc123"}

        hash1 = debouncer._hash_command(CommandType.SEND_MESSAGE, params1)
        hash2 = debouncer._hash_command(CommandType.SEND_MESSAGE, params2)

        assert hash1 == hash2


@pytest.mark.asyncio
class TestCommandDebouncerCheckDuplicate:
    """Test duplicate detection."""

    async def test_check_duplicate_disabled(self):
        """Test duplicate check returns False when disabled."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
            enabled=False,
        )

        is_dup, hash_val, time_val = await debouncer.check_duplicate(
            CommandType.SEND_MESSAGE, {"destination": "abc123", "text": "Hello"}
        )

        assert is_dup is False
        assert hash_val is None
        assert time_val is None

    async def test_check_duplicate_command_not_enabled(self):
        """Test duplicate check returns False for non-enabled commands."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},  # Only send_message enabled
            enabled=True,
        )

        # Try a different command type
        is_dup, hash_val, time_val = await debouncer.check_duplicate(
            CommandType.SEND_TRACE_PATH, {"destination": "abc123"}
        )

        assert is_dup is False
        assert hash_val is None
        assert time_val is None

    async def test_check_duplicate_first_occurrence(self):
        """Test first occurrence is not a duplicate."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        is_dup, hash_val, time_val = await debouncer.check_duplicate(
            CommandType.SEND_MESSAGE, {"destination": "abc123", "text": "Hello"}
        )

        assert is_dup is False
        assert hash_val is not None
        assert time_val is None
        assert debouncer.get_cache_size() == 1

    async def test_check_duplicate_second_occurrence(self):
        """Test second occurrence is detected as duplicate."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        params = {"destination": "abc123", "text": "Hello"}

        # First occurrence
        is_dup1, hash1, time1 = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params)
        assert is_dup1 is False

        # Second occurrence (should be duplicate)
        is_dup2, hash2, time2 = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params)

        assert is_dup2 is True
        assert hash2 == hash1
        assert time2 is not None
        assert isinstance(time2, datetime)

    async def test_check_duplicate_after_expiry(self):
        """Test command is not duplicate after expiry."""
        debouncer = CommandDebouncer(
            window_seconds=0.1,  # Very short window
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        params = {"destination": "abc123", "text": "Hello"}

        # First occurrence
        is_dup1, hash1, _ = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params)
        assert is_dup1 is False

        # Wait for expiry
        await asyncio.sleep(0.15)

        # Should not be duplicate anymore
        is_dup2, hash2, time2 = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params)

        assert is_dup2 is False
        assert time2 is None


@pytest.mark.asyncio
class TestCommandDebouncerCompletion:
    """Test command completion and result caching."""

    async def test_mark_completed(self):
        """Test marking a command as completed."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        params = {"destination": "abc123", "text": "Hello"}
        is_dup, cmd_hash, _ = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params)

        # Mark as completed
        result = CommandResult(success=True, message="Sent successfully", request_id="test-req")
        await debouncer.mark_completed(cmd_hash, result)

        # Verify result is cached
        cached_result = await debouncer.get_cached_result(cmd_hash)
        assert cached_result is not None
        assert cached_result.success is True
        assert cached_result.message == "Sent successfully"

    async def test_waiters_notified_on_completion(self):
        """Test that waiters are notified when command completes."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        params = {"destination": "abc123", "text": "Hello"}
        is_dup, cmd_hash, _ = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params)

        # Add waiters
        waiter1 = await debouncer.add_waiter(cmd_hash)
        waiter2 = await debouncer.add_waiter(cmd_hash)

        # Mark as completed
        result = CommandResult(success=True, message="Done", request_id="test-req")
        await debouncer.mark_completed(cmd_hash, result)

        # Waiters should be resolved
        assert waiter1.done()
        assert waiter2.done()
        assert waiter1.result() == result
        assert waiter2.result() == result

    async def test_get_cached_result_nonexistent(self):
        """Test getting cached result for nonexistent hash."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        result = await debouncer.get_cached_result("nonexistent_hash")
        assert result is None


@pytest.mark.asyncio
class TestCommandDebouncerCacheManagement:
    """Test cache size limits and eviction."""

    async def test_cache_size_limit(self):
        """Test cache respects max size limit."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=3,  # Small cache
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        # Add 5 commands (more than max)
        for i in range(5):
            params = {"destination": "abc123", "text": f"Message {i}"}
            await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params)

            # Mark first few as completed so they can be evicted
            if i < 2:
                is_dup, cmd_hash, _ = await debouncer.check_duplicate(
                    CommandType.SEND_MESSAGE, params
                )
                result = CommandResult(success=True, message="Done", request_id="test-req")
                await debouncer.mark_completed(cmd_hash, result)

        # Cache should not exceed max size
        assert debouncer.get_cache_size() <= 3

    async def test_lru_eviction(self):
        """Test LRU eviction of completed entries."""
        debouncer = CommandDebouncer(
            window_seconds=60.0,
            max_cache_size=2,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        # Add and complete first command
        params1 = {"destination": "abc123", "text": "First"}
        _, hash1, _ = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params1)
        await debouncer.mark_completed(
            hash1, CommandResult(success=True, message="Done1", request_id="test-req")
        )

        # Add and complete second command
        params2 = {"destination": "abc123", "text": "Second"}
        _, hash2, _ = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params2)
        await debouncer.mark_completed(
            hash2, CommandResult(success=True, message="Done2", request_id="test-req")
        )

        # Add third command (should evict oldest completed)
        params3 = {"destination": "abc123", "text": "Third"}
        await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params3)

        # Cache should be at max size
        assert debouncer.get_cache_size() == 2


@pytest.mark.asyncio
class TestCommandDebouncerCleanup:
    """Test background cleanup task."""

    async def test_cleanup_task_starts(self):
        """Test cleanup task can be started."""
        debouncer = CommandDebouncer(
            window_seconds=0.1,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        debouncer.start_cleanup()
        assert debouncer._cleanup_task is not None
        assert not debouncer._cleanup_task.done()

        await debouncer.stop_cleanup()

    async def test_cleanup_task_stops(self):
        """Test cleanup task can be stopped."""
        debouncer = CommandDebouncer(
            window_seconds=0.1,
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        debouncer.start_cleanup()
        await debouncer.stop_cleanup()
        assert debouncer._cleanup_task.cancelled() or debouncer._cleanup_task.done()

    async def test_cleanup_removes_expired(self):
        """Test cleanup removes expired entries."""
        debouncer = CommandDebouncer(
            window_seconds=0.1,  # Short window
            max_cache_size=100,
            enabled_commands={CommandType.SEND_MESSAGE},
        )

        # Add and complete a command
        params = {"destination": "abc123", "text": "Hello"}
        _, cmd_hash, _ = await debouncer.check_duplicate(CommandType.SEND_MESSAGE, params)
        await debouncer.mark_completed(
            cmd_hash, CommandResult(success=True, message="Done", request_id="test-req")
        )

        assert debouncer.get_cache_size() == 1

        # Start cleanup
        debouncer.start_cleanup()

        # Wait for expiry and cleanup
        await asyncio.sleep(0.25)

        # Entry should be cleaned up
        assert debouncer.get_cache_size() == 0

        await debouncer.stop_cleanup()
