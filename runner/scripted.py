#!/usr/bin/env python3.13
"""The hand-written baseline: same app, same transport, no model.

This exists so the Jev numbers mean something. Comparing Jev against patrol
would confound two variables at once — the decision layer AND the transport.
Here the transport is identical to `jev_agent.py`; the only difference is that
a human wrote the steps.

  python3.13 scripted.py --uri ws://127.0.0.1:8181/ws return-flow
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time

from jev_agent import Device

# Each step is (command, *args) passed straight to the marionette CLI.
FLOWS: dict[str, list[tuple[str, ...]]] = {
    "return-flow": [
        ("enter-text", "--key", "email_field", "--input", "demo@example.com"),
        ("enter-text", "--key", "password_field", "--input", "hunter2"),
        ("tap", "--key", "signin_button"),
        ("tap", "--key", "nav_orders"),
        ("tap", "--key", "order_5207"),
        ("tap", "--key", "start_return_button"),
        ("tap", "--key", "return_next_button"),
        ("tap", "--key", "return_next_button"),
        ("tap", "--key", "return_confirm"),
        ("tap", "--key", "return_next_button"),
    ],
    "browse-and-cart": [
        ("enter-text", "--key", "email_field", "--input", "demo@example.com"),
        ("enter-text", "--key", "password_field", "--input", "hunter2"),
        ("tap", "--key", "signin_button"),
        ("tap", "--key", "nav_shop"),
        ("tap", "--key", "product_p-speaker"),
        ("tap", "--key", "product_qty_plus"),
        ("tap", "--key", "add_to_cart_button"),
        ("tap", "--key", "view_cart_button"),
    ],
    "support-ticket": [
        ("enter-text", "--key", "email_field", "--input", "demo@example.com"),
        ("enter-text", "--key", "password_field", "--input", "hunter2"),
        ("tap", "--key", "signin_button"),
        ("tap", "--key", "nav_support"),
        ("tap", "--key", "contact_us_button"),
        ("enter-text", "--key", "contact_order_field", "--input", "5213"),
        ("enter-text", "--key", "contact_message_field",
         "--input", "My parcel has not moved in four days."),
        ("tap", "--key", "contact_send_button"),
    ],
}


def measure_overhead(device: Device, samples: int) -> list[float]:
    """How long a single marionette round trip costs.

    The CLI is stateless, so every call pays for a fresh process and a fresh
    VM service connection. If that dominates, the transport has to change.
    """
    timings = []
    for _ in range(samples):
        t0 = time.perf_counter()
        device.snapshot()
        timings.append(time.perf_counter() - t0)
    return timings


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("flow", choices=[*FLOWS, "overhead"])
    p.add_argument("--uri", required=True)
    p.add_argument("--samples", type=int, default=8)
    args = p.parse_args()

    device = Device(args.uri)

    if args.flow == "overhead":
        timings = measure_overhead(device, args.samples)
        print(f"marionette get-interactive-elements, {len(timings)} calls")
        print(f"  min    {min(timings) * 1000:7.0f}ms")
        print(f"  median {statistics.median(timings) * 1000:7.0f}ms")
        print(f"  max    {max(timings) * 1000:7.0f}ms")
        print(f"  mean   {statistics.mean(timings) * 1000:7.0f}ms")
        return 0

    steps = FLOWS[args.flow]
    print(f"flow: {args.flow} ({len(steps)} hand-written steps)")
    started = time.perf_counter()
    per_step = []
    for i, step in enumerate(steps, start=1):
        t0 = time.perf_counter()
        try:
            device._run(*step)
        except RuntimeError as err:
            print(f"  step {i}: FAILED {' '.join(step)}\n          {err}")
            return 1
        elapsed = time.perf_counter() - t0
        per_step.append(elapsed)
        print(f"  step {i}: {' '.join(step[:3]):48} {elapsed * 1000:6.0f}ms")

    total = time.perf_counter() - started
    print(f"\n  PASS")
    print(f"  steps {len(steps)} · model calls 0 · $0.0000")
    print(f"  wall {total:.2f}s  median step "
          f"{statistics.median(per_step) * 1000:.0f}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
