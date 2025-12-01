"""Unit tests for command queue manager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from meshcore_api.queue.manager import CommandQueueManager, QueueFullError
from meshcore_api.queue.models import CommandType, QueueFullBehavior


@pytest.fixture
def mock_meshcore():
    """Create a mock MeshCore interface."""
    mock = MagicMock()
    mock.send_message = AsyncMock(return_value=MagicMock(to_dict=lambda: {}))
    mock.send_channel_message = AsyncMock(return_value=MagicMock(to_dict=lambda: {}))
    mock.send_advert = AsyncMock(return_value=MagicMock(to_dict=lambda: {}))
    mock.send_trace_path = AsyncMock(return_value=MagicMock(to_dict=lambda: {}))
    mock.ping = AsyncMock(return_value=MagicMock(to_dict=lambda: {}))
    mock.send_telemetry_request = AsyncMock(return_value=MagicMock(to_dict=lambda: {}))
    return mock


@pytest_asyncio.fixture
async def queue_manager(mock_meshcore):
    """Create a queue manager for testing."""
    manager = CommandQueueManager(
        meshcore=mock_meshcore,
        max_queue_size=10,
        rate_limit_per_second=100.0,  # Fast for testing
        rate_limit_burst=10,
        debounce_window_seconds=0.1,  # Short for testing
        debounce_enabled=True,
    )
    yield manager
    await manager.stop()


@pytest.mark.asyncio
class TestCommandQueueManagerInit:
    """Test CommandQueueManager initialization."""

    async def test_init_default_values(self, mock_meshcore):
        """Test initialization with default values."""
        manager = CommandQueueManager(meshcore=mock_meshcore)
        assert manager.meshcore is mock_meshcore
        assert manager.max_queue_size == 100
        assert manager.queue_full_behavior == QueueFullBehavior.REJECT
        await manager.stop()

    async def test_init_custom_values(self, mock_meshcore):
        """Test initialization with custom values."""
        manager = CommandQueueManager(
            meshcore=mock_meshcore,
            max_queue_size=50,
            queue_full_behavior=QueueFullBehavior.DROP_OLDEST,
            rate_limit_per_second=0.5,
            rate_limit_burst=3,
            debounce_window_seconds=30.0,
            debounce_cache_max_size=500,
            debounce_enabled=False,
        )
        assert manager.max_queue_size == 50
        assert manager.queue_full_behavior == QueueFullBehavior.DROP_OLDEST
        await manager.stop()

    async def test_init_default_debounce_commands(self, mock_meshcore):
        """Test default debounce commands are set."""
        manager = CommandQueueManager(meshcore=mock_meshcore)
        # Check that debouncer was initialized with default commands
        assert manager._debouncer is not None
        await manager.stop()

    async def test_init_custom_debounce_commands(self, mock_meshcore):
        """Test custom debounce commands can be specified."""
        custom_commands = {CommandType.PING}
        manager = CommandQueueManager(
            meshcore=mock_meshcore,
            debounce_commands=custom_commands,
        )
        assert manager._debouncer.enabled_commands == custom_commands
        await manager.stop()


@pytest.mark.asyncio
class TestCommandQueueManagerStartStop:
    """Test start and stop methods."""

    async def test_start_creates_worker_task(self, queue_manager):
        """Test start creates the worker task."""
        await queue_manager.start()
        assert queue_manager._worker_task is not None
        assert not queue_manager._worker_task.done()

    async def test_start_idempotent(self, queue_manager):
        """Test calling start multiple times is safe."""
        await queue_manager.start()
        task1 = queue_manager._worker_task
        await queue_manager.start()  # Should not create new task
        assert queue_manager._worker_task is task1

    async def test_stop_cancels_worker(self, queue_manager):
        """Test stop cancels the worker task."""
        await queue_manager.start()
        await queue_manager.stop()
        assert queue_manager._worker_task.done() or queue_manager._worker_task.cancelled()

    async def test_stop_without_start(self, queue_manager):
        """Test stop without start is safe."""
        await queue_manager.stop()  # Should not raise
        assert True


@pytest.mark.asyncio
class TestCommandQueueManagerEnqueue:
    """Test enqueue method."""

    async def test_enqueue_command(self, queue_manager):
        """Test enqueueing a command."""
        result, queue_info = await queue_manager.enqueue(
            CommandType.SEND_MESSAGE,
            {"destination": "a" * 64, "text": "Hello"},
        )
        assert result.success is True
        assert queue_info.position == 1
        assert queue_info.debounced is False

    async def test_enqueue_multiple_commands(self, queue_manager):
        """Test enqueueing multiple commands."""
        for i in range(3):
            result, queue_info = await queue_manager.enqueue(
                CommandType.SEND_MESSAGE,
                {"destination": "a" * 64, "text": f"Message {i}"},
            )
            assert result.success is True
            assert queue_info.position == i + 1

    async def test_enqueue_debounces_duplicate(self, queue_manager):
        """Test duplicate commands are debounced."""
        params = {"destination": "a" * 64, "text": "Hello"}

        # First enqueue
        result1, info1 = await queue_manager.enqueue(CommandType.SEND_MESSAGE, params)
        assert result1.success is True
        assert info1.debounced is False

        # Second enqueue (same params - should be debounced)
        result2, info2 = await queue_manager.enqueue(CommandType.SEND_MESSAGE, params)
        assert result2.success is True
        assert info2.debounced is True

    async def test_enqueue_queue_full_reject(self, mock_meshcore):
        """Test enqueue raises error when queue is full and behavior is REJECT."""
        manager = CommandQueueManager(
            meshcore=mock_meshcore,
            max_queue_size=2,
            queue_full_behavior=QueueFullBehavior.REJECT,
            debounce_enabled=False,  # Disable to test queue full
        )

        # Fill the queue
        await manager.enqueue(CommandType.SEND_MESSAGE, {"destination": "a" * 64, "text": "1"})
        await manager.enqueue(CommandType.SEND_MESSAGE, {"destination": "a" * 64, "text": "2"})

        # Third should raise
        with pytest.raises(QueueFullError):
            await manager.enqueue(CommandType.SEND_MESSAGE, {"destination": "a" * 64, "text": "3"})

        await manager.stop()

    async def test_enqueue_queue_full_drop_oldest(self, mock_meshcore):
        """Test enqueue drops oldest when queue is full and behavior is DROP_OLDEST."""
        manager = CommandQueueManager(
            meshcore=mock_meshcore,
            max_queue_size=2,
            queue_full_behavior=QueueFullBehavior.DROP_OLDEST,
            debounce_enabled=False,
        )

        # Fill the queue
        await manager.enqueue(CommandType.SEND_MESSAGE, {"destination": "a" * 64, "text": "1"})
        await manager.enqueue(CommandType.SEND_MESSAGE, {"destination": "a" * 64, "text": "2"})

        # Third should succeed by dropping oldest
        result, info = await manager.enqueue(CommandType.SEND_MESSAGE, {"destination": "a" * 64, "text": "3"})
        assert result.success is True
        assert "dropped" in result.message.lower()

        await manager.stop()


@pytest.mark.asyncio
class TestCommandQueueManagerEstimateWaitTime:
    """Test wait time estimation."""

    async def test_estimate_wait_time_empty_queue(self, queue_manager):
        """Test wait time is 0 for empty queue."""
        wait_time = queue_manager._estimate_wait_time(0)
        assert wait_time == 0.0

    async def test_estimate_wait_time_with_position(self, queue_manager):
        """Test wait time estimation based on position."""
        wait_time = queue_manager._estimate_wait_time(5)
        # With rate of 100/sec, 5 commands = 0.05 seconds
        assert wait_time == pytest.approx(0.05, abs=0.01)

    async def test_estimate_wait_time_rate_limit_disabled(self, mock_meshcore):
        """Test wait time is 0 when rate limiting is disabled."""
        manager = CommandQueueManager(
            meshcore=mock_meshcore,
            rate_limit_enabled=False,
        )
        wait_time = manager._estimate_wait_time(10)
        assert wait_time == 0.0
        await manager.stop()


@pytest.mark.asyncio
class TestCommandQueueManagerWorker:
    """Test the background worker."""

    async def test_worker_processes_commands(self, queue_manager, mock_meshcore):
        """Test worker processes queued commands."""
        await queue_manager.start()

        # Enqueue a command
        await queue_manager.enqueue(
            CommandType.SEND_MESSAGE,
            {"destination": "a" * 64, "text": "Hello"},
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Verify meshcore was called
        mock_meshcore.send_message.assert_called()

    async def test_worker_processes_channel_message(self, queue_manager, mock_meshcore):
        """Test worker processes channel messages."""
        await queue_manager.start()

        await queue_manager.enqueue(
            CommandType.SEND_CHANNEL_MESSAGE,
            {"text": "Broadcast"},
        )

        await asyncio.sleep(0.1)
        mock_meshcore.send_channel_message.assert_called()

    async def test_worker_processes_advert(self, queue_manager, mock_meshcore):
        """Test worker processes advertisements."""
        await queue_manager.start()

        await queue_manager.enqueue(
            CommandType.SEND_ADVERT,
            {"flood": True},
        )

        await asyncio.sleep(0.1)
        mock_meshcore.send_advert.assert_called()

    async def test_worker_processes_trace_path(self, queue_manager, mock_meshcore):
        """Test worker processes trace path commands."""
        await queue_manager.start()

        await queue_manager.enqueue(
            CommandType.SEND_TRACE_PATH,
            {"destination": "a" * 64},
        )

        await asyncio.sleep(0.1)
        mock_meshcore.send_trace_path.assert_called()

    async def test_worker_processes_ping(self, queue_manager, mock_meshcore):
        """Test worker processes ping commands."""
        await queue_manager.start()

        await queue_manager.enqueue(
            CommandType.PING,
            {"destination": "a" * 64},
        )

        await asyncio.sleep(0.1)
        mock_meshcore.ping.assert_called()

    async def test_worker_processes_telemetry_request(self, queue_manager, mock_meshcore):
        """Test worker processes telemetry request commands."""
        await queue_manager.start()

        await queue_manager.enqueue(
            CommandType.SEND_TELEMETRY_REQUEST,
            {"destination": "a" * 64},
        )

        await asyncio.sleep(0.1)
        mock_meshcore.send_telemetry_request.assert_called()

    async def test_worker_handles_command_error(self, mock_meshcore):
        """Test worker handles command execution errors."""
        mock_meshcore.send_message = AsyncMock(side_effect=Exception("Network error"))

        manager = CommandQueueManager(
            meshcore=mock_meshcore,
            rate_limit_per_second=100.0,
            debounce_enabled=False,
        )
        await manager.start()

        await manager.enqueue(
            CommandType.SEND_MESSAGE,
            {"destination": "a" * 64, "text": "Hello"},
        )

        # Should not crash, just log error
        await asyncio.sleep(0.1)
        await manager.stop()


@pytest.mark.asyncio
class TestCommandQueueManagerGetStats:
    """Test get_stats method."""

    async def test_get_stats(self, queue_manager):
        """Test getting queue statistics."""
        stats = queue_manager.get_stats()
        assert stats.queue_size == 0
        assert stats.max_queue_size == 10
        assert stats.commands_processed_total == 0
        assert stats.commands_dropped_total == 0
        assert stats.commands_debounced_total == 0

    async def test_get_stats_after_enqueue(self, queue_manager):
        """Test stats update after enqueueing."""
        await queue_manager.enqueue(
            CommandType.SEND_MESSAGE,
            {"destination": "a" * 64, "text": "Hello"},
        )

        stats = queue_manager.get_stats()
        assert stats.queue_size == 1

    async def test_get_stats_after_processing(self, queue_manager):
        """Test stats update after processing."""
        await queue_manager.start()

        await queue_manager.enqueue(
            CommandType.SEND_MESSAGE,
            {"destination": "a" * 64, "text": "Hello"},
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        stats = queue_manager.get_stats()
        assert stats.commands_processed_total >= 1

    async def test_get_stats_debounced_count(self, queue_manager):
        """Test debounced count in stats."""
        params = {"destination": "a" * 64, "text": "Hello"}

        await queue_manager.enqueue(CommandType.SEND_MESSAGE, params)
        await queue_manager.enqueue(CommandType.SEND_MESSAGE, params)  # Debounced

        stats = queue_manager.get_stats()
        assert stats.commands_debounced_total == 1


@pytest.mark.asyncio
class TestQueueFullError:
    """Test QueueFullError exception."""

    async def test_queue_full_error_message(self):
        """Test QueueFullError has correct message."""
        error = QueueFullError("Test message")
        assert str(error) == "Test message"

    async def test_queue_full_error_is_exception(self):
        """Test QueueFullError is an Exception."""
        error = QueueFullError("Test")
        assert isinstance(error, Exception)
