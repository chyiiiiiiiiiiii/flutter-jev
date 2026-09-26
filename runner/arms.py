#!/usr/bin/env python3.13
"""Who should decide, and who should write: five ways to run the same tasks.

  scripted     the hand-written test, where one exists
  jev          Jev picks, text comes from the hand-written value table
  lite         Gemini flash-lite picks, same table (isolates the decider)
  lite-free    Gemini flash-lite picks and writes its own text (pure LLM)
  pro-free     Gemini Pro, reasoning on, picks and writes (pure frontier LLM)
  hybrid       Jev picks, flash-lite writes the text; no table at all
  hybrid-v2    the same, with a writer told to invent a required value

Every run is judged twice: by the agent's own verdict, and by reading the
app's store afterwards. The gap between the two is the number that matters
most, because a test that says "pass" when nothing happened is worse than one
that fails.

Two tasks ask for details the value table does not hold (a Home address, a
different order number). They are there to find out what the table costs.

  python3.13 arms.py --uri ws://127.0.0.1:PORT/xxx=/ws --repeats 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from agent import DEFAULT_VALUES, SCRIPTS, run_jev, run_scripted
from llm import WRITER_BRIEF_V2, GeminiDecider, GeminiWriter
from transport import Marionette

Check = Callable[[dict[str, Any]], bool]

TASKS: dict[str, tuple[str, Check, bool]] = {
    # name: (sentence, did it really happen, is it covered by the value table)
    "return-flow": (
        "sign in with the demo account, open order 5207, and submit a return "
        "request for it",
        lambda s: s["orders"].get("5207") == "returning", True),
    "cart-flow": (
        "sign in with the demo account, then add the pocket speaker to the "
        "cart and open the cart",
        lambda s: s["cart"].get("p-speaker", 0) >= 1, True),
    "support-flow": (
        "sign in with the demo account, then contact support about order 5213 "
        "not moving",
        lambda s: any("5213" in t["order"] for t in s["tickets"]), True),
    "address-flow": (
        "sign in with the demo account, then add a new saved delivery address "
        "labelled Office",
        lambda s: any(a["label"].strip().lower() == "office"
                      for a in s["addresses"]), True),
    "address-home": (
        "sign in with the demo account, then add a new saved delivery address "
        "labelled Home at 5F, 12 Zhongshan Rd",
        lambda s: any(a["label"].strip().lower() == "home"
                      and "zhongshan" in a["lines"].lower()
                      for a in s["addresses"]), False),
    "support-damaged": (
        "sign in with the demo account, then contact support saying order 5198 "
        "arrived damaged",
        lambda s: any("5198" in t["order"] and "damag" in t["message"].lower()
                      for t in s["tickets"]), False),
}

# The sign-in fields are needed by every task and are the same account every
# time, so the hybrid and free arms get them told in the sentence already.
ARMS = ["scripted", "jev", "lite", "lite-free", "pro-free", "hybrid",
        "hybrid-v2"]

LITE = "gemini-3.1-flash-lite"
PRO = "gemini-3.1-pro-preview"
SIGNIN = " (demo account: demo@example.com, password hunter2)"


async def one_run(uri: str, arm: str, name: str,
                  chaos: int = 0) -> dict[str, Any] | None:
    sentence, check, _ = TASKS[name]
    # macOS stops producing frames for a window that is fully covered, so the
    # screen after any navigation never builds and reads as empty. Every
    # setup fails identically when that happens, which looks like a model
    # result and is not one.
    await asyncio.create_subprocess_exec(
        "osascript", "-e", 'tell application "System Events" to set '
        'frontmost of application process "boxtide" to true')
    await asyncio.sleep(0.5)
    async with Marionette(uri) as app:
        await app.hot_restart()
        await asyncio.sleep(2.5)
        # A restart resets the store, chaos included, so churn goes on after.
        if chaos:
            await app.set_chaos(chaos)
            await asyncio.sleep(0.6)
        if arm == "scripted":
            if name not in SCRIPTS:
                return None
            report = await run_scripted(app, name)
        elif arm == "jev":
            report = await run_jev(app, sentence, DEFAULT_VALUES, 25, False,
                                   mode=arm)
        elif arm == "lite":
            report = await run_jev(app, sentence, DEFAULT_VALUES, 25, False,
                                   decider=GeminiDecider(LITE, False, False),
                                   mode=arm)
        elif arm == "lite-free":
            report = await run_jev(app, sentence + SIGNIN, {}, 25, False,
                                   decider=GeminiDecider(LITE, False, True),
                                   free_text=True, mode=arm)
        elif arm == "pro-free":
            report = await run_jev(app, sentence + SIGNIN, {}, 25, False,
                                   decider=GeminiDecider(PRO, True, True),
                                   free_text=True, mode=arm)
        elif arm == "hybrid":
            async with GeminiWriter(LITE) as writer:
                report = await run_jev(app, sentence + SIGNIN, {}, 25, False,
                                       writer=writer, mode=arm)
        elif arm == "hybrid-v2":
            async with GeminiWriter(LITE, WRITER_BRIEF_V2) as writer:
                report = await run_jev(app, sentence + SIGNIN, {}, 25, False,
                                       writer=writer, mode=arm)
        else:
            raise ValueError(arm)
        await asyncio.sleep(0.4)
        state = await app.state()
    row = report.to_json()
    row["task"] = name
    row["arm"] = arm
    row["chaos"] = chaos
    row["claimed"] = report.verdict == "pass"
    row["real"] = bool(check(state))
    row["state"] = state
    return row


def pct(n: int, d: int) -> str:
    return f"{n}/{d}" if d else "—"


def table(rows: list[dict[str, Any]]) -> str:
    out = [
        "| task | arm | runs | really done | claimed pass | false pass | "
        "median steps | median wall | median $/run | median decision | retries |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in TASKS:
        for arm in ARMS:
            runs = [r for r in rows if r["task"] == name and r["arm"] == arm]
            if not runs:
                continue
            real = sum(r["real"] for r in runs)
            claimed = sum(r["claimed"] for r in runs)
            false = sum(r["claimed"] and not r["real"] for r in runs)
            med = lambda k: statistics.median(float(r.get(k) or 0) for r in runs)
            dec = [float(r["median_decision_ms"]) for r in runs
                   if r.get("median_decision_ms")]
            out.append(
                f"| {name} | {arm} | {len(runs)} | {pct(real, len(runs))} | "
                f"{pct(claimed, len(runs))} | {false} | {med('steps'):.0f} | "
                f"{med('wall_seconds'):.1f}s | ${med('cost_usd'):.5f} | "
                f"{(statistics.median(dec) if dec else 0):.0f}ms | "
                f"{sum(int(r.get('retries') or 0) for r in runs)} |")
    return "\n".join(out)


def rollup(rows: list[dict[str, Any]]) -> str:
    out = [
        "| arm | runs | really done | false pass | median wall | "
        "mean $/run | median decision |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm in ARMS:
        runs = [r for r in rows if r["arm"] == arm]
        if not runs:
            continue
        real = sum(r["real"] for r in runs)
        false = sum(r["claimed"] and not r["real"] for r in runs)
        dec = [float(r["median_decision_ms"]) for r in runs
               if r.get("median_decision_ms")]
        out.append(
            f"| {arm} | {len(runs)} | {pct(real, len(runs))} | {false} | "
            f"{statistics.median(float(r['wall_seconds']) for r in runs):.1f}s | "
            f"${statistics.mean(float(r['cost_usd']) for r in runs):.5f} | "
            f"{(statistics.median(dec) if dec else 0):.0f}ms |")
    return "\n".join(out)


def churn_table(rows: list[dict[str, Any]]) -> str:
    """Really-done counts per churn seed, so a seed that breaks one arm shows."""
    seeds = sorted({r.get("chaos", 0) for r in rows})
    arms = [a for a in ARMS if any(r["arm"] == a for r in rows)]
    out = ["| arm | " + " | ".join(f"seed {s}" for s in seeds) +
           " | total | false pass | empty reads |",
           "|---|" + "---|" * (len(seeds) + 3)]
    for arm in arms:
        runs = [r for r in rows if r["arm"] == arm]
        cells = []
        for seed in seeds:
            rs = [r for r in runs if r.get("chaos", 0) == seed]
            cells.append(pct(sum(r["real"] for r in rs), len(rs)))
        out.append(f"| {arm} | " + " | ".join(cells) +
                   f" | {pct(sum(r['real'] for r in runs), len(runs))} | "
                   f"{sum(r['claimed'] and not r['real'] for r in runs)} | "
                   f"{sum(int(r.get('empty_reads') or 0) for r in runs)} |")
    return "\n".join(out)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri", required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--arms", nargs="*", default=ARMS)
    p.add_argument("--tasks", nargs="*", default=list(TASKS))
    p.add_argument("--chaos", nargs="*", type=int, default=[0],
                   help="churn seeds to run under; 0 is the app as written")
    p.add_argument("--out-dir", default="../results")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw_path = out_dir / f"arms-runs-{stamp}.json"
    rows: list[dict[str, Any]] = []
    for name in args.tasks:
      for seed in args.chaos:
        for arm in args.arms:
            for attempt in range(1, args.repeats + 1):
                print(f"\n===== {name} · seed {seed} · {arm} · run {attempt} =====")
                try:
                    row = await one_run(args.uri, arm, name, seed)
                except Exception as err:  # a crash is a data point
                    print(f"  run raised: {type(err).__name__}: {err}")
                    row = {"task": name, "arm": arm, "chaos": seed,
                           "verdict": "error",
                           "claimed": False, "real": False, "steps": 0,
                           "wall_seconds": 0.0, "cost_usd": 0.0,
                           "median_decision_ms": None, "retries": 0,
                           "error": str(err)[:300]}
                if row is None:
                    break
                print(f"  claimed {row['claimed']} · really done {row['real']}")
                rows.append(row)
                # Written as it goes, so a long run that dies keeps its data.
                raw_path.write_text(json.dumps(rows, indent=2))

    rendered = ("## By task\n\n" + table(rows) + "\n\n## By arm\n\n"
                + rollup(rows) + "\n")
    if any(r.get("chaos") for r in rows):
        rendered += "\n## Under churn, by seed\n\n" + churn_table(rows) + "\n"
    (out_dir / f"arms-{stamp}.md").write_text(rendered)
    print("\n" + rendered)
    print(f"wrote {raw_path} and arms-{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
