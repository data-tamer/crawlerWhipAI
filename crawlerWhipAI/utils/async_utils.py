"""Async utilities and helpers."""

import asyncio
import logging
from typing import TypeVar, Callable, Coroutine, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout_seconds: float,
    default: T = None
) -> T:
    """Execute coroutine with timeout.

    Args:
        coro: Coroutine to execute.
        timeout_seconds: Timeout in seconds.
        default: Default value if timeout occurs.

    Returns:
        Result or default value.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {timeout_seconds}s")
        return default


async def gather_with_limit(
    coros: list,
    limit: int = 5,
    return_exceptions: bool = False
) -> list:
    """Gather coroutines with concurrency limit.

    Args:
        coros: List of coroutines.
        limit: Maximum concurrent tasks.
        return_exceptions: Whether to return exceptions.

    Returns:
        Results from coroutines.
    """
    semaphore = asyncio.Semaphore(limit)

    async def sem_coro(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(
        *[sem_coro(c) for c in coros],
        return_exceptions=return_exceptions
    )


async def retry_async(
    coro_func: Callable,
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs
) -> Any:
    """Retry async function with exponential backoff.

    Args:
        coro_func: Async function to call.
        max_retries: Maximum retry attempts.
        delay_seconds: Initial delay between retries.
        backoff_factor: Multiplier for delay on each retry.
        **kwargs: Arguments to pass to function.

    Returns:
        Result of function call.

    Raises:
        Exception: Last exception if all retries fail.
    """
    last_error = None
    current_delay = delay_seconds

    for attempt in range(max_retries):
        try:
            return await coro_func(**kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} failed: {str(e)}. "
                    f"Waiting {current_delay}s before retry..."
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff_factor
            else:
                logger.error(f"All {max_retries} retry attempts failed: {str(e)}")

    raise last_error
