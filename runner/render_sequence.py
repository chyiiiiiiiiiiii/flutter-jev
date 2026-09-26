#!/usr/bin/env python3
"""Vendored from the author's article-figures skill so this repo stands alone.

Turn a recorded run (screenshots + what happened at each step) into a captioned GIF.

  python3 render_sequence.py SEQUENCE.json --out-dir <article>/images

Recording is the project's job: whatever drives the app saves one screenshot per
step and writes a sequence spec (see references/components.md, `sequence`).
This script only lays the frames out in the house style: a caption band saying
who acted and what they did, the clock and cost on the right, the screenshot
below. Every frame's caption is checked for text leaving the band; one bad frame
fails the whole GIF, and nothing is written.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WIDTH = 900

FRAME = """<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=Inter+Tight:wght@500;700;800&display=swap">
<style>
*{{box-sizing:border-box}}
html,body{{margin:0;background:#fff;color-scheme:light}}
.f{{width:{w}px;padding:34px 40px 30px;font-family:"Inter Tight","Noto Sans TC",sans-serif;color:#0D0D0D}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px}}
.txt{{min-width:0}}
.eye{{font-size:13px;color:#8E8E8E}}
.line{{font-size:22px;font-weight:800;margin-top:6px;line-height:1.35}}
.tag{{display:inline-block;font-size:14px;font-weight:700;padding:3px 9px;border-radius:5px;margin-right:10px;vertical-align:3px}}
.ink{{background:#0D0D0D;color:#fff}} .outline{{border:1.5px solid #0D0D0D}}
code{{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:18px;font-weight:600}}
.meta{{font-size:13.5px;color:#6E6E6E;margin-top:6px}}
.clock{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.clock b{{display:block;font-size:30px;font-weight:800;letter-spacing:-.02em}}
.clock span{{font-size:13px;color:#8E8E8E}}
.shot{{margin-top:20px;border:1px solid #E6E6E6;border-radius:10px;overflow:hidden}}
.shot img{{display:block;width:100%}}
.red{{color:#D6331D}}
</style>
<body><div class="f"><div class="top"><div class="txt"><div class="eye">{eyebrow}</div><div class="line">{line}</div><div class="meta">{meta}</div></div>
<div class="clock"><b>{clock}</b><span>{cost}</span></div></div>
<div class="shot"><img src="{img}"></div></div>
<script>
document.fonts.ready.then(() => {{
  const f = document.querySelector(".f").getBoundingClientRect(), bad = [];
  for (const el of document.querySelectorAll(".top *")) {{
    const r = el.getBoundingClientRect();
    if (r.width && (r.right > f.right - 39 || r.left < f.left + 39)) bad.push(el.textContent.trim().slice(0, 24));
  }}
  document.body.dataset.gate = bad.length ? "FAIL " + bad.slice(0, 3).join(" | ") : "PASS";
}});
</script>"""

# `**x**` bold, `` `x` `` monospace; everything else escaped.
md = lambda v: re.sub(r"`(.+?)`", r"<code>\1</code>",
                      re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(str(v or ""))))


def chrome(*args: str) -> str:
    return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                           "--force-device-scale-factor=1", "--virtual-time-budget=5000",
                           "--blink-settings=preferredColorScheme=1", *args],
                          capture_output=True, text=True, timeout=120).stdout


def frame_html(seq: dict, fr: dict, base: Path) -> str:
    tag = ""
    if fr.get("tag"):
        tag = f'<span class="tag {"outline" if fr.get("tagStyle") == "outline" else "ink"}">{md(fr["tag"])}</span>'
    line = tag + (f'<span class="red">{md(fr["line"])}</span>' if fr.get("tone") == "red" else md(fr["line"]))
    img = (base / fr["image"]).resolve().as_uri()
    return FRAME.format(w=WIDTH, eyebrow=md(seq.get("eyebrow")), line=line, meta=md(fr.get("meta")),
                        clock=md(fr.get("clock")), cost=md(fr.get("cost")), img=img)


def content_height(im: Image.Image) -> int:
    px = im.load()
    for y in range(im.height - 1, 0, -1):
        if any(px[x, y] != (255, 255, 255) for x in range(0, im.width, 12)):
            return y
    return im.height


def render(spec_path: Path, out_dir: Path) -> tuple[bool, str]:
    seq = json.loads(spec_path.read_text(encoding="utf-8"))
    for k in ("name", "alt", "frames"):
        if not seq.get(k):
            return False, f"{spec_path.name}: missing {k}"
    base = spec_path.parent
    hold, last = seq.get("hold", 1400), seq.get("lastHold", 4000)
    shots = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, fr in enumerate(seq["frames"]):
            page = Path(tmp) / f"f{i:02d}.html"
            page.write_text(frame_html(seq, fr, base), encoding="utf-8")
            gate = re.search(r'data-gate="([^"]*)"', chrome("--dump-dom", page.as_uri()))
            if not gate or not gate.group(1).startswith("PASS"):
                return False, f"{seq['name']} frame {i}: {html.unescape(gate.group(1)) if gate else 'no report'}"
            png = Path(tmp) / f"f{i:02d}.png"
            chrome(f"--window-size={WIDTH},1000", f"--screenshot={png}", page.as_uri())
            shots.append(Image.open(png).convert("RGB"))
        h = max(content_height(im) for im in shots) + 30
        frames = [im.crop((0, 0, WIDTH, h)).quantize(colors=128, method=Image.Quantize.MEDIANCUT) for im in shots]
        out = out_dir / f"{seq['name']}.gif"
        durations = [hold] * (len(frames) - 1) + [last]
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    return True, f"![{seq['alt']}](images/{out.name})"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("specs", nargs="+", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    bad = 0
    for s in a.specs:
        ok, msg = render(s, a.out_dir)
        print(("  ok    " if ok else "  FAIL  ") + msg)
        bad += not ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
