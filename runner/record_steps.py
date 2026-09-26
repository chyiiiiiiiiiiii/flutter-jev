#!/usr/bin/env python3.13
"""Build a side-by-side comparison from per-step screenshots.

Why not a screen recording: marionette's screencast streams frames through the
app, and when the app window is not frontmost macOS stops compositing, so the
stream hands back stale pictures. A 24 second recording of a run that visited
four screens showed the sign-in page the whole way through. A screenshot pulled
on demand is answered from the live tree, so every frame provably belongs to
the step it is labelled with.

The two sides share one real-time axis: each frame appears at the moment its
step actually happened, so a side that fails simply stops while the other keeps
going. The clock and the running cost are burned in.

  python3.13 record_steps.py --uri ws://... \\
      --left support-flow-naive \\
      --right-task "sign in with the demo account, then contact support ..." \\
      --name support-recovery
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
from pathlib import Path

from elements import build_actions, render_screen
from jev import Jev
from agent import (CONFIDENCE_FLOOR, DEFAULT_VALUES, SCRIPTS, Report,
                   perform, risk_of)
from transport import Marionette, MarionetteError

FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FONT_FALLBACK = "/System/Library/Fonts/Helvetica.ttc"
TAIL = 3.0


def font_path() -> str:
    return FONT if Path(FONT).exists() else FONT_FALLBACK


async def shoot(app: Marionette, shots: list[dict], frames: Path,
                index: int, started: float, label: str, detail: str,
                failed: bool = False) -> None:
    path = frames / f"{index:03d}.png"
    await app.screenshot(str(path))
    shots.append({
        "at": round(time.perf_counter() - started, 3),
        "file": str(path),
        "label": label,
        "detail": detail,
        "failed": failed,
    })


def renamed_to(elements: list, target: str) -> str | None:
    """Find what the app calls a widget now, given what the script called it.

    Without this the failing caption says only that a key was not found, and
    the viewer has no way to see that the widget is right there under another
    name. That sentence is the entire point of the comparison.
    """
    for e in elements:
        if e.key and e.key != target and e.key.startswith(target):
            return e.key
    return None


async def capture_scripted(app: Marionette, flow: str,
                           frames: Path) -> tuple[list[dict], dict]:
    steps = SCRIPTS[flow]
    shots: list[dict] = []
    report = Report("scripted", flow)
    started = time.perf_counter()
    await shoot(app, shots, frames, 0, started, "ready", "$0.0000  no model")

    before: tuple[int, ...] | None = None
    for i, (kind, selector, text) in enumerate(steps, start=1):
        elements = await app.settled_after(before)
        before = app.fingerprint(elements)
        target = selector.get("key", str(selector))
        try:
            await perform(app, kind, selector, text, elements)
        except MarionetteError:
            print(f"  step {i}: FAILED {kind} {target}")
            now = renamed_to(await app.elements(), target)
            detail = (f"the app calls it {now} now - the script stops here"
                      if now else "not on screen - the script stops here")
            await shoot(app, shots, frames, i, started,
                        f"x {i}. {kind} {target}", detail, failed=True)
            report.verdict = "fail"
            report.steps = i
            break
        print(f"  step {i}: {kind} {target}")
        await shoot(app, shots, frames, i, started,
                    f"{i}. {kind} {target}", "$0.0000  no model")
        report.steps = i
    else:
        report.verdict = "pass"
        # The last action fires a navigation the app has not finished yet, so
        # shooting straight after it captures the screen being left behind.
        await app.settled_after(before)
        await shoot(app, shots, frames, len(steps) + 1, started,
                    f"{len(steps)}. {steps[-1][0]} "
                    f"{steps[-1][1].get('key', '')}", "$0.0000  no model")

    report.wall = time.perf_counter() - started
    return shots, report.to_json()


async def capture_jev(app: Marionette, task: str, frames: Path,
                      max_steps: int) -> tuple[list[dict], dict]:
    shots: list[dict] = []
    report = Report("jev", task)
    started = time.perf_counter()
    await shoot(app, shots, frames, 0, started, "ready", "$0.0000")

    before: tuple[int, ...] | None = None
    previous_screen = previous_action = None
    barren: dict[str, int] = {}

    async with Jev() as model:
        for step in range(1, max_steps + 1):
            elements = await app.settled_after(before)
            screen, targets = render_screen(elements)
            if not targets:
                report.verdict = "fail"
                break
            actions = [a for a in build_actions(targets, DEFAULT_VALUES)
                       if barren.get(a.id, 0) < 2]
            decision = await model.decide({
                "task": task, "screen": screen,
                "previousScreen": previous_screen,
                "previousAction": previous_action,
            }, actions)
            report.usage.add(decision)
            chosen = next((a for a in actions if a.id == decision.action_id), None)
            if chosen is None:
                report.verdict = "fail"
                break
            report.steps = step

            target = chosen.element.key if chosen.element else chosen.id
            risk = risk_of(chosen.kind, target or "")
            label = f"{step}. {chosen.kind} {target}"
            detail = (f"${report.cost:.4f} so far   "
                      f"confidence {decision.confidence:.2f}   "
                      f"{decision.seconds * 1000:.0f}ms")
            print(f"  step {step}: {label}  {detail}")

            if decision.confidence < CONFIDENCE_FLOOR[risk]:
                await shoot(app, shots, frames, step, started, label,
                            f"{detail} - below the {risk} floor, stopping",
                            failed=True)
                report.verdict = "uncertain"
                break
            if chosen.kind == "finish":
                report.verdict = chosen.verdict or "unknown"
                await shoot(app, shots, frames, step, started,
                            f"{step}. reports {report.verdict}", detail)
                break

            selector = chosen.element.selector() if chosen.element else {}
            try:
                await perform(app, chosen.kind, selector, chosen.text or "",
                              elements)
            except MarionetteError:
                await shoot(app, shots, frames, step, started, label,
                            f"{detail} - action failed", failed=True)
                report.verdict = "fail"
                break

            after = app.fingerprint(await app.elements())
            if after == app.fingerprint(elements):
                barren[chosen.id] = barren.get(chosen.id, 0) + 1
            else:
                barren.pop(chosen.id, None)

            await shoot(app, shots, frames, step, started, label, detail)
            before = app.fingerprint(elements)
            previous_screen, previous_action = screen, chosen.description

    report.wall = time.perf_counter() - started
    return shots, report.to_json()


def esc(text: str) -> str:
    for a, b in (("\\", "\\\\"), (":", "\\:"), ("'", ""), ("%", "\\%"),
                 (",", "\\,"), ("[", "\\["), ("]", "\\]")):
        text = text.replace(a, b)
    return text


def caption(src: Path, dst: Path, title: str, subtitle: str, clock: str,
            line: str, detail: str, colour: str,
            width: int, height: int) -> None:
    """Burn one frame's captions in, rather than switching them with `enable`.

    Time-windowed `drawtext` looked right and rendered wrong: the concat
    demuxer does not hand stills the wall-clock timestamps those expressions
    assume, so every frame kept whichever caption happened to match its own
    small `t`. Baking each caption into its own frame removes the timing
    expression entirely, so what the JSON says is what the picture shows.

    The bands sit around the picture, not over it: overlaying them hid the
    app's own app bar and bottom navigation, which are part of the story.
    """
    font = font_path()
    top = bottom = 104
    filters = ",".join([
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#F7F6F2",
        f"pad={width}:{height + top + bottom}:0:{top}:color=#101512",
        f"drawtext=fontfile='{font}':text='{esc(title)}':"
        f"x=26:y=22:fontsize=32:fontcolor=white",
        f"drawtext=fontfile='{font}':text='{esc(subtitle)}':"
        f"x=26:y=66:fontsize=20:fontcolor=#9FE8C0",
        f"drawtext=fontfile='{font}':text='{esc(clock)}':"
        f"x={width - 170}:y=30:fontsize=34:fontcolor=white",
        f"drawtext=fontfile='{font}':text='{esc(line)}':"
        f"x=26:y=h-84:fontsize=24:fontcolor={colour}",
        f"drawtext=fontfile='{font}':text='{esc(detail)}':"
        f"x=26:y=h-44:fontsize=20:fontcolor=#C9D6CF",
    ])
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-vf", filters, "-frames:v", "1",
         str(dst)], check=True, capture_output=True)


def build_side(shots: list[dict], data: dict, title: str, subtitle: str,
               total: float, out: Path, width: int, height: int) -> None:
    """Render one column: captioned frames on the real elapsed-time axis."""
    verdict = str(data["verdict"]).upper()
    ran = float(data["wall_seconds"])
    band = "#FF9AA8" if verdict != "PASS" else "#9FE8C0"
    final = (f"{verdict}   {int(data['steps'])} steps   {ran:.1f}s   "
             f"${float(data['cost_usd']):.4f}")

    staged = out.parent / f"{out.stem}-captioned"
    staged.mkdir(parents=True, exist_ok=True)

    # The last caption needs guaranteed screen time. On a failed run the step
    # that failed lands at the same moment the run ends, so its window was a
    # few milliseconds wide and the closing banner covered it instantly: the
    # single most important frame in the video never played.
    LAST_HOLD = 2.8

    entries: list[tuple[Path, float]] = []
    for i, shot in enumerate(shots):
        at = float(shot["at"])
        last = i == len(shots) - 1
        nxt = float(shots[i + 1]["at"]) if not last else ran
        dst = staged / f"{i:03d}.png"
        caption(Path(shot["file"]), dst, title, subtitle, f"{at:.1f}s",
                str(shot["label"]), str(shot["detail"]),
                "#FF9AA8" if shot["failed"] else "white", width, height)
        hold = max(LAST_HOLD, nxt - at) if last else max(0.35, nxt - at)
        entries.append((dst, hold))

    # A closing frame that holds the totals, on whatever screen it stopped on.
    closing = staged / "999.png"
    caption(Path(shots[-1]["file"]), closing, title, subtitle, f"{ran:.1f}s",
            final, "", band, width, height)
    spent = sum(h for _, h in entries)
    entries.append((closing, max(0.6, total - spent)))

    concat = out.with_suffix(".txt")
    lines = []
    for path, hold in entries:
        lines.append(f"file '{path.resolve()}'")
        lines.append(f"duration {hold:.3f}")
    lines.append(f"file '{entries[-1][0].resolve()}'")
    concat.write_text("\n".join(lines) + "\n")

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
         "-vf", "fps=12", "-t", f"{total:.2f}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out)],
        check=True, capture_output=True)
    concat.unlink(missing_ok=True)


def stack(left: Path, right: Path, out_mp4: Path, out_gif: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(left), "-i", str(right),
         "-filter_complex",
         "[0:v][1:v]hstack=inputs=2[s];"
         "[s]pad=iw+24:ih+24:12:12:color=#101512[out]",
         "-map", "[out]", "-r", "12", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-crf", "20", str(out_mp4)],
        check=True, capture_output=True)

    palette = out_gif.with_name(out_gif.stem + "-palette.png")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(out_mp4), "-vf",
         "fps=8,scale=1200:-1:flags=lanczos,palettegen=stats_mode=diff",
         str(palette)], check=True, capture_output=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(out_mp4), "-i", str(palette), "-lavfi",
         "fps=8,scale=1200:-1:flags=lanczos[x];[x][1:v]"
         "paletteuse=dither=bayer:bayer_scale=3", str(out_gif)],
        check=True, capture_output=True)
    palette.unlink(missing_ok=True)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri", required=True)
    p.add_argument("--left", required=True)
    p.add_argument("--right-task", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--max-steps", type=int, default=25)
    p.add_argument("--chaos", type=int, default=0,
                   help="churn the app first, the same seed for both sides")
    p.add_argument("--out-dir", default="../results/media")
    args = p.parse_args()

    if args.left not in SCRIPTS:
        print(f"unknown flow; try one of {', '.join(SCRIPTS)}")
        return 2

    out = Path(args.out_dir)
    frames_l = out / f"{args.name}-frames-scripted"
    frames_r = out / f"{args.name}-frames-jev"
    for d in (out, frames_l, frames_r):
        d.mkdir(parents=True, exist_ok=True)

    churn = {}
    print(f"===== scripted: {args.left} =====")
    async with Marionette(args.uri) as app:
        await app.hot_restart()
        await asyncio.sleep(2.0)
        if args.chaos:
            churn = await app.set_chaos(args.chaos)
            print(f"  chaos seed {args.chaos}: keys now end "
                  f"{churn.get('keySuffix')}")
            await asyncio.sleep(0.8)
        shots_l, data_l = await capture_scripted(app, args.left, frames_l)

    print("\n===== jev =====")
    async with Marionette(args.uri) as app:
        await app.hot_restart()
        await asyncio.sleep(2.0)
        if args.chaos:
            # The identical churn, so the two sides face the same app.
            await app.set_chaos(args.chaos)
            await asyncio.sleep(0.8)
        shots_r, data_r = await capture_jev(app, args.right_task, frames_r,
                                            args.max_steps)
        await app.stop_screencast()

    total = max(float(data_l["wall_seconds"]),
                float(data_r["wall_seconds"])) + TAIL
    (out / f"{args.name}-steps.json").write_text(json.dumps(
        {"scripted": {"report": data_l, "shots": shots_l},
         "jev": {"report": data_r, "shots": shots_r},
         "total_seconds": round(total, 3)}, indent=2))

    print("\n===== composing =====")
    left_mp4 = out / f"{args.name}-left.mp4"
    right_mp4 = out / f"{args.name}-right.mp4"
    suffix = churn.get("keySuffix", "")
    left_sub = (f"{len(SCRIPTS[args.left])} selectors, written before "
                f"someone renamed things" if suffix
                else f"{len(SCRIPTS[args.left])} selectors written by me")
    right_sub = ("reads whatever the screen calls things now" if suffix
                 else "one English sentence in")
    build_side(shots_l, data_l, "Hand-written script", left_sub,
               total, left_mp4, 960, 720)
    build_side(shots_r, data_r, "Jev decides each step", right_sub,
               total, right_mp4, 960, 720)
    stack(left_mp4, right_mp4, out / f"{args.name}.mp4",
          out / f"{args.name}.gif")

    for f in (f"{args.name}.mp4", f"{args.name}.gif"):
        path = out / f
        if path.exists():
            print(f"  {path}  {path.stat().st_size / 1_000_000:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
