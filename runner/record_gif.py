#!/usr/bin/env python3.13
"""Record one real run of the hybrid setup and turn it into a captioned GIF.

Each step's frame is the app's own screenshot taken after that step, under a
caption saying who acted: Jev picking an action, or the LLM writing the words
that went into a field. The clock and cost come from the run's own trace, with
the time spent taking screenshots taken back out.

  python3.13 record_gif.py --uri ws://... --lang en --out-dir ../results/media --name hybrid-run-en

Frames and the sequence spec stay beside the GIF, so a caption fix is a
re-render rather than a re-recording:

  python3.13 render_sequence.py ../results/media/hybrid-run-en/sequence.json --out-dir ../results/media
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import render_sequence
from agent import run_jev
from arms import LITE, SIGNIN, TASKS
from llm import WRITER_BRIEF_V2, GeminiWriter
from transport import Marionette

TEXT = {
    "zh": {"eyebrow": "實測錄影 · Jev 挑每一步，LLM 只寫字 · 任務：回報訂單 5198 到貨損壞",
           "jev": "Jev 挑", "judge": "Jev 判斷", "llm": "LLM 寫", "tap": "點 `{t}`", "scroll": "往下捲",
           "pass": "回報：做完了", "fail": "回報：做不到", "fill": "「{x}」→ `{t}`",
           "conf": "信心 {c:.2f}", "fillmeta": "Jev 選了這一步（信心 {c:.2f}），要填的字由 LLM 看畫面寫",
           "start": "開始：一句話的任務，沒有腳本", "sec": "{v:.1f} 秒",
           "done": "app 裡實際寫進 ✓", "notdone": "app 裡沒有寫進正確的資料 ✗",
           "ticket": "訂單 {o}：「{m}」", "none": "沒有送出任何東西", "steps": "{n} 步 · ${c:.4f}",
           "alt": "一次實際的跑：Jev 挑動作、LLM 寫字，{n} 步、{w:.1f} 秒、${c:.4f}，app 收到訂單 5198 的客服單"},
    "en": {"eyebrow": "One recorded run · Jev picks every step, an LLM only writes · Task: report order 5198 arrived damaged",
           "jev": "Jev picks", "judge": "Jev judges", "llm": "LLM writes", "tap": "tap `{t}`", "scroll": "scroll down",
           "pass": "report: done", "fail": "report: cannot do it", "fill": "“{x}” → `{t}`",
           "conf": "confidence {c:.2f}",
           "fillmeta": "Jev chose this step (confidence {c:.2f}); the LLM wrote the words from the screen",
           "start": "Start: a one-sentence task, no script", "sec": "{v:.1f} s",
           "done": "What the app actually stored ✓", "notdone": "The app did not store the right thing ✗",
           "ticket": "order {o}: “{m}”", "none": "nothing was sent", "steps": "{n} steps · ${c:.4f}",
           "alt": "One recorded run: Jev picks the actions, an LLM writes the text, {n} steps, {w:.1f} s, "
                  "${c:.4f}; the app received the ticket for order 5198"},
}


def caption(T: dict, s: dict) -> dict:
    """Who did this step, and what it was."""
    if s["kind"] == "fill":
        return {"tag": T["llm"], "tagStyle": "outline", "line": T["fill"].format(x=s["typed"], t=s["target"]),
                "meta": T["fillmeta"].format(c=s["conf"])}
    if s["kind"] == "finish":
        return {"tag": T["judge"], "line": T["pass" if s["verdict"] == "pass" else "fail"],
                "meta": T["conf"].format(c=s["conf"])}
    line = T["scroll"] if s["kind"] == "scroll" else T["tap"].format(t=s["target"])
    return {"tag": T["jev"], "line": line, "meta": T["conf"].format(c=s["conf"])}


async def record(uri: str, task: str, frames: Path) -> tuple[list[dict], dict]:
    sentence, check, _ = TASKS[task]
    await asyncio.create_subprocess_exec(
        "osascript", "-e", 'tell application "System Events" to set frontmost of application process "boxtide" to true')
    await asyncio.sleep(0.5)
    shots: list[dict] = []
    async with Marionette(uri) as app:
        await app.hot_restart()
        await asyncio.sleep(2.5)
        start_png = frames / "00.png"
        await app.screenshot(str(start_png))
        overhead = 0.0

        async def on_step(step, action, decision, typed):
            nonlocal overhead
            t0 = time.perf_counter()
            await asyncio.sleep(1.0)  # let page transitions finish so the frame shows the result
            png = frames / f"{step:02d}.png"
            await app.screenshot(str(png))
            shots.append({"step": step, "kind": action.kind,
                          "target": (action.element.key if action.element else action.id) or "",
                          "typed": typed, "verdict": action.verdict, "conf": decision.confidence,
                          "shot": png, "overhead_before": overhead})
            overhead += time.perf_counter() - t0

        async with GeminiWriter(LITE, WRITER_BRIEF_V2) as writer:
            report = await run_jev(app, sentence + SIGNIN, {}, 25, False, writer=writer,
                                   mode="hybrid-v2", on_step=on_step)
        await asyncio.sleep(0.4)
        state = await app.state()
    trace = {t["step"]: t for t in report.trace}
    for s in shots:
        s["at"] = trace[s["step"]]["at"] - s["overhead_before"]
        s["cost"] = trace[s["step"]]["cost"]
    run = {"verdict": report.verdict, "real": bool(check(state)), "state": state,
           "wall": report.wall - overhead, "cost": report.cost, "steps": report.steps,
           "start": start_png, "sentence": sentence}
    return shots, run


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri", required=True)
    p.add_argument("--task", default="support-damaged")
    p.add_argument("--lang", choices=list(TEXT), default="zh")
    p.add_argument("--out-dir", type=Path, required=True,
                   help="gets <name>.gif, plus <name>/ holding the frames and sequence.json")
    p.add_argument("--name", default="hybrid-run")
    args = p.parse_args()
    T = TEXT[args.lang]
    seq_dir = args.out_dir / args.name
    seq_dir.mkdir(parents=True, exist_ok=True)
    shots, run = asyncio.run(record(args.uri, args.task, seq_dir))

    frames = [{"line": T["start"], "meta": run["sentence"], "clock": T["sec"].format(v=0),
               "cost": "$0.0000", "image": run["start"].name}]
    for s in shots:
        frames.append(caption(T, s) | {"clock": T["sec"].format(v=s["at"]), "cost": f"${s['cost']:.4f}",
                                       "image": s["shot"].name})
    t = run["state"].get("tickets") or []
    got = T["ticket"].format(o=t[-1]["order"], m=t[-1]["message"]) if t else T["none"]
    frames.append({"line": T["done" if run["real"] else "notdone"], "tone": "" if run["real"] else "red",
                   "meta": got, "clock": T["sec"].format(v=run["wall"]),
                   "cost": T["steps"].format(n=run["steps"], c=run["cost"]), "image": shots[-1]["shot"].name})
    seq = {"name": args.name, "eyebrow": T["eyebrow"], "frames": frames,
           "alt": T["alt"].format(n=run["steps"], w=run["wall"], c=run["cost"])}
    spec = seq_dir / "sequence.json"
    spec.write_text(json.dumps(seq, ensure_ascii=False, indent=1), encoding="utf-8")
    ok, msg = render_sequence.render(spec, args.out_dir)
    print(msg)
    print(f"verdict {run['verdict']}, really done {run['real']}, {run['wall']:.1f}s, ${run['cost']:.4f}")
    return 0 if ok and run["real"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
