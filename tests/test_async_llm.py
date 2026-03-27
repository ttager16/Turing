from __future__ import annotations

import asyncio
import time
import unittest

from turing_takehome.llm import run_async_job_builders


class AsyncLLMHelpersTest(unittest.IsolatedAsyncioTestCase):
    async def test_results_map_back_when_jobs_finish_out_of_order(self) -> None:
        async def build(delay: float, value: str) -> str:
            await asyncio.sleep(delay)
            return value

        jobs = [
            ("slow", lambda: build(0.05, "first")),
            ("fast", lambda: build(0.01, "second")),
            ("mid", lambda: build(0.02, "third")),
        ]
        result = await run_async_job_builders(jobs, max_concurrency=3)
        self.assertEqual(
            result,
            {
                "slow": "first",
                "fast": "second",
                "mid": "third",
            },
        )

    async def test_concurrency_reduces_elapsed_time(self) -> None:
        async def build(delay: float, value: int) -> int:
            await asyncio.sleep(delay)
            return value

        jobs = [(str(index), (lambda index=index: build(0.05, index))) for index in range(6)]

        start_serial = time.perf_counter()
        await run_async_job_builders(jobs, max_concurrency=1)
        serial_elapsed = time.perf_counter() - start_serial

        start_parallel = time.perf_counter()
        await run_async_job_builders(jobs, max_concurrency=3)
        parallel_elapsed = time.perf_counter() - start_parallel

        self.assertGreater(serial_elapsed, 0.25)
        self.assertLess(parallel_elapsed, serial_elapsed * 0.6)


if __name__ == "__main__":
    unittest.main()
