#!/usr/bin/env python3.13
"""Stitch the three comparisons into one film, with title cards between them.

The three clips answer three different questions and were built at different
sizes, so this pads each to a common canvas rather than stretching it, and puts
a card in front of each one saying what it is about and what the numbers were.

  python3.13 stitch.py
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1944, 1000
FPS = 12
CARD_SECONDS = 3.4

INK = (16, 21, 18)
PAPER = (247, 246, 242)
MINT = (159, 232, 192)
DIM = (150, 160, 154)

BOLD = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
MONO = "/System/Library/Fonts/Menlo.ttc"


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(MONO if mono else BOLD, size)


@dataclass
class Chapter:
    clip: str
    number: str
    title: str
    question: str
    lines: list[str]


CHAPTERS = [
    Chapter(
        clip="support-recovery.mp4",
        number="1",
        title="When the hand-written script breaks",
        question="Can an agent get past something a script cannot?",
        lines=[
            "The script reaches for a button that is below the fold, and stops.",
            "Jev types in the search box to shorten the list, and the button appears.",
            "script  FAIL  5 steps  3.8s  $0.0000        jev  PASS  10 steps  10.0s  $0.0004",
        ],
    ),
    Chapter(
        clip="return-both-pass.mp4",
        number="2",
        title="When both of them work",
        question="What does the agent cost when nothing is broken?",
        lines=[
            "Same flow, both green. The agent takes more steps and more time.",
            "A script that already knows every answer beats one that has to ask.",
            "script  PASS  10 steps  8.3s  $0.0000        jev  PASS  12 steps  17.7s  $0.0005",
        ],
    ),
    Chapter(
        clip="singlecall-race.mp4",
        number="3",
        title="Where the claimed multiplier actually lives",
        question="40-200x faster. Against what, exactly?",
        lines=[
            "One call, one typed judgement, 20 real Hacker News items, 40 calls per tier.",
            "Against a frontier model with reasoning: 19.5x faster, 220x cheaper.",
            "Against a small model with reasoning off: 3.5x. Both are true.",
        ],
    ),
]

OUTRO = [
    "In the UI loop the model is 30% of the wall time,",
    "so an instant model still caps the end-to-end gain at 1.43x.",
    "",
    "The multiplier is real where one call is the whole task.",
    "It disappears where the call is one step in a loop.",
]


def card(chapter: Chapter, path: Path) -> None:
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    d.text((110, 150), chapter.number, font=font(120, mono=True), fill=(46, 58, 50))
    d.text((300, 176), chapter.title, font=font(62), fill=PAPER)
    d.text((300, 268), chapter.question, font=font(34), fill=MINT)
    d.line([300, 340, W - 110, 340], fill=(46, 58, 50), width=2)
    y = 400
    for line in chapter.lines:
        mono = "$" in line and "  " in line
        d.text((300, y), line, font=font(26, mono=mono),
               fill=PAPER if not mono else MINT)
        y += 58
    d.text((300, H - 120), "measured on one machine, 2026-09-22",
           font=font(22), fill=DIM)
    img.save(path)


def outro(path: Path) -> None:
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    y = 250
    for line in OUTRO:
        if not line:
            y += 40
            continue
        big = line.startswith("The multiplier") or line.startswith("It disappears")
        d.text((140, y), line, font=font(46 if big else 36),
               fill=MINT if big else PAPER)
        y += 72 if big else 62
    d.text((140, H - 130), "github.com/… flutter-jev   ·   numbers and method in results/REPORT.md",
           font=font(24), fill=DIM)
    img.save(path)


def normalise(src: Path, dst: Path) -> None:
    """Fit a clip onto the shared canvas without distorting it."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
         f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=#101512,fps={FPS}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(dst)],
        check=True, capture_output=True)


def still(png: Path, seconds: float, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", str(png), "-t", f"{seconds}",
         "-vf", f"fps={FPS}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "20", str(dst)],
        check=True, capture_output=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--media", default="../results/media")
    p.add_argument("--name", default="jev-full-comparison")
    args = p.parse_args()

    media = Path(args.media)
    work = media / "_stitch"
    work.mkdir(parents=True, exist_ok=True)

    parts: list[Path] = []
    for i, chapter in enumerate(CHAPTERS):
        src = media / chapter.clip
        if not src.exists():
            print(f"missing {src}, skipping")
            continue
        png = work / f"card{i}.png"
        card(chapter, png)
        seg = work / f"card{i}.mp4"
        still(png, CARD_SECONDS, seg)
        parts.append(seg)

        body = work / f"body{i}.mp4"
        normalise(src, body)
        parts.append(body)

    png = work / "outro.png"
    outro(png)
    seg = work / "outro.mp4"
    still(png, 4.2, seg)
    parts.append(seg)

    listing = work / "parts.txt"
    listing.write_text("\n".join(f"file '{p.resolve()}'" for p in parts) + "\n")

    out = media / f"{args.name}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21",
         "-r", str(FPS), str(out)],
        check=True, capture_output=True)

    for f in work.iterdir():
        f.unlink()
    work.rmdir()

    duration = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out)],
        capture_output=True, text=True, check=True).stdout.strip()
    print(f"  {out}  {out.stat().st_size / 1_000_000:.1f} MB  {float(duration):.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
