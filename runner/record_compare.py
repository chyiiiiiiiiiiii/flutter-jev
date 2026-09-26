#!/usr/bin/env python3.13
"""Record both modes on the same flow and compose a side-by-side comparison.

The success case looks almost identical on screen, because both modes drive the
same app with the same taps. The difference lives in the terminal. So the
overlay is the point: it burns in the running clock, the step the mode is on,
and the accumulated model cost, which is what the two modes actually disagree
about.

  python3.13 record_compare.py --uri ws://... --flow support-flow \\
      --left support-flow-naive --right-task "sign in ... contact support ..."

Outputs an mp4 and a gif into ../results/media/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import subprocess
import time
from pathlib import Path

from agent import DEFAULT_VALUES, SCRIPTS, run_jev, run_scripted
from transport import Marionette

FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FONT_FALLBACK = "/System/Library/Fonts/Helvetica.ttc"

# The recorder attaches on its own schedule, so the video's t=0 is not the
# moment the subprocess was spawned. Guessing that offset put the captions
# five seconds ahead of the picture, so the clock now starts when the recorder
# itself says it is rolling.
READY_LINE = "Recording "
LEAD_IN = 0.8
TAIL = 2.5


def font_path() -> str:
    return FONT if Path(FONT).exists() else FONT_FALLBACK


async def record_one(uri: str, mode: str, target: str, out: Path,
                     seconds: int) -> dict[str, object]:
    """Record the app while a flow runs against it."""
    out.parent.mkdir(parents=True, exist_ok=True)
    recorder = await asyncio.create_subprocess_exec(
        "marionette", "--uri", uri, "record-video",
        "-o", str(out), "-d", str(seconds),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        # Wait for the recorder to say it is rolling; that line is video t=0.
        assert recorder.stdout is not None
        rolling = time.perf_counter()
        while True:
            raw = await asyncio.wait_for(recorder.stdout.readline(), timeout=30)
            if not raw:
                raise RuntimeError("recorder exited before it started")
            line = raw.decode(errors="replace")
            print(f"  [recorder] {line.rstrip()}")
            if READY_LINE in line:
                rolling = time.perf_counter()
                break

        await asyncio.sleep(LEAD_IN)
        async with Marionette(uri) as app:
            await app.hot_restart()
            await asyncio.sleep(2.0)
            started = time.perf_counter()
            if mode == "scripted":
                report = await run_scripted(app, target)
            else:
                report = await run_jev(app, target, DEFAULT_VALUES, 25, False)
            ran_for = time.perf_counter() - started
        await asyncio.sleep(TAIL)
    finally:
        try:
            await asyncio.wait_for(recorder.wait(), timeout=seconds + 30)
        except (TimeoutError, asyncio.TimeoutError):
            recorder.kill()
        # Whether it exited on its own or was killed, leave no frame stream
        # behind: one leaked screencast makes every later query ~20x slower.
        async with Marionette(uri) as cleanup:
            await cleanup.stop_screencast()

    data = report.to_json()
    # Measured, not assumed: how far into the video the flow actually began.
    data["offset"] = round(started - rolling, 3)
    data["ran_for"] = round(ran_for, 3)
    return data


def esc(text: str) -> str:
    """Escape a string for ffmpeg's drawtext, which is fussy about punctuation."""
    for a, b in (("\\", "\\\\"), (":", "\\:"), ("'", ""), ("%", "\\%"),
                 (",", "\\,"), ("[", "\\["), ("]", "\\]")):
        text = text.replace(a, b)
    return text


def overlay(data: dict[str, object], title: str, subtitle: str,
            width: int) -> list[str]:
    """Build the drawtext chain for one side of the comparison."""
    font = font_path()
    offset = float(data["offset"])
    filters = [
        # Header band, so the two sides are never confused for one another.
        f"drawbox=x=0:y=0:w={width}:h=96:color=black@0.82:t=fill",
        f"drawtext=fontfile='{font}':text='{esc(title)}':"
        f"x=24:y=18:fontsize=30:fontcolor=white",
        f"drawtext=fontfile='{font}':text='{esc(subtitle)}':"
        f"x=24:y=58:fontsize=19:fontcolor=#9FE8C0",
        # Running clock, started when the flow started.
        f"drawtext=fontfile='{font}':"
        f"text='%{{eif\\:max(0\\,t-{offset:.2f})\\:d}}.%{{eif\\:"
        f"mod(max(0\\,(t-{offset:.2f}))*10\\,10)\\:d}}s':"
        f"x={width - 150}:y=22:fontsize=32:fontcolor=white",
    ]

    trace = data.get("trace") or []
    steps = len(trace)
    for i, step in enumerate(trace):
        at = offset + float(step.get("at", 0.0))
        nxt = (offset + float(trace[i + 1].get("at", 0.0))
               if i + 1 < steps else offset + float(data["ran_for"]) + 0.2)
        failed = bool(step.get("failed"))
        target = str(step.get("target", ""))
        kind = str(step.get("kind", ""))
        line = f"{i + 1}. {kind} {target}"
        if failed:
            line = f"x FAILED: {kind} {target} not on screen"
        colour = "#FF9AA8" if failed else "white"
        filters.append(
            f"drawbox=x=0:y=ih-104:w={width}:h=104:color=black@0.82:t=fill:"
            f"enable='between(t,{at:.2f},{nxt:.2f})'")
        filters.append(
            f"drawtext=fontfile='{font}':text='{esc(line)}':"
            f"x=24:y=h-88:fontsize=21:fontcolor={colour}:"
            f"enable='between(t,{at:.2f},{nxt:.2f})'")
        cost = float(step.get("cost", 0.0))
        money = "$0.0000  no model" if cost == 0 else f"${cost:.4f} so far"
        conf = step.get("confidence")
        detail = money if conf is None else f"{money}   confidence {conf:.2f}"
        filters.append(
            f"drawtext=fontfile='{font}':text='{esc(detail)}':"
            f"x=24:y=h-52:fontsize=19:fontcolor=#C9D6CF:"
            f"enable='between(t,{at:.2f},{nxt:.2f})'")

    verdict = str(data["verdict"]).upper()
    total = float(data["ran_for"])
    final = (f"{verdict}   {steps} steps   {total:.1f}s   "
             f"${float(data['cost_usd']):.4f}")
    band = "#FF9AA8" if verdict != "PASS" else "#9FE8C0"
    last = offset + total + 0.2
    filters.append(
        f"drawbox=x=0:y=ih-104:w={width}:h=104:color=black@0.9:t=fill:"
        f"enable='gte(t,{last:.2f})'")
    filters.append(
        f"drawtext=fontfile='{font}':text='{esc(final)}':"
        f"x=24:y=h-72:fontsize=26:fontcolor={band}:enable='gte(t,{last:.2f})'")
    return filters


def compose(left: Path, left_data: dict, right: Path, right_data: dict,
            out_mp4: Path, out_gif: Path, height: int = 720) -> None:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(left)],
        capture_output=True, text=True, check=True).stdout.strip()
    src_w, src_h = (int(v) for v in probe.split(",")[:2])
    width = max(2, int(src_w * height / src_h) // 2 * 2)

    lf = ",".join([f"scale={width}:{height}",
                   *overlay(left_data, "Hand-written script",
                            "10 selectors written by me", width)])
    rf = ",".join([f"scale={width}:{height}",
                   *overlay(right_data, "Jev decides each step",
                            "one English sentence in", width)])

    cmd = [
        "ffmpeg", "-y",
        "-i", str(left), "-i", str(right),
        "-filter_complex",
        f"[0:v]{lf}[L];[1:v]{rf}[R];"
        f"[L][R]hstack=inputs=2[v];"
        f"[v]pad=iw:ih+8:0:8:color=#101512[out]",
        "-map", "[out]", "-r", "24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        str(out_mp4),
    ]
    print("\n$ " + " ".join(shlex.quote(c) for c in cmd)[:400] + " ...")
    subprocess.run(cmd, check=True, capture_output=True)

    # A GIF is what actually gets shared, so make one that is not enormous.
    palette = out_gif.with_suffix(".png")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(out_mp4), "-vf",
         "fps=10,scale=1100:-1:flags=lanczos,palettegen=stats_mode=diff",
         str(palette)], check=True, capture_output=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(out_mp4), "-i", str(palette),
         "-lavfi", "fps=10,scale=1100:-1:flags=lanczos[x];[x][1:v]"
                   "paletteuse=dither=bayer:bayer_scale=3",
         str(out_gif)], check=True, capture_output=True)
    palette.unlink(missing_ok=True)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri", required=True)
    p.add_argument("--left", required=True, help="scripted flow name")
    p.add_argument("--right-task", required=True, help="sentence for Jev")
    p.add_argument("--name", required=True, help="output basename")
    p.add_argument("--seconds", type=int, default=34)
    p.add_argument("--out-dir", default="../results/media")
    args = p.parse_args()

    if args.left not in SCRIPTS:
        print(f"unknown flow; try one of {', '.join(SCRIPTS)}")
        return 2

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"===== recording scripted: {args.left} =====")
    left_raw = out / f"{args.name}-scripted.webm"
    left_data = await record_one(args.uri, "scripted", args.left,
                                 left_raw, args.seconds)

    print(f"\n===== recording jev =====")
    right_raw = out / f"{args.name}-jev.webm"
    right_data = await record_one(args.uri, "jev", args.right_task,
                                  right_raw, args.seconds)

    (out / f"{args.name}-trace.json").write_text(
        json.dumps({"scripted": left_data, "jev": right_data}, indent=2))

    print("\n===== composing =====")
    compose(left_raw, left_data, right_raw, right_data,
            out / f"{args.name}.mp4", out / f"{args.name}.gif")

    for f in (f"{args.name}.mp4", f"{args.name}.gif"):
        path = out / f
        size = path.stat().st_size / 1_000_000 if path.exists() else 0
        print(f"  {path}  {size:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
