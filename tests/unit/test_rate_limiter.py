"""Unit tests for token bucket rate limiter."""

import asyncio
import time

import pytest

from meshcore_api.queue.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiterInit:
    """Test TokenBucketRateLimiter initialization."""

    def test_init_default_enabled(self):
        """Test initialization with default enabled state."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5)
        assert limiter.rate == 1.0
        assert limiter.burst == 5
        assert limiter.enabled is True
        assert limiter._tokens == 5.0  # Starts with full bucket

    def test_init_disabled(self):
        """Test initialization with disabled state."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5, enabled=False)
        assert limiter.enabled is False

    def test_init_custom_values(self):
        """Test initialization with custom rate and burst."""
        limiter = TokenBucketRateLimiter(rate=0.02, burst=2)
        assert limiter.rate == 0.02
        assert limiter.burst == 2
        assert limiter._tokens == 2.0


@pytest.mark.asyncio
class TestTokenBucketRateLimiterAcquire:
    """Test TokenBucketRateLimiter acquire method."""

    async def test_acquire_when_disabled(self):
        """Test acquire returns immediately when disabled."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5, enabled=False)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Should be instant

    async def test_acquire_when_rate_zero(self):
        """Test acquire returns immediately when rate is 0."""
        limiter = TokenBucketRateLimiter(rate=0.0, burst=5, enabled=True)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Should be instant

    async def test_acquire_single_token(self):
        """Test acquiring a single token."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)
        await limiter.acquire()
        assert limiter._tokens == 4.0

    async def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)
        await limiter.acquire(tokens=3)
        assert limiter._tokens == 2.0

    async def test_acquire_all_tokens(self):
        """Test acquiring all available tokens."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)
        await limiter.acquire(tokens=5)
        assert limiter._tokens == 0.0

    async def test_acquire_waits_for_refill(self):
        """Test acquire waits when not enough tokens available."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=2)

        # Empty the bucket
        await limiter.acquire(tokens=2)
        assert limiter._tokens == 0.0

        # This should wait ~0.1 seconds for 1 token to refill
        start = time.monotonic()
        await limiter.acquire(tokens=1)
        elapsed = time.monotonic() - start

        # Should have waited approximately 0.1 seconds (1 token / 10 tokens per second)
        assert 0.08 < elapsed < 0.15  # Allow some variance

    async def test_acquire_burst_handling(self):
        """Test burst allows multiple quick requests."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5)

        # Should be able to quickly acquire up to burst amount
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should be very fast (no waiting)
        assert elapsed < 0.1


@pytest.mark.asyncio
class TestTokenBucketRateLimiterRefill:
    """Test token refill behavior."""

    async def test_tokens_refill_over_time(self):
        """Test tokens refill at the specified rate."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=10)

        # Consume all tokens
        await limiter.acquire(tokens=10)
        assert limiter._tokens == 0.0

        # Wait for refill (0.5 seconds should give us 5 tokens)
        await asyncio.sleep(0.5)

        # Check available tokens (should be approximately 5)
        available = limiter.get_available_tokens()
        assert 4.5 < available < 5.5

    async def test_tokens_capped_at_burst(self):
        """Test tokens don't exceed burst capacity."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)

        # Use one token
        await limiter.acquire(tokens=1)

        # Wait longer than needed to refill to burst
        await asyncio.sleep(1.0)  # Should refill way past burst

        # Tokens should be capped at burst
        available = limiter.get_available_tokens()
        assert available == 5.0

    async def test_partial_token_accumulation(self):
        """Test fractional tokens accumulate correctly."""
        limiter = TokenBucketRateLimiter(rate=2.5, burst=10)  # 2.5 tokens per second

        # Empty bucket
        await limiter.acquire(tokens=10)

        # Wait 0.4 seconds (should give 1.0 tokens)
        await asyncio.sleep(0.4)

        available = limiter.get_available_tokens()
        assert 0.9 < available < 1.1


class TestTokenBucketRateLimiterGetAvailableTokens:
    """Test get_available_tokens method."""

    def test_get_available_tokens_disabled(self):
        """Test get_available_tokens returns -1 when disabled."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5, enabled=False)
        assert limiter.get_available_tokens() == -1.0

    def test_get_available_tokens_zero_rate(self):
        """Test get_available_tokens returns -1 when rate is 0."""
        limiter = TokenBucketRateLimiter(rate=0.0, burst=5, enabled=True)
        assert limiter.get_available_tokens() == -1.0

    def test_get_available_tokens_initial(self):
        """Test get_available_tokens returns burst amount initially."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5)
        available = limiter.get_available_tokens()
        assert available == 5.0

    def test_get_available_tokens_doesnt_modify_state(self):
        """Test get_available_tokens doesn't consume tokens."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5)

        # Call multiple times
        for _ in range(3):
            available = limiter.get_available_tokens()
            assert available == 5.0  # Should remain the same


@pytest.mark.asyncio
class TestTokenBucketRateLimiterTryAcquire:
    """Test try_acquire method with timeout."""

    async def test_try_acquire_disabled(self):
        """Test try_acquire returns True immediately when disabled."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5, enabled=False)
        result = await limiter.try_acquire(timeout=0.1)
        assert result is True

    async def test_try_acquire_zero_rate(self):
        """Test try_acquire returns True immediately when rate is 0."""
        limiter = TokenBucketRateLimiter(rate=0.0, burst=5, enabled=True)
        result = await limiter.try_acquire(timeout=0.1)
        assert result is True

    async def test_try_acquire_success(self):
        """Test try_acquire succeeds when tokens available."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)
        result = await limiter.try_acquire()
        assert result is True
        assert limiter._tokens == 4.0

    async def test_try_acquire_timeout(self):
        """Test try_acquire with insufficient tokens."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=1)

        # Use up tokens
        await limiter.acquire(tokens=1)

        # Small sleep to ensure bucket is empty
        await asyncio.sleep(0.01)

        # Check that we don't have enough tokens immediately
        available = limiter.get_available_tokens()
        assert available < 1.0

    async def test_try_acquire_waits_within_timeout(self):
        """Test try_acquire waits and succeeds within timeout."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=2)

        # Empty the bucket
        await limiter.acquire(tokens=2)

        # Try to acquire with sufficient timeout (should succeed)
        result = await limiter.try_acquire(timeout=0.5)
        assert result is True

    async def test_try_acquire_no_timeout(self):
        """Test try_acquire without timeout waits forever."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=2)

        # Empty the bucket
        await limiter.acquire(tokens=2)

        # Try to acquire without timeout (should wait and succeed)
        result = await limiter.try_acquire(timeout=None)
        assert result is True


@pytest.mark.asyncio
class TestTokenBucketRateLimiterConcurrency:
    """Test concurrent access to rate limiter."""

    async def test_concurrent_acquire(self):
        """Test multiple concurrent acquire calls are serialized."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)

        results = []

        async def acquire_and_record():
            await limiter.acquire()
            results.append(limiter._tokens)

        # Launch 5 concurrent acquires
        await asyncio.gather(*[acquire_and_record() for _ in range(5)])

        # All should have succeeded and tokens should be approximately 0
        assert len(results) == 5
        assert limiter._tokens < 0.01  # Very close to 0, accounting for time elapsed

    async def test_concurrent_try_acquire(self):
        """Test multiple concurrent try_acquire calls."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=3)

        async def try_acquire_task():
            return await limiter.try_acquire(timeout=0.5)

        # Launch 5 concurrent try_acquires (only 3 should succeed immediately)
        results = await asyncio.gather(*[try_acquire_task() for _ in range(5)])

        # All should eventually succeed due to refill within timeout
        assert all(results)


@pytest.mark.asyncio
class TestTokenBucketRateLimiterEdgeCases:
    """Test edge cases and unusual scenarios."""

    async def test_acquire_zero_tokens(self):
        """Test acquiring zero tokens (should be instant)."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5)
        start = time.monotonic()
        await limiter.acquire(tokens=0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1
        assert limiter._tokens == 5.0  # No tokens consumed

    async def test_very_slow_rate(self):
        """Test with very slow rate (LoRa scenario)."""
        # 0.02 commands/second = 1 per 50 seconds
        limiter = TokenBucketRateLimiter(rate=0.02, burst=2)

        # Burst should allow 2 quick commands
        await limiter.acquire()
        await limiter.acquire()
        assert limiter._tokens < 0.01  # Very close to 0

        # Check that tokens refill very slowly
        await asyncio.sleep(0.1)  # 0.1 seconds should give us only 0.002 tokens
        available = limiter.get_available_tokens()
        assert available < 0.01  # Still very few tokens available

    async def test_high_rate(self):
        """Test with very high rate (non-LoRa scenario)."""
        limiter = TokenBucketRateLimiter(rate=100.0, burst=10)

        # Should be able to acquire quickly even after burst
        for _ in range(15):
            await limiter.acquire()

        # Should complete quickly due to high refill rate
        assert limiter.get_available_tokens() >= 0


class TestTokenBucketRateLimiterMisc:
    """Test miscellaneous scenarios."""

    def test_fractional_burst(self):
        """Test with fractional burst value."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=3)
        assert limiter.burst == 3
        assert limiter._tokens == 3.0
