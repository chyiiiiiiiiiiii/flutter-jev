"""Turn the e2e matrix into one table: e2e's verdict next to the store's.

Reads results/e2e/report-<label>.json and store-<label>.jsonl for every label
the matrix wrote, and prints one row per run plus the cache reasons seen.

    python3 summarize.py [--md ../results/e2e/summary.md]
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results" / "e2e"

# Same published rates the runner uses (runner/llm.py, runner/jev.py).
PRICES = {
    "gemini-3.1-flash-lite": (0.25 / 1e6, 1.50 / 1e6),
    "jev": (0.042 / 1e6, 0.0),
}


def price(model: str, tokens_in: int, tokens_out: int) -> float:
    for name, (pin, pout) in PRICES.items():
        if name in model:
            return tokens_in * pin + tokens_out * pout
    return 0.0


def store_verdicts(label: str) -> dict[str, bool | None]:
    path = RESULTS / f"store-{label}.jsonl"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["flow"]] = rec.get("done")
    return out


def summarize(label: str) -> dict:
    report = json.loads((RESULTS / f"report-{label}.json").read_text())
    store = store_verdicts(label)
    row = collections.Counter()
    reasons = collections.Counter()
    locations = set()
    flows = {}
    cost = 0.0
    for res in report["run"]["results"]:
        if res["status"] == "skipped" or not res.get("attempts"):
            continue
        flow = res["titlePath"][-1]
        attempt = res["attempts"][-1]
        row["tests"] += 1
        row["passed"] += res["status"] == "passed"
        row["ms"] += attempt["durationMs"]
        flows[flow] = (res["status"], store.get(flow))
        for step in attempt["steps"]:
            if step.get("kind") != "agent":
                continue
            row["agent_steps"] += 1
            row["calls"] += (step.get("metrics") or {}).get("modelCalls", 0)
            models = step.get("model")
            for m in models if isinstance(models, list) else [models] if models else []:
                tin, tout = m.get("inputTokens", 0), m.get("outputTokens", 0)
                row["tokens"] += tin + tout
                cost += price(m.get("model", ""), tin, tout)
            cache = step.get("cache") or {}
            if cache:
                row[f"cache_{cache.get('mode')}"] += 1
                if cache.get("reason"):
                    reasons[cache["reason"]] += 1
            loc = (step.get("screen") or {}).get("location")
            if loc:
                locations.add(loc)
    row["store_done"] = sum(1 for _, done in flows.values() if done)
    row["false_pass"] = sum(1 for st, done in flows.values() if st == "passed" and done is False)
    return {"label": label, **row, "cost": cost, "reasons": dict(reasons),
            "locations": sorted(locations), "flows": flows}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--md")
    args = p.parse_args()
    labels = sorted(f.stem.removeprefix("report-") for f in RESULTS.glob("report-*.json")
                    if not f.stem.startswith("report-smoke"))
    order = {"normal": 0, "chaos": 1}
    labels.sort(key=lambda l: (order.get(l.split("-")[0], 9), l.split("-")[1], l))
    lines = ["| run | e2e passed | store done | false pass | wall s | agent steps | model calls | tokens | $ | replayed | handed off | missed |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    all_reasons = collections.Counter()
    all_locations = set()
    for label in labels:
        s = summarize(label)
        all_reasons.update(s["reasons"])
        all_locations.update(s["locations"])
        lines.append(
            f"| {label} | {s.get('passed', 0)}/{s.get('tests', 0)} | {s['store_done']}/{s.get('tests', 0)} | {s['false_pass']} "
            f"| {s.get('ms', 0) / 1000:.1f} | {s.get('agent_steps', 0)} | {s.get('calls', 0)} | {s.get('tokens', 0):,} | {s['cost']:.4f} "
            f"| {s.get('cache_self-finalized', 0)} | {s.get('cache_agent-concluded', 0)} | {s.get('cache_missed', 0)} |")
    lines += ["", f"cache reasons: {dict(all_reasons)}", f"screen locations seen: {sorted(all_locations)}"]
    text = "\n".join(lines)
    print(text)
    if args.md:
        Path(args.md).write_text(text + "\n")


if __name__ == "__main__":
    main()
