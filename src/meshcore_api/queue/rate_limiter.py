"""
Token bucket rate limiter for controlling command throughput.
"""
import asyncio
import time
from typing import Optional


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter implementation.

    Allows controlled bursts while maintaining average rate over time.
    Each command consumes one token. Tokens refill at a constant rate.
    """

    def __init__(
        self,
        rate: float,
        burst: int,
        enabled: bool = True,
    ):
        """
        Initialize the rate limiter.

        Args:
            rate: Tokens added per second (average rate)
            burst: Maximum tokens (burst capacity)
            enabled: Whether rate limiting is enabled
        """
        self.rate = rate
        self.burst = burst
        self.enabled = enabled
        self._tokens = float(burst)  # Start with full bucket
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens from the bucket.

        Blocks until enough tokens are available.

        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        if not self.enabled or self.rate <= 0:
            return  # No rate limiting

        async with self._lock:
            while True:
                # Refill tokens based on time elapsed
                now = time.monotonic()
                elapsed = now - self._last_update
                self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
                self._last_update = now

                # Check if we have enough tokens
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                # Calculate wait time for next token
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate

                # Release lock and wait
                self._lock.release()
                await asyncio.sleep(wait_time)
                await self._lock.acquire()

    def get_available_tokens(self) -> float:
        """
        Get the current number of available tokens.

        Returns:
            Number of tokens currently available (returns -1.0 if rate limiting is disabled)
        """
        if not self.enabled or self.rate <= 0:
            return -1.0  # Indicates unlimited (rate limiting disabled)

        # Update tokens based on elapsed time
        now = time.monotonic()
        elapsed = now - self._last_update
        tokens = min(self.burst, self._tokens + elapsed * self.rate)
        return tokens

    async def try_acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Try to acquire tokens with optional timeout.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            True if tokens acquired, False if timeout
        """
        if not self.enabled or self.rate <= 0:
            return True

        try:
            await asyncio.wait_for(self.acquire(tokens), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
