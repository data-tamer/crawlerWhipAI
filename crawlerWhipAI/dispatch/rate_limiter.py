"""Rate limiting with exponential backoff."""

import logging
import asyncio
import time
from typing import Dict, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimiter:
    """Domain-aware rate limiting with exponential backoff."""

    def __init__(
        self,
        base_delay: Tuple[float, float] = (1.0, 3.0),
        max_delay: float = 60.0,
        max_retries: int = 3,
    ):
        """Initialize rate limiter.

        Args:
            base_delay: (min, max) seconds for random base delay.
            max_delay: Maximum backoff delay in seconds.
            max_retries: Max retries on rate limit (429/503).
        """
        self.base_delay_min, self.base_delay_max = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries

        # Per-domain state
        self.domain_delays: Dict[str, float] = {}
        self.last_request: Dict[str, float] = {}
        self.failure_counts: Dict[str, int] = {}

    async def wait(self, domain: str) -> None:
        """Wait appropriate time before making request to domain.

        Args:
            domain: Domain to rate limit.
        """
        # Get current delay for domain
        current_delay = self.domain_delays.get(domain, self.base_delay_min)

        # Check last request time
        last_time = self.last_request.get(domain, 0)
        time_since_last = time.time() - last_time

        # Wait if needed
        if time_since_last < current_delay:
            wait_time = current_delay - time_since_last
            logger.debug(f"Rate limiting {domain}: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        # Update last request time
        self.last_request[domain] = time.time()

    def on_success(self, domain: str) -> None:
        """Record successful request - reduce delay.

        Args:
            domain: Domain that succeeded.
        """
        current_delay = self.domain_delays.get(domain, self.base_delay_min)

        # Gradually reduce delay on success
        new_delay = max(self.base_delay_min, current_delay * 0.75)
        self.domain_delays[domain] = new_delay

        # Reset failure count
        self.failure_counts[domain] = 0

    def on_rate_limited(self, domain: str) -> int:
        """Record rate limit (429/503) - increase delay.

        Args:
            domain: Domain that rate limited.

        Returns:
            Retry count for this domain.
        """
        current_delay = self.domain_delays.get(domain, self.base_delay_min)
        failure_count = self.failure_counts.get(domain, 0) + 1

        # Exponential backoff with jitter
        import random
        new_delay = min(
            current_delay * 2 * random.uniform(0.75, 1.25),
            self.max_delay
        )
        self.domain_delays[domain] = new_delay
        self.failure_counts[domain] = failure_count

        logger.warning(
            f"Rate limited on {domain}: "
            f"new delay {new_delay:.2f}s, attempt {failure_count}/{self.max_retries}"
        )

        return failure_count

    def should_retry(self, domain: str, failure_count: int) -> bool:
        """Check if should retry after rate limit.

        Args:
            domain: Domain that failed.
            failure_count: Number of failures so far.

        Returns:
            True if should retry.
        """
        return failure_count < self.max_retries

    def reset_domain(self, domain: str) -> None:
        """Reset rate limiting state for a domain.

        Args:
            domain: Domain to reset.
        """
        if domain in self.domain_delays:
            del self.domain_delays[domain]
        if domain in self.last_request:
            del self.last_request[domain]
        if domain in self.failure_counts:
            del self.failure_counts[domain]
        logger.debug(f"Reset rate limiter for {domain}")

    def reset_all(self) -> None:
        """Reset all rate limiting state."""
        self.domain_delays.clear()
        self.last_request.clear()
        self.failure_counts.clear()
        logger.info("Reset all rate limiters")

    def get_stats(self) -> Dict:
        """Get current rate limiting statistics.

        Returns:
            Dictionary with stats per domain.
        """
        return {
            domain: {
                "current_delay": self.domain_delays.get(domain, self.base_delay_min),
                "failures": self.failure_counts.get(domain, 0),
                "last_request": datetime.fromtimestamp(
                    self.last_request.get(domain, 0)
                ).isoformat() if domain in self.last_request else None,
            }
            for domain in set(
                list(self.domain_delays.keys()) +
                list(self.failure_counts.keys())
            )
        }
