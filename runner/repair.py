"""Repair mode: a hand-written test lost its keys; let Jev find the new ones.

When a Patrol test goes red because a key was renamed, run the same task with
Jev on the churned app, take the keys Jev actually acted on, and pair each key
the script uses with the one that replaced it. The output is a proposal for a
person to review, never a fix applied on its own.

The demo app renames by suffix, so pairing is by prefix; the ground truth comes
from the same hash `Store.renamed` uses, so every proposal can be scored.

    python3.13 repair.py --udid <simulator> --chaos 4 --flows return-flow \
        --out ../results/repair-seed4.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from agent import DEFAULT_VALUES, SCRIPTS, run_jev
from arms import TASKS
from transport import Marionette

import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e2e"))
from state_check import running_pid, vm_uri  # noqa: E402

FLOWS = ["return-flow", "cart-flow", "support-flow", "address-flow"]


def renamed(base: str, seed: int) -> bool:
    """`Store.renamed` in demo_app/lib/data.dart, line for line."""
    h = 0x811C9DC5
    for unit in f"{base}#{seed}".encode("utf-16-le")[::2]:
        h = ((h ^ unit) * 0x01000193) & 0x7FFFFFFF
    return h % 5 < 2


def suffix(seed: int) -> str:
    return f"_v{seed % 90 + 10}"


def script_keys(flow: str) -> list[str]:
    return list(dict.fromkeys(sel["key"] for _, sel, _ in SCRIPTS[flow] if "key" in sel))


def propose(flow: str, used: list[str]) -> dict:
    """Pair script keys with the keys Jev used in their place."""
    mapping, unmatched = {}, []
    for key in script_keys(flow):
        if key in used:
            continue
        candidates = [u for u in used if u.startswith(key + "_")]
        if candidates:
            mapping[key] = candidates[0]
        else:
            unmatched.append(key)
    known = set(script_keys(flow)) | set(mapping.values())
    extra = [u for u in dict.fromkeys(used) if u not in known]
    return {"mapping": mapping, "unmatched": unmatched, "extra": extra}


def score(flow: str, proposal: dict, seed: int) -> dict:
    truth = {k: k + suffix(seed) for k in script_keys(flow) if renamed(k, seed)}
    right = sum(1 for k, v in proposal["mapping"].items() if truth.get(k) == v)
    return {"renamed": len(truth), "proposed": len(proposal["mapping"]),
            "correct": right, "missed": sorted(set(truth) - set(proposal["mapping"]))}


def relaunch(udid: str) -> str:
    """A fresh process instead of a hot restart, which needs `flutter run`."""
    subprocess.run(["xcrun", "simctl", "terminate", udid, "dev.yii.boxtide"], capture_output=True)
    subprocess.run(["xcrun", "simctl", "launch", udid, "dev.yii.boxtide"], capture_output=True, check=True)
    for _ in range(30):
        try:
            return vm_uri(udid, running_pid(udid))
        except Exception:
            time.sleep(1)
    raise RuntimeError("app did not come back")


async def repair(udid: str, seed: int, max_steps: int, flows: list[str]) -> list[dict]:
    out = []
    for flow in flows:
        async with Marionette(relaunch(udid)) as app:
            await app.set_chaos(seed)
            report = await run_jev(app, TASKS[flow][0], dict(DEFAULT_VALUES), max_steps, False)
            state = await app.state()
            used = [str(t["target"]) for t in report.trace
                    if t.get("kind") in ("tap", "fill", "scroll") and t.get("target")]
            proposal = propose(flow, used)
            out.append({
                "flow": flow,
                "jev_verdict": report.verdict,
                "done": bool(TASKS[flow][1](state)),
                "steps": report.steps,
                "model_calls": report.usage.calls,
                "cost_usd": round(report.cost, 6),
                "wall_seconds": round(report.wall, 2),
                "used": used,
                **proposal,
                "score": score(flow, proposal, seed),
            })
            print(f"{flow}: {report.verdict}, done={out[-1]['done']}, "
                  f"mapping={proposal['mapping']}, extra={proposal['extra']}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--udid", required=True, help="simulator running a debug Boxtide build")
    p.add_argument("--flows", default=",".join(FLOWS))
    p.add_argument("--chaos", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=25)
    p.add_argument("--out")
    args = p.parse_args()
    results = asyncio.run(repair(args.udid, args.chaos, args.max_steps, args.flows.split(",")))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
