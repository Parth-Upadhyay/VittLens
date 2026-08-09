"""
Resilience retry decorator with exponential backoff and jitter for synchronous and asynchronous calls.
"""

import asyncio
import functools
import random
import time
from typing import Any, Callable, Tuple, Type, Union

from core.logging import get_logger

logger = get_logger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator for retrying transient operations with exponential backoff.
    Supports both synchronous and asynchronous functions.

    Args:
        max_retries: Maximum number of retry attempts before raising exception
        initial_delay: Initial wait delay in seconds
        backoff_factor: Multiplicative factor for exponential growth
        jitter: If True, adds random jitter to prevent thundering herd
        retryable_exceptions: Tuple of Exception classes to catch and retry

    Returns:
        Callable decorator
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_exception: Union[Exception, None] = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exception = exc
                    if attempt == max_retries:
                        logger.error(
                            f"Operation '{func.__name__}' failed after {max_retries} attempts: {exc}"
                        )
                        raise

                    actual_delay = (
                        delay + random.uniform(0, delay * 0.5) if jitter else delay
                    )
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} for '{func.__name__}' failed: {exc}. Retrying in {actual_delay:.2f}s..."
                    )
                    time.sleep(actual_delay)
                    delay *= backoff_factor

            if last_exception:
                raise last_exception

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_exception: Union[Exception, None] = None

            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exception = exc
                    if attempt == max_retries:
                        logger.error(
                            f"Async operation '{func.__name__}' failed after {max_retries} attempts: {exc}"
                        )
                        raise

                    actual_delay = (
                        delay + random.uniform(0, delay * 0.5) if jitter else delay
                    )
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} for async '{func.__name__}' failed: {exc}. Retrying in {actual_delay:.2f}s..."
                    )
                    await asyncio.sleep(actual_delay)
                    delay *= backoff_factor

            if last_exception:
                raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
