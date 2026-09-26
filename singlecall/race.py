#!/usr/bin/env python3.13
"""Render the single-call comparison as a race, from real measured timings.

There is no screen to record when the whole task is one API call, so this is
a visualisation rather than a screen capture, and it says so on the frame. The
lane lengths, the clocks and the costs are the actual numbers from the run that
produced them; nothing here is drawn to a target.

  python3.13 race.py --item 0 --repeats 3

Writes an mp4 and a gif into ../results/media/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bench import DEPTH_NAMES, Gemini, Jev

W, H = 1500, 760
FPS = 20
TAIL = 1.8

INK = (20, 28, 24)
PAPER = (247, 246, 242)
DIM = (120, 132, 126)
LINE = (221, 219, 210)
GREEN = (31, 77, 58)
AMBER = (154, 107, 31)
ROSE = (155, 44, 63)

BOLD = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
MONO = "/System/Library/Fonts/Menlo.ttc"


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(MONO if mono else BOLD, size)


@dataclass
class Lane:
    label: str
    sub: str
    seconds: float
    cost: float
    answer: str
    colour: tuple[int, int, int]
    detail: str


async def measure(item: dict, repeats: int) -> list[Lane]:
    """Run each tier several times and keep the median, so one slow call does
    not become the story."""
    runs: dict[str, list] = {"jev": [], "flash-lite": [], "pro": []}
    async with (Jev() as jev,
                Gemini("gemini-3.1-flash-lite", think=False) as fast,
                Gemini("gemini-3.1-pro-preview", think=True) as pro):
        for i in range(repeats):
            runs["jev"].append(await jev.triage(item))
            runs["flash-lite"].append(await fast.triage(item))
            runs["pro"].append(await pro.triage(item))
            print(f"  pass {i + 1}/{repeats}")

    def pick(mode: str) -> Lane:
        ok = [s for s in runs[mode] if s.ok]
        if not ok:
            raise RuntimeError(f"{mode} never answered")
        secs = statistics.median(s.seconds for s in ok)
        rep = min(ok, key=lambda s: abs(s.seconds - secs))
        answer = (f"include {'yes' if rep.include else 'no'}   "
                  f"{rep.category}   {rep.depth}")
        thought = f" + {rep.thought_tokens} thinking" if rep.thought_tokens else ""
        return Lane(
            label={"jev": "Jev", "flash-lite": "Gemini 3.1 Flash-Lite",
                   "pro": "Gemini 3.1 Pro"}[mode],
            sub={"jev": "System One · typed answers, no text generated",
                 "flash-lite": "LLM · thinking off, writes JSON",
                 "pro": "LLM · thinking on, writes JSON"}[mode],
            seconds=secs,
            cost=statistics.median(s.cost_usd for s in ok),
            answer=answer,
            colour={"jev": GREEN, "flash-lite": AMBER, "pro": ROSE}[mode],
            detail=f"{rep.output_tokens} output tokens{thought}",
        )

    return [pick("jev"), pick("flash-lite"), pick("pro")]


def draw_frame(t: float, lanes: list[Lane], item: dict, total: float,
               footnote: str = "") -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 132], fill=INK)
    d.text((40, 24), "Same question. Three models.", font=font(34), fill=PAPER)
    d.text((40, 70), '"Would a senior engineer want this in today\'s digest?"'
                     "  +  which bucket  +  how deep",
           font=font(20), fill=(159, 232, 192))
    d.text((40, 98), item["title"][:94], font=font(17), fill=DIM)

    clock = font(30, mono=True)
    d.text((W - 190, 46), f"{t:5.2f}s", font=clock, fill=PAPER)

    top = 178
    lane_h = 168
    bar_x, bar_w = 430, W - 430 - 250

    for i, lane in enumerate(lanes):
        y = top + i * lane_h
        d.text((40, y), lane.label, font=font(27), fill=INK)
        d.text((40, y + 36), lane.sub, font=font(16), fill=DIM)

        done = t >= lane.seconds
        slowest = max(x.seconds for x in lanes)
        # Shared axis, so the lanes are directly comparable by length.
        frac = min(lane.seconds, t) / slowest if slowest > 0 else 1.0
        d.rounded_rectangle([bar_x, y + 4, bar_x + bar_w, y + 40],
                            radius=18, fill=(238, 237, 230), outline=LINE)
        if frac > 0.002:
            d.rounded_rectangle(
                [bar_x, y + 4, bar_x + max(30, int(bar_w * frac)), y + 40],
                radius=18, fill=lane.colour)

        shown = lane.seconds if done else t
        d.text((bar_x + bar_w + 24, y + 8), f"{shown:5.2f}s",
               font=font(26, mono=True), fill=INK if done else DIM)

        if done:
            d.text((bar_x, y + 54), lane.answer, font=font(21), fill=INK)
            d.text((bar_x, y + 86),
                   f"${lane.cost:.6f}   {lane.detail}",
                   font=font(17), fill=DIM)
        else:
            d.text((bar_x, y + 54), "working…", font=font(21), fill=DIM)

        if i < len(lanes) - 1:
            d.line([40, y + lane_h - 26, W - 40, y + lane_h - 26], fill=LINE)

    # Multipliers, once everything has landed.
    if t >= max(x.seconds for x in lanes):
        base = lanes[0]
        worst = lanes[-1]
        d.rectangle([0, H - 84, W, H], fill=INK)
        d.text((40, H - 72),
               f"Jev vs {worst.label}:  "
               f"{worst.seconds / base.seconds:.1f}x faster   "
               f"{worst.cost / base.cost:.0f}x cheaper",
               font=font(26), fill=(159, 232, 192))
        # The multipliers without the agreement rate would be a sales pitch.
        if footnote:
            d.text((40, H - 34), footnote, font=font(18), fill=(190, 198, 192))
    else:
        d.rectangle([0, H - 66, W, H], fill=(238, 237, 230))
        d.text((40, H - 46),
               "visualisation of measured API latencies, not a screen recording",
               font=font(17), fill=DIM)
    return img


def render(lanes: list[Lane], item: dict, out_dir: Path, name: str,
           footnote: str = "") -> None:
    total = max(x.seconds for x in lanes) + TAIL
    frames = out_dir / f"{name}-frames"
    frames.mkdir(parents=True, exist_ok=True)
    count = int(total * FPS)
    for n in range(count):
        draw_frame(n / FPS, lanes, item, total, footnote).save(
            frames / f"{n:05d}.png")
    print(f"  {count} frames over {total:.1f}s")

    mp4 = out_dir / f"{name}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frames / "%05d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(mp4)],
        check=True, capture_output=True)

    gif = out_dir / f"{name}.gif"
    palette = out_dir / f"{name}-palette.png"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp4), "-vf",
         "fps=10,scale=1100:-1:flags=lanczos,palettegen=stats_mode=diff",
         str(palette)], check=True, capture_output=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp4), "-i", str(palette), "-lavfi",
         "fps=10,scale=1100:-1:flags=lanczos[x];[x][1:v]"
         "paletteuse=dither=bayer:bayer_scale=3", str(gif)],
        check=True, capture_output=True)
    palette.unlink(missing_ok=True)
    for f in frames.iterdir():
        f.unlink()
    frames.rmdir()

    for p in (mp4, gif):
        print(f"  {p}  {p.stat().st_size / 1_000_000:.1f} MB")


def lanes_from_samples(path: Path) -> tuple[list[Lane], dict]:
    """Use the medians of the whole benchmark, not one item.

    A single call is a sample of one: the first render happened to catch a Pro
    call at 3.27s against its own 5.39s median, and reported 8.6x instead of
    the 19.5x the run actually measured. The aggregate is the honest number.
    """
    rows = [r for r in json.loads(path.read_text()) if r["ok"]]
    spec = {
        "jev": ("Jev", "System One · typed answers, no text generated", GREEN),
        "flash-lite": ("Gemini 3.1 Flash-Lite", "LLM · thinking off, writes JSON",
                       AMBER),
        "pro": ("Gemini 3.1 Pro", "LLM · thinking on, writes JSON", ROSE),
    }
    out: list[Lane] = []
    for mode, (label, sub, colour) in spec.items():
        s = [r for r in rows if r["mode"] == mode]
        secs = statistics.median(r["seconds"] for r in s)
        rep = min(s, key=lambda r: abs(r["seconds"] - secs))
        thought = statistics.median(r["thought_tokens"] for r in s)
        extra = f" + {thought:.0f} thinking" if thought else ""
        out.append(Lane(
            label=label, sub=sub, seconds=secs,
            cost=statistics.median(r["cost_usd"] for r in s),
            answer=f"include {'yes' if rep['include'] else 'no'}   "
                   f"{rep['category']}   {rep['depth']}",
            colour=colour,
            detail=f"{statistics.median(r['output_tokens'] for r in s):.0f} "
                   f"output tokens{extra}",
        ))
    n = len({r["item_id"] for r in rows})
    calls = len([r for r in rows if r["mode"] == "jev"])

    # Agreement, so the speed and cost numbers are not shown on their own.
    keyed = {}
    for r in rows:
        keyed.setdefault((r["mode"], r["item_id"]), r)
    ids = sorted({r["item_id"] for r in rows
                  if ("jev", r["item_id"]) in keyed
                  and ("pro", r["item_id"]) in keyed})
    agree = sum(1 for i in ids
                if keyed[("jev", i)]["include"] == keyed[("pro", i)]["include"]
                and keyed[("jev", i)]["category"] == keyed[("pro", i)]["category"])
    note = (f"they do not always agree: jev and pro give the same include and "
            f"bucket on {agree} of {len(ids)} items. "
            f"neither is ground truth; the task is a judgement call.")
    return out, {"title": f"median of {calls} calls per tier over "
                          f"{n} real Hacker News items", "footnote": note}


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--items", default="/tmp/hn_items.json")
    p.add_argument("--item", type=int, default=0)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--from-samples",
                   help="a singlecall-samples-*.json to take medians from")
    p.add_argument("--name", default="singlecall-race")
    p.add_argument("--out-dir", default="../results/media")
    args = p.parse_args()

    if args.from_samples:
        lanes, item = lanes_from_samples(Path(args.from_samples))
        print(f"driving the race from {args.from_samples}")
    else:
        item = json.loads(Path(args.items).read_text())[args.item]
        print(f'item: "{item["title"]}"')
        lanes = await measure(item, args.repeats)
    for lane in lanes:
        print(f"  {lane.label:26} {lane.seconds * 1000:7.0f}ms  "
              f"${lane.cost:.6f}  {lane.answer}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.name}-lanes.json").write_text(json.dumps(
        {"item": item, "lanes": [l.__dict__ for l in lanes]},
        indent=2, default=str))
    render(lanes, item, out, args.name, item.get("footnote", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
