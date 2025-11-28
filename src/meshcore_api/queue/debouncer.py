"""
Command debouncer for preventing duplicate commands.
"""
import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .models import CommandResult, CommandType


@dataclass
class DebouncedCommand:
    """A command that is being debounced."""

    command_hash: str
    first_seen: datetime
    last_seen: datetime
    pending: bool = True
    result: Optional[CommandResult] = None
    waiters: list[asyncio.Future] = field(default_factory=list)


class CommandDebouncer:
    """
    Debounces duplicate commands within a time window.

    Uses content-based hashing to identify duplicates.
    """

    def __init__(
        self,
        window_seconds: float,
        max_cache_size: int,
        enabled_commands: set[CommandType],
        enabled: bool = True,
    ):
        """
        Initialize the debouncer.

        Args:
            window_seconds: Time window to consider duplicates
            max_cache_size: Maximum entries in cache
            enabled_commands: Command types to debounce
            enabled: Whether debouncing is enabled
        """
        self.window_seconds = window_seconds
        self.max_cache_size = max_cache_size
        self.enabled_commands = enabled_commands
        self.enabled = enabled
        self._cache: dict[str, DebouncedCommand] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def _hash_command(self, command_type: CommandType, parameters: dict[str, Any]) -> str:
        """
        Generate a hash for a command.

        Args:
            command_type: Type of command
            parameters: Command parameters

        Returns:
            SHA256 hash of command content
        """
        # Create a canonical representation
        content = {
            "type": command_type.value,
            "params": parameters,
        }
        # Sort keys for consistent hashing
        canonical = json.dumps(content, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _is_expired(self, cmd: DebouncedCommand) -> bool:
        """
        Check if a debounced command has expired.

        Args:
            cmd: Debounced command to check

        Returns:
            True if expired, False otherwise
        """
        elapsed = (datetime.utcnow() - cmd.last_seen).total_seconds()
        return elapsed > self.window_seconds

    async def _cleanup_expired(self) -> None:
        """Periodically clean up expired entries from cache."""
        while True:
            try:
                await asyncio.sleep(self.window_seconds)
                async with self._lock:
                    # Remove expired entries
                    expired_hashes = [
                        h for h, cmd in self._cache.items()
                        if self._is_expired(cmd) and not cmd.pending
                    ]
                    for h in expired_hashes:
                        del self._cache[h]
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but keep cleanup task running
                pass

    def start_cleanup(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_expired())

    async def stop_cleanup(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def check_duplicate(
        self,
        command_type: CommandType,
        parameters: dict[str, Any],
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """
        Check if a command is a duplicate.

        Args:
            command_type: Type of command
            parameters: Command parameters

        Returns:
            Tuple of (is_duplicate, command_hash, original_request_time)
        """
        if not self.enabled or command_type not in self.enabled_commands:
            return False, None, None

        command_hash = self._hash_command(command_type, parameters)

        async with self._lock:
            # Check if hash exists and is not expired
            if command_hash in self._cache:
                cmd = self._cache[command_hash]
                if not self._is_expired(cmd):
                    # Update last seen
                    cmd.last_seen = datetime.utcnow()
                    return True, command_hash, cmd.first_seen
                else:
                    # Expired, remove it
                    del self._cache[command_hash]

            # Not a duplicate, add to cache
            if len(self._cache) >= self.max_cache_size:
                # Simple LRU: remove oldest non-pending entry
                oldest_hash = None
                oldest_time = None
                for h, cmd in self._cache.items():
                    if not cmd.pending and (oldest_time is None or cmd.last_seen < oldest_time):
                        oldest_hash = h
                        oldest_time = cmd.last_seen
                if oldest_hash:
                    del self._cache[oldest_hash]

            now = datetime.utcnow()
            self._cache[command_hash] = DebouncedCommand(
                command_hash=command_hash,
                first_seen=now,
                last_seen=now,
                pending=True,
            )

            return False, command_hash, None

    async def add_waiter(self, command_hash: str) -> asyncio.Future:
        """
        Add a waiter for a pending command.

        Args:
            command_hash: Hash of the command to wait for

        Returns:
            Future that will be resolved when command completes
        """
        async with self._lock:
            if command_hash not in self._cache:
                raise ValueError(f"Command hash {command_hash} not in cache")

            future = asyncio.Future()
            self._cache[command_hash].waiters.append(future)
            return future

    async def mark_completed(
        self,
        command_hash: str,
        result: CommandResult,
    ) -> None:
        """
        Mark a command as completed and notify waiters.

        Args:
            command_hash: Hash of the completed command
            result: Result of the command execution
        """
        async with self._lock:
            if command_hash not in self._cache:
                return

            cmd = self._cache[command_hash]
            cmd.pending = False
            cmd.result = result

            # Notify all waiters
            for waiter in cmd.waiters:
                if not waiter.done():
                    waiter.set_result(result)
            cmd.waiters.clear()

    async def get_cached_result(
        self,
        command_hash: str,
    ) -> Optional[CommandResult]:
        """
        Get cached result for a command.

        Args:
            command_hash: Hash of the command

        Returns:
            Cached result if available, None otherwise
        """
        async with self._lock:
            if command_hash in self._cache:
                cmd = self._cache[command_hash]
                if not self._is_expired(cmd):
                    return cmd.result
            return None

    def get_cache_size(self) -> int:
        """Get current cache size."""
        return len(self._cache)
