#!/usr/bin/env python3
"""Draw the system design and the one-step flow, in the look Wingman's READMEs use,
and render them to PNG with Chrome.

    python3 scripts/make-diagrams.py    writes docs/{architecture,flow}-{en,zh-Hant}.png

Every word and position lives here, so a change is an edit to this file and a rerun.
Jev is indigo and the writing model cyan; the decision loop, the one card that talks
to both, gets the gradient border. The numbers are the ones results/ holds. Needs
Google Chrome.
"""
from __future__ import annotations

import html
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

STYLE = """
* { box-sizing: border-box; margin: 0; }
body { background: #0E0F13; color: #F4F4F5; -webkit-font-smoothing: antialiased;
       font-family: -apple-system, "SF Pro Text", "PingFang TC", "Helvetica Neue", sans-serif; }
.canvas { position: relative; overflow: hidden;
          background: radial-gradient(900px 500px at 0% 0%, rgba(91,79,224,.20), transparent 60%),
                      radial-gradient(800px 500px at 100% 100%, rgba(38,201,206,.12), transparent 60%), #0E0F13; }
.head { position: absolute; left: 48px; top: 36px; display: flex; gap: 16px; align-items: center; }
.head .mark { width: 48px; height: 48px; border-radius: 12px; display: grid; place-items: center;
              background: linear-gradient(135deg, #6A5CF0, #26C9CE); font-size: 24px; font-weight: 800; color: #0E0F13; }
.head b { display: block; font-size: 26px; letter-spacing: -.01em; }
.head span { display: block; font-size: 15px; color: #A1A1AA; margin-top: 2px; }
.card { position: absolute; border-radius: 14px; background: #17181E; border: 1px solid rgba(255,255,255,.10);
        box-shadow: 0 12px 30px -18px rgba(0,0,0,.8); padding: 14px 16px; }
.card h3 { font-size: 16px; font-weight: 650; letter-spacing: -.005em; }
.card code { display: block; font: 12px/1.5 "SF Mono", Menlo, monospace; color: #8FA3C8; margin-top: 3px; }
.card p { font-size: 13px; line-height: 1.5; color: #A1A1AA; margin-top: 4px; }
.card.core { border: 1.5px solid transparent;
             background: linear-gradient(#17181E, #17181E) padding-box, linear-gradient(120deg, #6A5CF0, #26C9CE) border-box; }
.card.jev { border-color: rgba(139,124,255,.75); background: #1A1830; }
.card.jev h3 { color: #B3A9FF; }
.card.llm { border-color: rgba(63,208,216,.7); background: #122428; }
.card.llm h3 { color: #6FE0E6; }
.label { position: absolute; font-size: 12.5px; color: #8B8B96; white-space: nowrap; }
.caps { position: absolute; font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #71717A; }
.frame { position: absolute; border: 1.5px dashed rgba(255,255,255,.18); border-radius: 22px; }
.tag { position: absolute; background: #0E0F13; padding: 2px 12px; border-radius: 999px; font-size: 14px; font-weight: 600;
       border: 1px solid rgba(255,255,255,.16); }
.tag i { font-style: normal; font-weight: 400; color: #A1A1AA; margin-left: 6px; }
.lane { position: absolute; border-radius: 16px; background: rgba(255,255,255,.028); border: 1px solid rgba(255,255,255,.05); }
.lane-name { position: absolute; font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.step .n { display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; font-size: 12px;
           font-weight: 700; background: #F4F4F5; color: #0E0F13; margin-right: 8px; vertical-align: 1px; }
.step.jev .n { background: #8B7CFF; color: #0E0F13; }
.step.llm .n { background: #3FD0D8; color: #0E0F13; }
.chip { display: inline-block; margin-top: 8px; font-size: 12px; padding: 2px 9px; border-radius: 999px;
        background: rgba(255,255,255,.07); color: #D4D4D8; }
.stop { margin-top: 8px; font-size: 12px; line-height: 1.45; color: #D4D4D8; border: 1px dashed rgba(255,255,255,.25);
        border-radius: 8px; padding: 5px 8px; }
.foot { position: absolute; font-size: 14px; color: #A1A1AA; line-height: 1.55; }
.foot b { color: #F4F4F5; font-weight: 600; }
svg { position: absolute; left: 0; top: 0; }
"""

COLORS = {"ink": "rgba(255,255,255,.42)", "jev": "#8B7CFF", "llm": "#3FD0D8"}


class Page:
    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self.parts: list[str] = []
        self.lines: list[str] = []

    def add(self, markup: str, x: float, y: float, w: float | None = None, h: float | None = None, cls: str = "card"):
        size = (f"width:{w}px;" if w else "") + (f"min-height:{h}px;" if h else "")
        self.parts.append(f'<div class="{cls}" style="left:{x}px;top:{y}px;{size}">{markup}</div>')

    def arrow(self, points: list[tuple[float, float]], color: str = "ink", dashed: bool = False):
        path = " ".join(f"{x},{y}" for x, y in points)
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.lines.append(f'<polyline points="{path}" fill="none" stroke="{COLORS[color]}" stroke-width="1.8"'
                          f' stroke-linejoin="round"{dash} marker-end="url(#{color})"/>')

    def line(self, points: list[tuple[float, float]]):
        path = " ".join(f"{x},{y}" for x, y in points)
        self.lines.append(f'<polyline points="{path}" fill="none" stroke="{COLORS["ink"]}" stroke-width="1.8"'
                          f' stroke-linejoin="round"/>')

    def badge(self, x: float, y: float, text: str, color: str):
        width = 14 + 14 * len(text)
        self.lines.append(f'<rect x="{x - width / 2}" y="{y - 12}" width="{width}" height="24" rx="12" fill="#0E0F13" '
                          f'stroke="{COLORS[color]}" stroke-width="1.5"/>'
                          f'<text x="{x}" y="{y + 4.5}" text-anchor="middle" font-size="13" font-weight="700" '
                          f'fill="{COLORS[color]}">{html.escape(text)}</text>')

    def header(self, title: str, subtitle: str):
        self.parts.append(f'<div class="head"><div class="mark">J</div><div>'
                          f'<b>{html.escape(title)}</b><span>{html.escape(subtitle)}</span></div></div>')

    def render(self) -> str:
        markers = "".join(
            f'<marker id="{name}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
            for name, color in COLORS.items())
        svg = (f'<svg width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">'
               f'<defs>{markers}</defs>{"".join(self.lines)}</svg>')
        return (f'<!doctype html><html><head><meta charset="utf-8"><style>{STYLE}</style></head><body>'
                f'<div class="canvas" style="width:{self.width}px;height:{self.height}px">'
                f'{"".join(self.parts)}{svg}</div></body></html>')


def card(title: str, code: str = "", *lines: str) -> str:
    markup = f"<h3>{html.escape(title)}</h3>"
    if code:
        markup += f"<code>{html.escape(code)}</code>"
    return markup + "".join(f"<p>{html.escape(line)}</p>" for line in lines)


# ---------------------------------------------------------------- one step of the agent loop

FLOW = {
    "en": dict(
        title="Flutter × Jev", subtitle="One step of the agent: from reading the screen to acting on it",
        lanes=("Your machine · runner + app", "Jev · TypeSafe", "LLM · Gemini flash-lite"),
        steps=[
            ("Read the screen", "marionette lists the widgets; the runner compresses them to 337 characters.", "on your machine"),
            ("Build the options", "One action per widget: fill_email_field, tap_signin_button…", "on your machine"),
            ("Write the text", "Only for a new input field: the LLM writes what goes in it.", "~2.7 calls a run"),
            ("Pick one", "Jev picks one option, with a probability, and says whether the task is done.", "~0.23 s"),
            ("Check the floor", "Act if confidence clears the floor for this kind of step.", "on your machine"),
            ("Act, then loop", "Tap or type, wait for the screen to settle, back to step 1.", "on your machine"),
        ],
        stop="Unsure on a step that can be undone: ask the LLM to referee. Unsure on send or finish: stop, never lie.",
        foot="A full run: <b>one Jev call per step, the LLM only when it must</b> · about US$0.001 · "
             "judged by what the app stored, not by what the agent says",
    ),
    "zh-Hant": dict(
        title="Flutter × Jev", subtitle="agent 的一步怎麼跑：從讀畫面到做出動作",
        lanes=("你的電腦 · runner + app", "Jev · TypeSafe", "LLM · Gemini flash-lite"),
        steps=[
            ("讀畫面", "marionette 讀出元件，runner 壓成 337 字元的清單。", "在你的電腦"),
            ("組選項", "每個元件變成一個動作：fill_email_field、tap_signin_button…", "在你的電腦"),
            ("寫字", "只在遇到新的輸入欄位時叫，寫要填進去的字。", "一次跑約 2.7 次"),
            ("挑一個", "從選項裡挑一個、附機率，順便判斷做完了沒。", "約 0.23 秒"),
            ("過門檻", "信心過了這類動作的門檻才做。", "在你的電腦"),
            ("執行，再來一輪", "點擊或打字，等畫面穩定，回到第 1 步。", "在你的電腦"),
        ],
        stop="可回頭的步驟信心不夠：問 LLM 當裁判。送出、判定做完信心不夠：停下，不謊報。",
        foot="一次完整跑：<b>每步 1 次 Jev，LLM 只在必要時叫</b> · 約 US$0.001 · 判定看 app 真的寫進了什麼，不看 agent 自己說的",
    ),
}


def flow(language: str) -> str:
    w = FLOW[language]
    page = Page(1440, 1000)
    page.header(w["title"], w["subtitle"])
    lanes = [(128, 360), (502, 204), (720, 214)]            # top, height of each lane
    colors = ["#F4F4F5", "#8B7CFF", "#3FD0D8"]
    for (top, height), name, color in zip(lanes, w["lanes"], colors):
        page.add("", 40, top, 1360, height, "lane")
        page.add(f'<span class="dot" style="background:{color}"></span>{html.escape(name)}', 60, top + 16, cls="lane-name")
    rows = [0, 0, 2, 1, 0, 0]
    kinds = ["", "", "llm", "jev", "", ""]
    left, width, pitch = 64, 192, 222
    boxes = []
    for i, ((title, detail, when), row, kind) in enumerate(zip(w["steps"], rows, kinds)):
        top = lanes[row][0] + 52
        x = left + i * pitch
        extra = f'<div class="stop">{html.escape(w["stop"])}</div>' if i == 4 else ""
        page.add(f'<h3><span class="n">{i + 1}</span>{html.escape(title)}</h3><p>{html.escape(detail)}</p>'
                 f'<span class="chip">{html.escape(when)}</span>{extra}',
                 x, top, width, 150, f"card step {kind}".strip())
        boxes.append((x, top, width))
    for i in range(5):
        (x1, y1, w1), (x2, y2, _) = boxes[i], boxes[i + 1]
        a, b = (x1 + w1, y1 + 40), (x2, y2 + 40)
        mid = (a[0] + b[0]) / 2
        page.arrow([a, (mid, a[1]), (mid, b[1]), b], ["ink", "ink", "llm", "jev", "ink", "ink"][i + 1])
    # Step 6 goes back to step 1: the loop.
    x6, y6, w6 = boxes[5]
    x1, y1, w1 = boxes[0]
    loop_y = lanes[0][0] + lanes[0][1] - 24
    page.arrow([(x6 + w6 / 2, y6 + 150), (x6 + w6 / 2, loop_y), (x1 + w1 / 2, loop_y), (x1 + w1 / 2, y1 + 150)],
               "ink", dashed=True)
    page.add(f'<b style="color:#D4D4D8">{"next step" if language == "en" else "下一步"}</b>', 540, loop_y - 24, cls="label")
    page.add(w["foot"], 64, 952, cls="foot")
    return page.render()


# ---------------------------------------------------------------- the parts, and what leaves the machine

ARCH = {
    "en": dict(
        title="Flutter × Jev", subtitle="System design: the app, the runner and the verdict run locally. Two kinds of request leave.",
        mac="Your machine", mac_note="app, runner and judging all local", apps="Flutter app", runner="runner (Python)",
        outside="Outside your machine",
        app=("Boxtide demo app", "", "13 screens · every widget has a Key and an identifier"),
        marionette=("marionette_flutter", "ext.flutter.marionette.*", "read widgets · tap · type · screenshot"),
        store=("App store", "ext.flutter.boxtide.state", "orders, cart, addresses, tickets"),
        reader=("Read the screen", "transport.py", "one kept-open websocket, ~10 ms a call"),
        options=("Compress, list options", "elements.py", "5,488 → 337 characters · one action per widget"),
        loop=("Decision loop", "agent.py · run_jev", "ask Jev for the next step · risk-tiered floors",
              "LLM only for new fields, and to referee ties"),
        act=("Act", "transport.py", "tap / type / scroll, then wait for the screen to settle"),
        judge=("Judge", "arms.py", "read the store after the run; never trust the agent's own pass"),
        jev=("Jev · TypeSafe", "", "① screen + options → ② one pick + probability", "~0.23 s a decision · official key, direct"),
        llm=("LLM · Gemini flash-lite", "", "③ a new field → ④ the text to type", "⑤ Jev unsure → ⑥ its pick",
             "~2.7 calls a run"),
        read="widgets", listed="elements", options_l="screen + options", decided="an action", taps="tap, type",
        stored="after", leaves="<b>Only this leaves your machine:</b><br>the task sentence, the compressed screen and the options.",
    ),
    "zh-Hant": dict(
        title="Flutter × Jev", subtitle="系統架構：app、runner、判定都在本機，只有兩種請求會離開",
        mac="你的電腦", mac_note="app、runner、判定都在本機", apps="Flutter App", runner="Runner（Python）",
        outside="電腦之外",
        app=("Boxtide demo app", "", "13 個畫面 · 每個元件都有 Key 和 identifier"),
        marionette=("marionette_flutter", "ext.flutter.marionette.*", "讀元件 · 點擊 · 打字 · 截圖"),
        store=("App 的 store", "ext.flutter.boxtide.state", "訂單、購物車、地址、客服單"),
        reader=("讀畫面", "transport.py", "一條常駐 websocket，每次約 10 ms"),
        options=("壓縮、組選項", "elements.py", "5,488 → 337 字元 · 每個元件一個動作"),
        loop=("決策迴圈", "agent.py · run_jev", "問 Jev 下一步 · 按風險分級的門檻", "新欄位才叫 LLM 寫字，平手才叫它當裁判"),
        act=("執行動作", "transport.py", "點擊、打字、捲動，等畫面穩定"),
        judge=("判定", "arms.py", "跑完讀 store，不信 agent 自己說的 pass"),
        jev=("Jev · TypeSafe", "", "① 畫面 + 選項 → ② 挑一個 + 機率", "每個決策約 0.23 秒 · 官方 key 直連"),
        llm=("LLM · Gemini flash-lite", "", "③ 新欄位 → ④ 要填的字", "⑤ Jev 拿不定 → ⑥ 它選一個", "一次跑約 2.7 次"),
        read="元件", listed="元件清單", options_l="畫面 + 選項", decided="一個動作", taps="點擊、打字",
        stored="跑完之後", leaves="<b>離開電腦的只有：</b><br>任務句子、壓縮後的畫面和候選動作。",
    ),
}


def architecture(language: str) -> str:
    w = ARCH[language]
    page = Page(1440, 1010)
    page.header(w["title"], w["subtitle"])
    page.add("", 40, 136, 860, 844, "frame")
    page.add(f'{html.escape(w["mac"])}<i>{html.escape(w["mac_note"])}</i>', 64, 124, cls="tag")
    page.add(html.escape(w["apps"]), 72, 176, cls="caps")
    page.add(html.escape(w["runner"]), 448, 176, cls="caps")
    page.add(html.escape(w["outside"]), 1000, 176, cls="caps")

    # The Flutter app.
    ax, aw = 72, 300
    page.add(card(*w["app"]), ax, 204, aw, 84)
    page.add(card(*w["marionette"]), ax, 330, aw, 96)
    page.add(card(*w["store"]), ax, 852, aw, 96)
    # The runner, top to bottom.
    wx, ww = 448, 400
    rows = {"reader": (204, 92), "options": (332, 92), "loop": (460, 230), "act": (726, 92), "judge": (852, 96)}
    for key, (top, height) in rows.items():
        page.add(card(*w[key]), wx, top, ww, height, "card core" if key == "loop" else "card")
    # Outside.
    ox, ow = 1000, 360
    page.add(card(*w["jev"]), ox, 440, ow, 118, "card jev")
    page.add(card(*w["llm"]), ox, 590, ow, 140, "card llm")
    page.add(w["leaves"], ox, 760, ow, cls="foot")

    mid = wx + ww / 2
    # app -> marionette, marionette -> reader.
    page.arrow([(ax + aw / 2, 288), (ax + aw / 2, 330)])
    page.arrow([(ax + aw, 360), (410, 360), (410, 250), (wx, 250)])
    page.add(html.escape(w["read"]), 418, 300, cls="label")
    # Down the runner column.
    for (y1, y2), text in (((296, 332), w["listed"]), ((424, 460), w["options_l"]), ((690, 726), w["decided"])):
        page.arrow([(mid, y1), (mid, y2)])
        page.add(html.escape(text), mid + 12, (y1 + y2) / 2 - 9, cls="label")
    # Act goes back into the app through marionette; the loop repeats.
    page.arrow([(wx, 772), (390, 772), (390, 400), (ax + aw, 400)])
    page.add(html.escape(w["taps"]), 318, 748, cls="label")
    # The verdict reads the store.
    page.arrow([(ax + aw, 900), (wx, 900)])
    page.add(html.escape(w["stored"]), ax + aw + 12, 876, cls="label")

    # Across the machine's edge: requests solid, answers dashed.
    right = wx + ww
    for y, color, dashed, number in ((480, "jev", False, "①"), (516, "jev", True, "②"),
                                    (630, "llm", False, "③⑤"), (666, "llm", True, "④⑥")):
        start, end = ((right, y), (ox, y)) if not dashed else ((ox, y), (right, y))
        page.arrow([start, end], color, dashed)
        page.badge((right + ox) / 2, y, number, color)
    return page.render()


def render(markup: str, out: Path, width: int, height: int) -> None:
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "page.html"
        source.write_text(markup)
        command = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={folder}/profile",
                   "--force-device-scale-factor=2", f"--window-size={width},{height}", f"--screenshot={out}",
                   source.as_uri()]
        out.unlink(missing_ok=True)
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Headless Chrome writes the screenshot and then lingers; stop it once the file has settled.
        size, deadline = -1, time.time() + 45
        while time.time() < deadline and process.poll() is None:
            time.sleep(0.5)
            current = out.stat().st_size if out.exists() else -1
            if current > 0 and current == size:
                break
            size = current
        process.kill()
    if not out.exists():
        sys.exit(f"Chrome wrote no {out.name}")
    print(f"{out.relative_to(ROOT)} {out.stat().st_size // 1024} KB")


def main() -> None:
    for language in ("en", "zh-Hant"):
        render(flow(language), ROOT / f"docs/flow-{language}.png", 1440, 1000)
        render(architecture(language), ROOT / f"docs/architecture-{language}.png", 1440, 1010)


if __name__ == "__main__":
    main()
