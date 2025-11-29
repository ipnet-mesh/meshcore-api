"""
Command queue manager for handling MeshCore outbound actions.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from ..meshcore.interface import MeshCoreInterface
from .debouncer import CommandDebouncer
from .models import (
    CommandResult,
    CommandType,
    QueuedCommand,
    QueueFullBehavior,
    QueueInfo,
    QueueStats,
)
from .rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


class QueueFullError(Exception):
    """Raised when the command queue is full and cannot accept new commands."""

    pass


class CommandQueueManager:
    """
    Manages the command queue for MeshCore outbound actions.

    Provides rate limiting, debouncing, and queuing for all commands
    sent to the MeshCore network.
    """

    def __init__(
        self,
        meshcore: MeshCoreInterface,
        max_queue_size: int = 100,
        queue_full_behavior: QueueFullBehavior = QueueFullBehavior.REJECT,
        rate_limit_per_second: float = 2.0,
        rate_limit_burst: int = 5,
        rate_limit_enabled: bool = True,
        debounce_window_seconds: float = 5.0,
        debounce_cache_max_size: int = 1000,
        debounce_enabled: bool = True,
        debounce_commands: Optional[set[CommandType]] = None,
    ):
        """
        Initialize the command queue manager.

        Args:
            meshcore: MeshCore interface for executing commands
            max_queue_size: Maximum number of queued commands
            queue_full_behavior: Behavior when queue is full
            rate_limit_per_second: Commands per second (average)
            rate_limit_burst: Maximum burst size
            rate_limit_enabled: Enable rate limiting
            debounce_window_seconds: Debounce time window
            debounce_cache_max_size: Max debounce cache entries
            debounce_enabled: Enable debouncing
            debounce_commands: Command types to debounce (default: messages and adverts)
        """
        self.meshcore = meshcore
        self.max_queue_size = max_queue_size
        self.queue_full_behavior = queue_full_behavior

        # Initialize queue
        self._queue: asyncio.Queue[QueuedCommand] = asyncio.Queue(maxsize=max_queue_size)

        # Initialize rate limiter
        self._rate_limiter = TokenBucketRateLimiter(
            rate=rate_limit_per_second,
            burst=rate_limit_burst,
            enabled=rate_limit_enabled,
        )

        # Initialize debouncer
        if debounce_commands is None:
            debounce_commands = {
                CommandType.SEND_MESSAGE,
                CommandType.SEND_CHANNEL_MESSAGE,
                CommandType.SEND_ADVERT,
            }
        self._debouncer = CommandDebouncer(
            window_seconds=debounce_window_seconds,
            max_cache_size=debounce_cache_max_size,
            enabled_commands=debounce_commands,
            enabled=debounce_enabled,
        )

        # Statistics
        self._commands_processed = 0
        self._commands_dropped = 0
        self._commands_debounced = 0

        # Worker task
        self._worker_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the background worker task."""
        if self._worker_task is None or self._worker_task.done():
            logger.info("Starting command queue worker")
            self._shutdown_event.clear()
            self._worker_task = asyncio.create_task(self._worker())
            self._debouncer.start_cleanup()

    async def stop(self) -> None:
        """Stop the background worker task."""
        logger.info("Stopping command queue worker")
        self._shutdown_event.set()

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        await self._debouncer.stop_cleanup()
        logger.info("Command queue worker stopped")

    async def enqueue(
        self,
        command_type: CommandType,
        parameters: dict[str, Any],
    ) -> tuple[CommandResult, QueueInfo]:
        """
        Enqueue a command for execution (non-blocking).

        This method returns immediately after adding the command to the queue.
        It does NOT wait for the command to be executed.

        Args:
            command_type: Type of command to execute
            parameters: Command parameters

        Returns:
            Tuple of (result, queue_info) - result indicates queued, not executed

        Raises:
            QueueFullError: If queue is full and behavior is REJECT
        """
        # Check for duplicates
        is_duplicate, command_hash, original_time = await self._debouncer.check_duplicate(
            command_type, parameters
        )

        if is_duplicate:
            logger.debug(
                f"Command {command_type.value} is a duplicate, debouncing",
                extra={"command_hash": command_hash},
            )
            self._commands_debounced += 1

            # Check if original command has completed
            cached_result = await self._debouncer.get_cached_result(command_hash)

            queue_info = QueueInfo(
                position=1,  # Approximate - it's somewhere in queue
                estimated_wait_seconds=self._estimate_wait_time(),
                queue_size=self._queue.qsize(),
                debounced=True,
                original_request_time=original_time,
            )

            if cached_result is not None:
                # Original command has completed, return its result
                logger.debug(
                    f"Returning cached result for debounced command",
                    extra={"command_hash": command_hash, "success": cached_result.success},
                )
                return cached_result, queue_info
            else:
                # Original command still pending
                result = CommandResult(
                    success=True,
                    message="Command already queued (pending execution)",
                    request_id="debounced",
                )
                return result, queue_info

        # Not a duplicate, enqueue normally
        command = QueuedCommand(
            command_type=command_type,
            parameters=parameters,
            command_hash=command_hash,  # Store hash for marking completed later
        )

        try:
            # Try to add to queue (non-blocking)
            self._queue.put_nowait(command)
            position = self._queue.qsize()

            queue_info = QueueInfo(
                position=position,
                estimated_wait_seconds=self._estimate_wait_time(position),
                queue_size=position,
                debounced=False,
            )

            result = CommandResult(
                success=True,
                message=f"Command queued successfully (position {position})",
                request_id=command.request_id,
            )

            logger.debug(
                f"Command {command_type.value} queued at position {position}",
                extra={"request_id": command.request_id},
            )

            return result, queue_info

        except asyncio.QueueFull:
            # Queue is full, handle based on behavior
            if self.queue_full_behavior == QueueFullBehavior.REJECT:
                logger.warning(f"Queue full, rejecting command {command_type.value}")
                self._commands_dropped += 1

                # Mark command as failed in debouncer before rejecting
                if command_hash:
                    failure_result = CommandResult(
                        success=False,
                        message="Command queue is full",
                        request_id=command.request_id,
                        error="queue_full",
                    )
                    await self._debouncer.mark_completed(command_hash, failure_result)
                    logger.debug(
                        f"Marked rejected command as failed in debouncer",
                        extra={"command_hash": command_hash},
                    )

                raise QueueFullError("Command queue is full")
            else:  # DROP_OLDEST
                logger.warning(f"Queue full, dropping oldest command for {command_type.value}")
                try:
                    # Remove oldest command
                    dropped = self._queue.get_nowait()
                    self._commands_dropped += 1
                    logger.info(
                        f"Dropped command {dropped.command_type.value} to make room",
                        extra={"dropped_request_id": dropped.request_id},
                    )

                    # Mark dropped command as failed in debouncer
                    if dropped.command_hash:
                        failure_result = CommandResult(
                            success=False,
                            message="Command dropped from queue (queue full)",
                            request_id=dropped.request_id,
                            error="queue_full",
                        )
                        await self._debouncer.mark_completed(dropped.command_hash, failure_result)
                        logger.debug(
                            f"Marked dropped command as failed in debouncer",
                            extra={"command_hash": dropped.command_hash},
                        )

                    # Now try again
                    self._queue.put_nowait(command)
                    position = self._queue.qsize()

                    queue_info = QueueInfo(
                        position=position,
                        estimated_wait_seconds=self._estimate_wait_time(position),
                        queue_size=position,
                        debounced=False,
                    )

                    result = CommandResult(
                        success=True,
                        message=f"Command queued successfully (position {position}, oldest dropped)",
                        request_id=command.request_id,
                    )

                    return result, queue_info

                except asyncio.QueueEmpty:
                    # This shouldn't happen, but handle it
                    raise QueueFullError("Command queue is full")

    def _estimate_wait_time(self, position: Optional[int] = None) -> float:
        """
        Estimate wait time based on queue position and rate limit.

        Args:
            position: Position in queue (if None, uses current queue size)

        Returns:
            Estimated wait time in seconds
        """
        if position is None:
            position = self._queue.qsize()

        if position == 0:
            return 0.0

        # Estimate based on rate limiter
        rate = self._rate_limiter.rate
        if rate <= 0 or not self._rate_limiter.enabled:
            return 0.0  # No rate limiting

        # Calculate wait time: position / rate
        # This is optimistic - assumes tokens are available
        return position / rate

    async def _worker(self) -> None:
        """Background worker that processes the command queue."""
        logger.info("Command queue worker started")

        while not self._shutdown_event.is_set():
            try:
                # Get next command from queue
                try:
                    command = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue  # Check shutdown event

                # Apply rate limiting
                await self._rate_limiter.acquire()

                # Execute command
                logger.debug(
                    f"Processing command {command.command_type.value}",
                    extra={"request_id": command.request_id},
                )

                result = await self._execute_command(command)
                self._commands_processed += 1

                # Mark command as completed in debouncer (allows cache cleanup)
                if command.command_hash:
                    await self._debouncer.mark_completed(command.command_hash, result)

                # Log result
                if result.success:
                    logger.info(
                        f"Command {command.command_type.value} executed successfully",
                        extra={"request_id": command.request_id},
                    )
                else:
                    logger.error(
                        f"Command {command.command_type.value} failed: {result.error}",
                        extra={"request_id": command.request_id},
                    )

                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in command queue worker: {e}", exc_info=True)
                # Continue processing

        logger.info("Command queue worker exiting")

    async def _execute_command(self, command: QueuedCommand) -> CommandResult:
        """
        Execute a queued command.

        Args:
            command: Command to execute

        Returns:
            Result of command execution
        """
        try:
            result = None

            if command.command_type == CommandType.SEND_MESSAGE:
                result = await self.meshcore.send_message(
                    destination=command.parameters["destination"],
                    text=command.parameters["text"],
                    text_type=command.parameters.get("text_type", "plain"),
                )
            elif command.command_type == CommandType.SEND_CHANNEL_MESSAGE:
                result = await self.meshcore.send_channel_message(
                    text=command.parameters["text"],
                    flood=command.parameters.get("flood", False),
                )
            elif command.command_type == CommandType.SEND_ADVERT:
                result = await self.meshcore.send_advert(
                    flood=command.parameters.get("flood", False)
                )
            elif command.command_type == CommandType.SEND_TRACE_PATH:
                result = await self.meshcore.send_trace_path(
                    destination=command.parameters["destination"]
                )
            elif command.command_type == CommandType.PING:
                result = await self.meshcore.ping(destination=command.parameters["destination"])
            elif command.command_type == CommandType.SEND_TELEMETRY_REQUEST:
                result = await self.meshcore.send_telemetry_request(
                    destination=command.parameters["destination"]
                )
            else:
                raise ValueError(f"Unknown command type: {command.command_type}")

            # Convert meshcore result to CommandResult
            # The meshcore methods return Event objects, we need to extract success/message
            return CommandResult(
                success=True,
                message=f"Command {command.command_type.value} executed successfully",
                request_id=command.request_id,
                details={"event": result.to_dict() if hasattr(result, "to_dict") else None},
            )

        except Exception as e:
            logger.error(
                f"Error executing command {command.command_type.value}: {e}",
                extra={"request_id": command.request_id},
                exc_info=True,
            )
            return CommandResult(
                success=False,
                message=f"Command execution failed: {str(e)}",
                request_id=command.request_id,
                error=str(e),
            )

    def get_stats(self) -> QueueStats:
        """
        Get current queue statistics.

        Returns:
            Queue statistics
        """
        return QueueStats(
            queue_size=self._queue.qsize(),
            max_queue_size=self.max_queue_size,
            rate_limit_tokens_available=self._rate_limiter.get_available_tokens(),
            debounce_cache_size=self._debouncer.get_cache_size(),
            commands_processed_total=self._commands_processed,
            commands_dropped_total=self._commands_dropped,
            commands_debounced_total=self._commands_debounced,
        )
