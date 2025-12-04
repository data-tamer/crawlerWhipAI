"""Advanced task dispatching and concurrency control."""

import logging
import asyncio
import psutil
from abc import ABC, abstractmethod
from typing import List, Callable, Coroutine, Any, Optional
from urllib.parse import urlparse

from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class BaseDispatcher(ABC):
    """Base class for task dispatchers."""

    @abstractmethod
    async def dispatch(
        self,
        tasks: List[Coroutine],
        per_domain_limiter: Optional[RateLimiter] = None,
    ) -> List[Any]:
        """Dispatch tasks.

        Args:
            tasks: List of coroutines to execute.
            per_domain_limiter: Optional rate limiter.

        Returns:
            Results from tasks.
        """
        pass


class SemaphoreDispatcher(BaseDispatcher):
    """Dispatcher using semaphore for concurrency control."""

    def __init__(
        self,
        semaphore_count: int = 5,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """Initialize dispatcher.

        Args:
            semaphore_count: Max concurrent tasks.
            rate_limiter: Optional rate limiter.
        """
        self.semaphore_count = semaphore_count
        self.rate_limiter = rate_limiter or RateLimiter()
        self.completed = 0
        self.failed = 0

    async def dispatch(
        self,
        tasks: List[Coroutine],
        per_domain_limiter: Optional[RateLimiter] = None,
    ) -> List[Any]:
        """Dispatch tasks with semaphore limiting.

        Args:
            tasks: List of coroutines.
            per_domain_limiter: Optional per-domain rate limiter.

        Returns:
            Results from tasks.
        """
        semaphore = asyncio.Semaphore(self.semaphore_count)

        async def sem_task(task):
            async with semaphore:
                return await task

        try:
            results = await asyncio.gather(
                *[sem_task(t) for t in tasks],
                return_exceptions=True
            )
            return results
        except Exception as e:
            logger.error(f"Dispatch error: {str(e)}")
            return []


class MemoryAdaptiveDispatcher(BaseDispatcher):
    """Dispatcher that adapts concurrency based on memory usage."""

    def __init__(
        self,
        base_concurrency: int = 5,
        memory_threshold_percent: float = 70.0,
        rate_limiter: Optional[RateLimiter] = None,
        check_interval: float = 1.0,
    ):
        """Initialize dispatcher.

        Args:
            base_concurrency: Initial concurrent tasks.
            memory_threshold_percent: Memory threshold to trigger throttling.
            rate_limiter: Optional rate limiter.
            check_interval: Memory check interval in seconds.
        """
        self.base_concurrency = base_concurrency
        self.memory_threshold_percent = memory_threshold_percent
        self.rate_limiter = rate_limiter or RateLimiter()
        self.check_interval = check_interval
        self.current_concurrency = base_concurrency

    async def dispatch(
        self,
        tasks: List[Coroutine],
        per_domain_limiter: Optional[RateLimiter] = None,
    ) -> List[Any]:
        """Dispatch tasks with memory-adaptive concurrency.

        Args:
            tasks: List of coroutines.
            per_domain_limiter: Optional per-domain rate limiter.

        Returns:
            Results from tasks.
        """
        semaphore = asyncio.Semaphore(self.current_concurrency)
        memory_monitor = asyncio.create_task(self._monitor_memory())

        try:
            async def sem_task(task):
                async with semaphore:
                    return await task

            results = await asyncio.gather(
                *[sem_task(t) for t in tasks],
                return_exceptions=True
            )
            return results
        finally:
            memory_monitor.cancel()

    async def _monitor_memory(self) -> None:
        """Monitor memory and adjust concurrency."""
        process = psutil.Process()

        while True:
            try:
                memory_percent = process.memory_percent()

                if memory_percent > self.memory_threshold_percent:
                    # Reduce concurrency
                    self.current_concurrency = max(1, self.current_concurrency - 1)
                    logger.warning(
                        f"Memory at {memory_percent:.1f}%, reducing concurrency to {self.current_concurrency}"
                    )
                elif memory_percent < (self.memory_threshold_percent * 0.5):
                    # Increase concurrency
                    if self.current_concurrency < self.base_concurrency:
                        self.current_concurrency = min(
                            self.base_concurrency,
                            self.current_concurrency + 1
                        )
                        logger.info(
                            f"Memory at {memory_percent:.1f}%, increasing concurrency to {self.current_concurrency}"
                        )

                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Memory monitoring error: {str(e)}")
                await asyncio.sleep(self.check_interval)


class DomainAwareDispatcher(BaseDispatcher):
    """Dispatcher with per-domain rate limiting."""

    def __init__(
        self,
        semaphore_count: int = 5,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """Initialize dispatcher.

        Args:
            semaphore_count: Max concurrent tasks.
            rate_limiter: Rate limiter instance.
        """
        self.semaphore_count = semaphore_count
        self.rate_limiter = rate_limiter or RateLimiter()

    async def dispatch_with_urls(
        self,
        url_tasks: List[tuple],  # (url, coroutine)
    ) -> List[Any]:
        """Dispatch tasks with per-domain rate limiting.

        Args:
            url_tasks: List of (url, coroutine) tuples.

        Returns:
            Results from tasks.
        """
        semaphore = asyncio.Semaphore(self.semaphore_count)

        async def rate_limited_task(url: str, task: Coroutine) -> Any:
            domain = urlparse(url).netloc.lower()

            # Wait for rate limit
            await self.rate_limiter.wait(domain)

            async with semaphore:
                try:
                    result = await task
                    self.rate_limiter.on_success(domain)
                    return result
                except Exception as e:
                    logger.error(f"Task failed for {url}: {str(e)}")
                    raise

        tasks = [rate_limited_task(url, task) for url, task in url_tasks]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        except Exception as e:
            logger.error(f"Dispatch error: {str(e)}")
            return []

    async def dispatch(
        self,
        tasks: List[Coroutine],
        per_domain_limiter: Optional[RateLimiter] = None,
    ) -> List[Any]:
        """Dispatch tasks (base method).

        Args:
            tasks: List of coroutines.
            per_domain_limiter: Ignored (uses internal limiter).

        Returns:
            Results from tasks.
        """
        semaphore = asyncio.Semaphore(self.semaphore_count)

        async def sem_task(task):
            async with semaphore:
                return await task

        try:
            results = await asyncio.gather(
                *[sem_task(t) for t in tasks],
                return_exceptions=True
            )
            return results
        except Exception as e:
            logger.error(f"Dispatch error: {str(e)}")
            return []
