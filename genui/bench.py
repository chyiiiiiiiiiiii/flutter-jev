#!/usr/bin/env python3.13
"""Measure the three ways to decide what interface to show next.

  generate  Gemini writes the whole A2UI surfaceUpdate payload, token by token.
            This is what Flutter's GenUI SDK does today with an LLM provider.
  select    Gemini is allowed only to name a surface from the catalogue.
  jev       Jev names a surface from the same catalogue.

`generate` against `select` isolates what writing the payload costs.
`select` against `jev` isolates what the model class costs, with the task held
fixed. Running only the first and last would confound the two.

  python3.13 bench.py --repeats 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import aiohttp

from catalog import DATA, SURFACES, TURNS

GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent?key={key}")
JEV_URL = "https://api.typesafe.ai/v1/systemone"

# Published rates. Jev bills input only; output is free.
JEV_INPUT_PER_TOKEN = 0.042 / 1_000_000

A2UI_BRIEF = """You are the interface layer of a customer support app.

Reply with a single A2UI `surfaceUpdate` JSON object and nothing else: no prose,
no markdown fence. Shape:

{"surfaceUpdate": {"surfaceId": "<surface name>", "components": [
  {"id": "<id>", "component": {"<ComponentType>": { ... }}}
]}}

Allowed surface names and what each is for:
%s

Component types you may use: Text (with `text.literalString` and `usageHint`
one of h1/h2/body/caption), Button (`label`, `action`), ListView (`items`),
Row, Column, Card, TextInput (`label`, `value`), Checkbox (`label`, `checked`),
DropdownInput (`label`, `options`), Timeline (`steps`), QuantityStepper.

Bind real values from this application state, quoting them exactly:
%s
"""

SELECT_BRIEF = """You are the interface layer of a customer support app.

Choose which single surface to render next for the customer's message. Reply
with the surface name only: no punctuation, no explanation.

Surfaces:
%s
"""


@dataclass
class Sample:
    mode: str
    turn: str
    expected: str
    chosen: str
    seconds: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    ok: bool
    raw: str = ""


@dataclass
class Group:
    mode: str
    samples: list[Sample] = field(default_factory=list)

    def stat(self, pick) -> dict[str, float]:
        values = [pick(s) for s in self.samples if s.ok]
        if not values:
            return {"median": 0.0, "p90": 0.0, "mean": 0.0}
        ordered = sorted(values)
        return {
            "median": statistics.median(ordered),
            "p90": ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))],
            "mean": statistics.mean(ordered),
        }


def _surface_lines() -> str:
    return "\n".join(f"- {name}: {why}" for name, why in SURFACES.items())


class Gemini:
    def __init__(self, model: str = GEMINI_MODEL) -> None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self._url = GEMINI_URL.format(model=model, key=key)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Gemini:
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session:
            await self._session.close()

    async def ask(self, system: str, message: str,
                  max_tokens: int) -> tuple[str, float, int, int]:
        assert self._session is not None
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": message}]}],
            "generationConfig": {"temperature": 0.0,
                                 "maxOutputTokens": max_tokens},
        }
        started = time.perf_counter()
        async with self._session.post(self._url, json=body) as response:
            payload = await response.json()
        elapsed = time.perf_counter() - started
        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            text = ""
        usage = payload.get("usageMetadata", {})
        return (text.strip(), elapsed,
                int(usage.get("promptTokenCount", 0)),
                int(usage.get("candidatesTokenCount", 0)))


class Jev:
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

    async def pick(self, message: str) -> tuple[str, float, int, int, float]:
        assert self._session is not None
        body = {
            "model": "jev-latest",
            "state": {"customerMessage": message, "appState": DATA},
            "questions": {
                "surface": {
                    "type": "choice",
                    "instructions": "Which single surface should the app render "
                                    "next in reply to `customerMessage`?",
                    "criteria": SURFACES,
                },
            },
        }
        started = time.perf_counter()
        async with self._session.post(JEV_URL, json=body) as response:
            raw = await response.text()
        elapsed = time.perf_counter() - started
        payload = json.loads(raw)
        if "answers" not in payload:
            raise RuntimeError(raw[:300])
        usage = payload.get("usage", {})
        confidence = float(payload["answers"]["surface"].get("confidence", 0))
        return (payload["answers"]["surface"]["choice"], elapsed,
                int(usage.get("input_tokens", 0)),
                int(usage.get("output_tokens", 0)), confidence)


def surface_from_payload(text: str) -> str:
    """Pull the surfaceId back out of whatever the model wrote."""
    cleaned = text.strip().removeprefix("```json").removeprefix("```")
    cleaned = cleaned.removesuffix("```").strip()
    try:
        return str(json.loads(cleaned)["surfaceUpdate"]["surfaceId"])
    except Exception:
        for name in SURFACES:
            if name in text:
                return name
        return ""


async def run(repeats: int) -> list[Sample]:
    samples: list[Sample] = []
    generate_brief = A2UI_BRIEF % (_surface_lines(),
                                   json.dumps(DATA, separators=(",", ":")))
    select_brief = SELECT_BRIEF % _surface_lines()

    async with Gemini() as gemini, Jev() as jev:
        for attempt in range(repeats):
            for turn, expected in TURNS:
                # 1. Gemini writes the whole payload.
                text, secs, tin, tout = await gemini.ask(
                    generate_brief, turn, max_tokens=2048)
                chosen = surface_from_payload(text)
                samples.append(Sample(
                    "generate", turn, expected, chosen, secs, tin, tout,
                    cost_usd=0.0, ok=bool(text), raw=text[:400]))

                # 2. Gemini only names a surface.
                text, secs, tin, tout = await gemini.ask(
                    select_brief, turn, max_tokens=16)
                chosen = next((n for n in SURFACES if n in text), "")
                samples.append(Sample(
                    "select", turn, expected, chosen, secs, tin, tout,
                    cost_usd=0.0, ok=bool(text), raw=text[:120]))

                # 3. Jev names a surface.
                choice, secs, tin, tout, conf = await jev.pick(turn)
                samples.append(Sample(
                    "jev", turn, expected, choice, secs, tin, tout,
                    cost_usd=tin * JEV_INPUT_PER_TOKEN, ok=True,
                    raw=f"confidence={conf:.2f}"))
            print(f"  pass {attempt + 1}/{repeats} done "
                  f"({len(TURNS)} turns × 3 modes)")
    return samples


def render(samples: list[Sample]) -> str:
    groups = {m: Group(m) for m in ("generate", "select", "jev")}
    for s in samples:
        groups[s.mode].samples.append(s)

    lines = [
        f"Gemini model: {GEMINI_MODEL} · {len(TURNS)} turns · "
        f"{len(samples) // 3 // len(TURNS)} repeats",
        "",
        "| mode | agrees with designer | median latency | p90 | median output tokens | median total tokens |",
        "|---|---|---|---|---|---|",
    ]
    for mode in ("generate", "select", "jev"):
        g = groups[mode]
        done = [s for s in g.samples if s.ok]
        agree = sum(1 for s in done if s.chosen == s.expected)
        lat = g.stat(lambda s: s.seconds)
        out = g.stat(lambda s: float(s.output_tokens))
        tot = g.stat(lambda s: float(s.input_tokens + s.output_tokens))
        lines.append(
            f"| {mode} | {agree}/{len(done)} | {lat['median'] * 1000:.0f}ms | "
            f"{lat['p90'] * 1000:.0f}ms | {out['median']:.0f} | "
            f"{tot['median']:.0f} |")

    lines += ["", "Where the modes disagree with the designer's expectation:", ""]
    seen: set[tuple[str, str, str]] = set()
    for s in samples:
        if s.ok and s.chosen != s.expected:
            k = (s.mode, s.turn, s.chosen)
            if k in seen:
                continue
            seen.add(k)
            lines.append(f"- `{s.mode}` on \"{s.turn}\" → "
                         f"`{s.chosen or 'unparseable'}` "
                         f"(expected `{s.expected}`)")
    return "\n".join(lines)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--out-dir", default="../results")
    args = p.parse_args()

    print(f"benchmarking {len(TURNS)} turns × 3 modes × {args.repeats} repeats")
    samples = await run(args.repeats)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (out / f"genui-samples-{stamp}.json").write_text(
        json.dumps([s.__dict__ for s in samples], indent=2))
    rendered = render(samples)
    (out / f"genui-{stamp}.md").write_text(rendered + "\n")
    print("\n" + rendered)
    print(f"\nwrote {out}/genui-{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
