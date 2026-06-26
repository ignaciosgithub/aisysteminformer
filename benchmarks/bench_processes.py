"""Micro-benchmark for the process-collection hot path.

This is a manual, ad-hoc benchmark (not part of CI). It times the batched
``list_processes`` collector against a deliberately naive per-process approach
that issues separate ``psutil`` calls for each attribute, demonstrating why the
batched ``oneshot()`` strategy is used in :mod:`aisysteminformer.core.processes`.

Run with:

    python benchmarks/bench_processes.py [iterations]
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable

import psutil

from aisysteminformer.core import processes


def _naive_list() -> int:
    """Collect the same fields as ``list_processes`` but without batching.

    Each attribute is fetched with an individual call (no ``oneshot()``), which
    is what an unoptimised implementation typically does.
    """

    count = 0
    for proc in psutil.process_iter():
        try:
            _ = proc.pid
            _ = proc.ppid()
            _ = proc.name()
            _ = proc.username()
            _ = proc.status()
            _ = proc.cpu_percent()
            _ = proc.memory_info().rss
            _ = proc.memory_percent()
            _ = proc.num_threads()
            _ = proc.create_time()
            count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return count


def _time(label: str, fn: Callable[[], object], iterations: int) -> float:
    # Warm up caches so the first-call penalty is not attributed to either run.
    fn()
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start
    per_iter_ms = elapsed / iterations * 1e3
    print(f"{label:<28} {iterations} iters in {elapsed:6.3f}s  ({per_iter_ms:6.2f} ms/iter)")
    return elapsed


def main(argv: list[str]) -> int:
    iterations = int(argv[1]) if len(argv) > 1 else 20
    print(f"Benchmarking process collection over {iterations} iterations\n")

    batched = _time("batched (oneshot)", lambda: processes.list_processes(), iterations)
    naive = _time("naive (per-attribute)", _naive_list, iterations)

    if batched > 0:
        ratio = naive / batched
        faster, slower = ("batched", "naive") if batched < naive else ("naive", "batched")
        print(f"\n{faster} is {ratio if ratio >= 1 else 1 / ratio:.2f}x faster than {slower}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
