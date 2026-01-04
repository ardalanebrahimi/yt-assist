"""Async utilities for running blocking operations in thread pools."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar
from functools import partial

T = TypeVar("T")

# Default executor for I/O-bound operations
_executor: ThreadPoolExecutor | None = None


def get_executor(max_workers: int = 3) -> ThreadPoolExecutor:
    """Get or create the thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=max_workers)
    return _executor


async def run_in_thread(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Run a blocking function in a thread pool.

    This is useful for I/O-bound operations like API calls that would
    otherwise block the async event loop.

    Args:
        func: The blocking function to run
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the function call
    """
    loop = asyncio.get_event_loop()
    executor = get_executor()

    if kwargs:
        func = partial(func, **kwargs)

    return await loop.run_in_executor(executor, func, *args)


class ParallelProcessor:
    """
    Process items in parallel with progress tracking via async queue.

    This class handles running multiple blocking operations concurrently
    while providing real-time progress updates via an async queue.
    """

    def __init__(self, max_workers: int = 2):
        """
        Initialize the parallel processor.

        Args:
            max_workers: Maximum number of concurrent operations
        """
        self.max_workers = max_workers
        self.progress_queue: asyncio.Queue = asyncio.Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def process_items(
        self,
        items: list[Any],
        process_func: Callable[[Any], dict],
        item_id_func: Callable[[Any], str] = lambda x: str(x),
    ) -> dict:
        """
        Process items in parallel, yielding progress updates.

        Args:
            items: List of items to process
            process_func: Function to process each item (returns result dict)
            item_id_func: Function to get ID from item (for logging)

        Returns:
            Summary dict with completed/failed counts
        """
        loop = asyncio.get_event_loop()
        semaphore = asyncio.Semaphore(self.max_workers)

        results = {
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }

        async def process_with_semaphore(item, index):
            async with semaphore:
                try:
                    # Run blocking operation in thread
                    result = await loop.run_in_executor(
                        self.executor,
                        process_func,
                        item,
                    )

                    # Put progress update in queue
                    await self.progress_queue.put({
                        "index": index,
                        "item_id": item_id_func(item),
                        **result,
                    })

                    return result
                except Exception as e:
                    error_result = {
                        "status": "failed",
                        "message": str(e)[:100],
                    }
                    await self.progress_queue.put({
                        "index": index,
                        "item_id": item_id_func(item),
                        **error_result,
                    })
                    return error_result

        # Create tasks for all items
        tasks = [
            process_with_semaphore(item, i)
            for i, item in enumerate(items)
        ]

        # Run all tasks concurrently
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count results
        for result in all_results:
            if isinstance(result, Exception):
                results["failed"] += 1
            elif isinstance(result, dict):
                status = result.get("status", "failed")
                if status == "done":
                    results["completed"] += 1
                elif status == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1

        # Signal completion
        await self.progress_queue.put(None)

        return results

    def shutdown(self):
        """Shutdown the executor."""
        self.executor.shutdown(wait=False)
