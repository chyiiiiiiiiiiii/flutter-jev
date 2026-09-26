#!/usr/bin/env python3.13
"""Run every flow in both modes, repeatedly, and write the comparison.

The point of running each one several times is that a single green run proves
very little about an agent loop. What matters is whether it lands on the same
answer twice, and what it costs when it does.

  python3.13 compare.py --uri ws://127.0.0.1:53954/x=/ws --repeats 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path

from agent import DEFAULT_VALUES, SCRIPTS, run_jev, run_scripted
from transport import Marionette

# Each flow has a hand-written script and the sentence a person would say
# instead. Same destination, two ways of asking.
FLOWS = {
    "return-flow": "sign in with the demo account, open order 5207, and submit "
                   "a return request for it",
    "cart-flow": "sign in with the demo account, then add the pocket "
                 "speaker to the cart and open the cart",
    "support-flow": "sign in with the demo account, then contact support about "
                    "order 5213 not moving",
    "address-flow": "sign in with the demo account, then add a new saved "
                    "delivery address labelled Office",
}


async def one_run(uri: str, mode: str, flow: str) -> dict[str, object]:
    # A covered macOS window stops rendering; see arms.one_run.
    await asyncio.create_subprocess_exec(
        "osascript", "-e", 'tell application "System Events" to set '
        'frontmost of application process "boxtide" to true')
    await asyncio.sleep(0.5)
    async with Marionette(uri) as app:
        await app.hot_restart()
        await asyncio.sleep(2.5)
        if mode == "scripted":
            report = await run_scripted(app, flow)
        else:
            report = await run_jev(app, FLOWS[flow], DEFAULT_VALUES, 25, False)
    return report.to_json()


def table(rows: list[dict[str, object]]) -> str:
    """Group runs by mode and flow and render the comparison."""
    out = [
        "| flow | mode | runs | passed | steps | model calls | tokens | "
        "cost | wall | median decision |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for flow in FLOWS:
        for mode in ("scripted", "jev"):
            runs = [r for r in rows
                    if r["label"] in (flow, FLOWS[flow]) and r["mode"] == mode]
            if not runs:
                continue
            passed = sum(1 for r in runs if r["verdict"] == "pass")
            steps = statistics.median(float(r["steps"]) for r in runs)
            calls = statistics.median(float(r["model_calls"]) for r in runs)
            tokens = statistics.median(float(r["input_tokens"]) for r in runs)
            cost = statistics.median(float(r["cost_usd"]) for r in runs)
            wall = statistics.median(float(r["wall_seconds"]) for r in runs)
            decisions = [float(r["median_decision_ms"]) for r in runs
                         if r["median_decision_ms"]]
            dec = f"{statistics.median(decisions):.0f}ms" if decisions else "—"
            out.append(
                f"| {flow} | {mode} | {len(runs)} | {passed}/{len(runs)} | "
                f"{steps:.0f} | {calls:.0f} | {tokens:.0f} | "
                f"${cost:.4f} | {wall:.1f}s | {dec} |")
    return "\n".join(out)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri", required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--flows", nargs="*", default=list(FLOWS))
    p.add_argument("--out-dir", default="../results")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for flow in args.flows:
        if flow not in SCRIPTS:
            print(f"skipping unknown flow {flow}")
            continue
        for mode in ("scripted", "jev"):
            for attempt in range(1, args.repeats + 1):
                print(f"\n===== {flow} · {mode} · run {attempt} =====")
                try:
                    rows.append(await one_run(args.uri, mode, flow))
                except Exception as err:  # keep going; a crash is a data point
                    print(f"  run raised: {type(err).__name__}: {err}")
                    rows.append({
                        "mode": mode, "label": flow, "verdict": "error",
                        "steps": 0, "model_calls": 0, "input_tokens": 0,
                        "output_tokens": 0, "cost_usd": 0.0,
                        "wall_seconds": 0.0, "model_seconds": 0.0,
                        "transport_seconds": 0.0, "transport_calls": 0,
                        "median_decision_ms": None, "raw_chars": 0,
                        "compact_chars": 0, "error": str(err)[:300],
                    })

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (out_dir / f"runs-{stamp}.json").write_text(json.dumps(rows, indent=2))
    rendered = table(rows)
    (out_dir / f"comparison-{stamp}.md").write_text(rendered + "\n")
    print("\n" + rendered)
    print(f"\nwrote {out_dir}/runs-{stamp}.json and comparison-{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
