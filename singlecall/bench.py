#!/usr/bin/env python3.13
"""Where does the 40-200x actually live?

The UI-driving experiment could not reproduce TypeSafe's claimed multiplier,
and the report shows why: the model call was 30% of the wall time, so even an
instant model caps the end-to-end gain at 1.43x. Their claim is about a single
call, against a baseline of "3 to 329 seconds for frontier models".

So this measures a single call, on a task that is genuinely System One shaped:
triage a news item the way a digest pipeline has to. Three tiers, identical
task, only the model class changes.

  jev         one systemOne request, three typed questions answered in parallel
  flash-lite  the same three questions, emitted as JSON, thinking suppressed
  pro         the same three questions, emitted as JSON, thinking allowed

flash-lite against jev isolates the model class at minimum output length.
pro against jev is the comparison TypeSafe's number is actually about.

  python3.13 bench.py --repeats 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiohttp

JEV_URL = "https://api.typesafe.ai/v1/systemone"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent?key={key}")

# Published rates, read off the vendors' own pricing pages on 2026-09-22.
# Gemini: ai.google.dev/gemini-api/docs/pricing. The Pro tier is the
# "prompts <= 200k tokens" row, which is the one these prompts fall in.
# Jev: typesafe.ai — $0.042/MTok input, output free.
RATES = {
    # model: (input $/token, output $/token)
    "jev-latest": (0.042 / 1e6, 0.0),
    "gemini-3.1-flash-lite": (0.25 / 1e6, 1.50 / 1e6),
    "gemini-3.1-pro-preview": (2.00 / 1e6, 12.00 / 1e6),
}

# The three judgements a digest pipeline actually needs per item.
CATEGORIES = {
    "ai_ml": "AI, machine learning, models, training, inference",
    "infra": "infrastructure, databases, networking, operating systems",
    "languages": "programming languages, compilers, type systems, runtimes",
    "product": "a product launch, a company, funding, business of software",
    "security": "vulnerabilities, cryptography, privacy, incidents",
    "culture": "history, opinion, careers, community, anything else",
}
# A Score's levels are ordered, so its `criteria` is a list, not a map. The
# answer comes back as a continuous position on that axis (0..len-1) with the
# probability mass per level, not as one of the names.
DEPTH_LEVELS = [
    "a headline, an announcement, or an opinion with no detail",
    "enough detail that a working engineer could act on it",
    "a substantial technical explanation, paper, or teardown",
]
DEPTH_NAMES = ["shallow", "practical", "deep"]
DEPTH = dict(zip(DEPTH_NAMES, DEPTH_LEVELS))

TASK_BRIEF = """You triage items for a daily technical digest read by senior
engineers. For the item given, answer exactly three things and reply with only
a JSON object, no prose and no markdown fence:

{"include": true|false, "category": "<one of %s>", "depth": "<one of %s>"}

include: would a senior engineer want this in today's digest?
category: which bucket it belongs in.
depth: how much technical substance it carries.

Bucket meanings:
%s

Depth meanings:
%s
""" % (
    "|".join(CATEGORIES),
    "|".join(DEPTH),
    "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items()),
    "\n".join(f"- {k}: {v}" for k, v in DEPTH.items()),
)


@dataclass
class Sample:
    mode: str
    model: str
    item_id: int
    title: str
    seconds: float
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    cost_usd: float
    include: bool | None
    category: str
    depth: str
    ok: bool
    raw: str = ""


def cost_of(model: str, tin: int, tout: int) -> float:
    rate_in, rate_out = RATES.get(model, (0.0, 0.0))
    return tin * rate_in + tout * rate_out


class Jev:
    model = "jev-latest"

    def __init__(self) -> None:
        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise RuntimeError("TYPESAFE_API_KEY is not set")
        self._key = key
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Jev:
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._key}",
                     "Content-Type": "application/json"})
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session:
            await self._session.close()

    async def triage(self, item: dict) -> Sample:
        assert self._session is not None
        body = {
            "model": self.model,
            "state": {"item": item},
            "questions": {
                # All three answered in one request, sampled in parallel.
                "include": {
                    "type": "noul",
                    "instructions": "Would a senior engineer want this item in "
                                    "today's technical digest?",
                },
                "category": {
                    "type": "choice",
                    "instructions": "Which bucket does this item belong in?",
                    "criteria": CATEGORIES,
                },
                "depth": {
                    "type": "score",
                    "instructions": "How much technical substance does this "
                                    "item carry?",
                    "criteria": DEPTH_LEVELS,
                },
            },
        }
        started = time.perf_counter()
        async with self._session.post(JEV_URL, json=body) as response:
            raw = await response.text()
        elapsed = time.perf_counter() - started
        payload = json.loads(raw)
        if "answers" not in payload:
            return Sample("jev", self.model, item["id"], item["title"], elapsed,
                          0, 0, 0, 0.0, None, "", "", False, raw[:300])
        a = payload["answers"]
        usage = payload.get("usage", {})
        tin = int(usage.get("input_tokens", 0))
        tout = int(usage.get("output_tokens", 0))
        return Sample(
            "jev", self.model, item["id"], item["title"], elapsed, tin, tout, 0,
            cost_of(self.model, tin, tout),
            a["include"]["noul"] >= 0.5,
            a["category"]["choice"],
            # Round the continuous score back onto a level name so it can be
            # compared with the categorical answer the LLM has to emit.
            DEPTH_NAMES[min(len(DEPTH_NAMES) - 1,
                            max(0, round(float(a["depth"]["score"]))))],
            True,
        )


class Gemini:
    def __init__(self, model: str, think: bool) -> None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.model = model
        self.think = think
        self._url = GEMINI_URL.format(model=model, key=key)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Gemini:
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session:
            await self._session.close()

    async def triage(self, item: dict) -> Sample:
        assert self._session is not None
        config: dict = {"temperature": 0.0, "maxOutputTokens": 2048}
        if not self.think:
            # Suppress reasoning so this tier is the LLM's best case.
            config["thinkingConfig"] = {"thinkingBudget": 0}
        body = {
            "systemInstruction": {"parts": [{"text": TASK_BRIEF}]},
            "contents": [{"role": "user",
                          "parts": [{"text": json.dumps(item)}]}],
            "generationConfig": config,
        }
        started = time.perf_counter()
        async with self._session.post(self._url, json=body) as response:
            payload = await response.json()
        elapsed = time.perf_counter() - started

        text = ""
        try:
            for part in payload["candidates"][0]["content"]["parts"]:
                text += part.get("text", "")
        except (KeyError, IndexError):
            pass
        usage = payload.get("usageMetadata", {})
        tin = int(usage.get("promptTokenCount", 0))
        tout = int(usage.get("candidatesTokenCount", 0))
        thought = int(usage.get("thoughtsTokenCount", 0))

        include = category = depth = None
        cleaned = text.strip().removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()
        try:
            parsed = json.loads(cleaned)
            include = bool(parsed.get("include"))
            category = str(parsed.get("category", ""))
            depth = str(parsed.get("depth", ""))
        except Exception:
            pass

        mode = "pro" if self.think else "flash-lite"
        # Reasoning tokens are billed as output whether or not they are shown.
        return Sample(
            mode, self.model, item["id"], item["title"], elapsed,
            tin, tout, thought,
            cost_of(self.model, tin, tout + thought),
            include, category or "", depth or "",
            include is not None, text[:200],
        )


async def run(items: list[dict], repeats: int) -> list[Sample]:
    samples: list[Sample] = []
    async with (Jev() as jev,
                Gemini("gemini-3.1-flash-lite", think=False) as fast,
                Gemini("gemini-3.1-pro-preview", think=True) as pro):
        for attempt in range(1, repeats + 1):
            for item in items:
                # Sequential on purpose: a concurrent race would measure the
                # event loop as much as the services.
                samples.append(await jev.triage(item))
                samples.append(await fast.triage(item))
                samples.append(await pro.triage(item))
            print(f"  pass {attempt}/{repeats} done "
                  f"({len(items)} items x 3 tiers)")
    return samples


def render(samples: list[Sample], items: list[dict]) -> str:
    by: dict[str, list[Sample]] = {}
    for s in samples:
        by.setdefault(s.mode, []).append(s)

    order = ["jev", "flash-lite", "pro"]
    jev_lat = statistics.median(s.seconds for s in by["jev"] if s.ok)
    jev_cost = statistics.mean(s.cost_usd for s in by["jev"] if s.ok)

    lines = [
        f"{len(items)} real Hacker News items x {len(by['jev']) // len(items)} "
        f"repeats, one call per item per tier.",
        "",
        "| tier | model | n | median | p90 | median out tokens | "
        "thought tokens | $/call | faster than | cheaper than |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for mode in order:
        ok = [s for s in by.get(mode, []) if s.ok]
        if not ok:
            continue
        lat = sorted(s.seconds for s in ok)
        p90 = lat[min(len(lat) - 1, int(len(lat) * 0.9))]
        med = statistics.median(lat)
        out = statistics.median(s.output_tokens for s in ok)
        thought = statistics.median(s.thought_tokens for s in ok)
        cost = statistics.mean(s.cost_usd for s in ok)
        speed = "—" if mode == "jev" else f"{med / jev_lat:.1f}x slower"
        money = "—" if mode == "jev" else f"{cost / jev_cost:.1f}x dearer"
        lines.append(
            f"| {mode} | `{ok[0].model}` | {len(ok)} | {med * 1000:.0f}ms | "
            f"{p90 * 1000:.0f}ms | {out:.0f} | {thought:.0f} | "
            f"${cost:.6f} | {speed} | {money} |")

    lines += ["", "Agreement between tiers, on the questions where they can be "
                  "compared:", ""]
    keyed: dict[tuple[str, int], Sample] = {}
    for s in samples:
        if s.ok:
            keyed.setdefault((s.mode, s.item_id), s)
    both = [i["id"] for i in items
            if ("jev", i["id"]) in keyed and ("pro", i["id"]) in keyed]
    for field in ("include", "category"):
        same = sum(1 for i in both
                   if getattr(keyed[("jev", i)], field)
                   == getattr(keyed[("pro", i)], field))
        lines.append(f"- jev vs pro on `{field}`: {same}/{len(both)} agree")
    for field in ("include", "category"):
        same = sum(1 for i in both
                   if ("flash-lite", i) in keyed
                   and getattr(keyed[("jev", i)], field)
                   == getattr(keyed[("flash-lite", i)], field))
        lines.append(f"- jev vs flash-lite on `{field}`: {same}/{len(both)} agree")
    return "\n".join(lines)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--items", default="/tmp/hn_items.json")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--out-dir", default="../results")
    args = p.parse_args()

    items = json.loads(Path(args.items).read_text())[:args.limit]
    print(f"{len(items)} items x 3 tiers x {args.repeats} repeats")
    samples = await run(items, args.repeats)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (out / f"singlecall-samples-{stamp}.json").write_text(
        json.dumps([s.__dict__ for s in samples], indent=2))
    rendered = render(samples, items)
    (out / f"singlecall-{stamp}.md").write_text(rendered + "\n")
    print("\n" + rendered)
    print(f"\nwrote {out}/singlecall-{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
