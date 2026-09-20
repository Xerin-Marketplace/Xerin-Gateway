import asyncio
import time
import statistics
import argparse
from collections import Counter

import httpx


# ============================================================
# DEFAULT CONFIG
# ============================================================

DEFAULT_BASE_URL = "https://api.xerinmarketplace.com/api/v1"
DEFAULT_ENDPOINTS = (
    "/products",
    "/products/categories",
    "/advertisements",
) 

# 1000 requests per second
DEFAULT_RPS = 3000

# Each batch will generate for 1 second.
# At 1000 RPS this is approximately 1000 requests per batch.
DEFAULT_BATCH_DURATION = 1

# Keep repeating batches for 180 minutes
DEFAULT_TOTAL_MINUTES = 180

DEFAULT_TIMEOUT = 30

DEFAULT_MAX_IN_FLIGHT = 2000


# ============================================================
# MAIN REQUEST
# ============================================================


async def send_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    request_number: int,
    results: list,
    url: str,
):
    async with semaphore:
        start = time.perf_counter()

        try:
            response = await client.get(url)

            elapsed = time.perf_counter() - start

            results.append(
                {
                    "request": request_number,
                    "status": response.status_code,
                    "elapsed": elapsed,
                    "success": 200 <= response.status_code < 300,
                    "error": None,
                }
            )

        except Exception as exc:
            elapsed = time.perf_counter() - start

            results.append(
                {
                    "request": request_number,
                    "status": None,
                    "elapsed": elapsed,
                    "success": False,
                    "error": str(exc),
                }
            )


# ============================================================
# SINGLE BATCH
# ============================================================


async def run_batch(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    urls: list[str],
    rps: int,
    duration: int,
    batch_number: int,
):

    results = []

    tasks = []

    batch_start = time.perf_counter()

    interval = 1.0 / rps

    next_request_time = batch_start

    request_number = 0

    print()
    print("=" * 75)

    print(f"BATCH #{batch_number:,} STARTED")

    print("Targets:")
    for target_url in urls:
        print(f"  - {target_url}")

    print(f"Target RPS:         {rps:,}")

    print(f"Batch duration:     {duration}s")

    print(f"Expected requests:  {rps * duration:,}")

    print("=" * 75)

    # ========================================================
    # SAME FIXED-RATE LOOP AS YOUR ORIGINAL SCRIPT
    # ========================================================

    while True:
        now = time.perf_counter()

        if now - batch_start >= duration:
            break

        if next_request_time > now:
            await asyncio.sleep(next_request_time - now)

        request_number += 1

        task = asyncio.create_task(
            send_request(
                client,
                semaphore,
                request_number,
                results,
                urls[(request_number - 1) % len(urls)],
            )
        )

        tasks.append(task)

        next_request_time += interval

    print(f"Generated {request_number:,} requests.")

    print("Waiting for this batch to finish...")

    await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    batch_total_time = time.perf_counter() - batch_start

    # ========================================================
    # BATCH RESULTS
    # ========================================================

    successful = [r for r in results if r["success"]]

    failed = [r for r in results if not r["success"]]

    durations = [r["elapsed"] for r in results]

    print()
    print("-" * 75)

    print(f"BATCH #{batch_number:,} RESULTS")

    print("-" * 75)

    print(f"Requests generated:  {request_number:,}")

    print(f"Requests completed:  {len(results):,}")

    print(f"Successful:          {len(successful):,}")

    print(f"Failed:              {len(failed):,}")

    if results:
        success_rate = len(successful) / len(results) * 100

        print(f"Success rate:        {success_rate:.2f}%")

    if batch_total_time > 0:
        actual_rps = len(results) / batch_total_time

        print(f"Completed RPS:       {actual_rps:.2f}")

    if durations:
        durations_sorted = sorted(durations)

        def percentile(p):

            index = int(len(durations_sorted) * p)

            index = min(
                index,
                len(durations_sorted) - 1,
            )

            return durations_sorted[index] * 1000

        print(f"Average latency:     {statistics.mean(durations) * 1000:.2f} ms")

        print(f"P95 latency:         {percentile(0.95):.2f} ms")

        print(f"P99 latency:         {percentile(0.99):.2f} ms")

    # ========================================================
    # STATUS CODES
    # ========================================================

    statuses = Counter(
        r["status"] if r["status"] is not None else "NETWORK ERROR" for r in results
    )

    print()
    print("HTTP STATUS BREAKDOWN")

    for status, count in sorted(
        statuses.items(),
        key=lambda x: str(x[0]),
    ):
        print(f"{str(status):20} {count:,}")

    # ========================================================
    # SAMPLE ERRORS
    # ========================================================

    if failed:
        print()
        print("SAMPLE ERRORS")

        for result in failed[:10]:
            print(
                f"Request #{result['request']}: {result['error'] or result['status']}"
            )

    print()
    print(f"BATCH #{batch_number:,} FINISHED")

    print("=" * 75)

    return {
        "generated": request_number,
        "completed": len(results),
        "successful": len(successful),
        "failed": len(failed),
    }


# ============================================================
# CONTINUOUS 180-MINUTE TEST
# ============================================================


async def run_test(
    urls: list[str],
    rps: int,
    batch_duration: int,
    total_minutes: int,
    timeout: int,
    max_in_flight: int,
):

    total_seconds = total_minutes * 60

    print()
    print("=" * 75)
    print("XERIN MARKETPLACE CONTINUOUS LOAD TEST")
    print("=" * 75)

    print("Targets:")
    for target_url in urls:
        print(f"  - {target_url}")

    print(f"RPS:                {rps:,}")

    print(f"Requests per batch: approximately {rps * batch_duration:,}")

    print(f"Total test time:    {total_minutes} minutes")

    print(f"Max in-flight:      {max_in_flight:,}")

    print(f"Timeout:            {timeout}s")

    print()
    print(
        "The script will automatically start "
        "the next batch when the previous batch finishes."
    )

    print("=" * 75)

    limits = httpx.Limits(
        max_connections=max_in_flight,
        max_keepalive_connections=min(
            max_in_flight,
            1000,
        ),
    )

    timeout_config = httpx.Timeout(
        timeout,
        connect=10,
    )

    semaphore = asyncio.Semaphore(max_in_flight)

    test_start = time.perf_counter()

    batch_number = 0

    grand_generated = 0
    grand_completed = 0
    grand_successful = 0
    grand_failed = 0

    async with httpx.AsyncClient(
        limits=limits,
        timeout=timeout_config,
        follow_redirects=True,
    ) as client:
        # ====================================================
        # REPEAT UNTIL 180 MINUTES HAVE PASSED
        # ====================================================

        while True:
            elapsed = time.perf_counter() - test_start

            if elapsed >= total_seconds:
                break

            batch_number += 1

            batch = await run_batch(
                client=client,
                semaphore=semaphore,
                urls=urls,
                rps=rps,
                duration=batch_duration,
                batch_number=batch_number,
            )

            grand_generated += batch["generated"]

            grand_completed += batch["completed"]

            grand_successful += batch["successful"]

            grand_failed += batch["failed"]

            elapsed = time.perf_counter() - test_start

            remaining = max(
                total_seconds - elapsed,
                0,
            )

            print()
            print("STARTING NEXT BATCH...")

            print(f"Test elapsed: {elapsed / 60:.2f} minutes")

            print(f"Remaining: {remaining / 60:.2f} minutes")

            print()

    # ========================================================
    # FINAL 180-MINUTE RESULT
    # ========================================================

    total_elapsed = time.perf_counter() - test_start

    print()
    print("=" * 75)
    print("FINAL TEST RESULTS")
    print("=" * 75)

    print(f"Total batches:        {batch_number:,}")

    print(f"Total generated:      {grand_generated:,}")

    print(f"Total completed:      {grand_completed:,}")

    print(f"Total successful:     {grand_successful:,}")

    print(f"Total failed:         {grand_failed:,}")

    if grand_completed:
        success_rate = grand_successful / grand_completed * 100

        print(f"Overall success rate: {success_rate:.2f}%")

    print(f"Total runtime:        {total_elapsed / 60:.2f} minutes")

    print()
    print("=" * 75)
    print("LOAD TEST FINISHED")
    print("=" * 75)


# ============================================================
# CLI
# ============================================================


def main():

    parser = argparse.ArgumentParser(
        description=("Xerin Marketplace continuous fixed-RPS load test")
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
    )

    parser.add_argument(
        "--endpoints",
        nargs="+",
        default=list(DEFAULT_ENDPOINTS),
    )

    parser.add_argument(
        "--rps",
        type=int,
        default=DEFAULT_RPS,
    )

    parser.add_argument(
        "--batch-duration",
        type=int,
        default=DEFAULT_BATCH_DURATION,
    )

    parser.add_argument(
        "--total-minutes",
        type=int,
        default=DEFAULT_TOTAL_MINUTES,
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
    )

    parser.add_argument(
        "--max-in-flight",
        type=int,
        default=DEFAULT_MAX_IN_FLIGHT,
    )

    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    urls = [f"{base_url}/{endpoint.lstrip('/')}" for endpoint in args.endpoints]

    if args.rps <= 0:
        raise SystemExit("RPS must be greater than 0.")

    if args.batch_duration <= 0:
        raise SystemExit("Batch duration must be greater than 0.")

    if args.total_minutes <= 0:
        raise SystemExit("Total minutes must be greater than 0.")

    asyncio.run(
        run_test(
            urls=urls,
            rps=args.rps,
            batch_duration=args.batch_duration,
            total_minutes=args.total_minutes,
            timeout=args.timeout,
            max_in_flight=args.max_in_flight,
        )
    )


if __name__ == "__main__":
    main()
