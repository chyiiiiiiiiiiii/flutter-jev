#!/usr/bin/env python3.13
"""An LLM in Jev's seat, and an LLM that only writes the strings Jev cannot.

The decider is given the same screen, the same offered actions and the same
instructions Jev gets, so a comparison between them isolates the model. It is
also given the best structured-output setup Gemini has: a response schema whose
`action` is an enum of the offered ids. That is what a careful team would ship,
and it means an invalid pick is constrained away on this side too; the retry
count is kept to show whether that holds.

The writer is the other half of the hybrid. Jev picks every step, and the LLM
is asked only when a text field appears that has no value yet: once per new
set of fields, not once per step.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import aiohttp

from elements import Action, Element
from jev import CHOICE_INSTRUCTIONS, Decision

GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent?key={key}")

# Published rates, read off ai.google.dev/gemini-api/docs/pricing on
# 2026-09-22 (same table as singlecall/bench.py). Reasoning tokens bill as
# output whether or not they are shown.
RATES = {
    "gemini-3.1-flash-lite": (0.25 / 1e6, 1.50 / 1e6),
    "gemini-3.1-pro-preview": (2.00 / 1e6, 12.00 / 1e6),
}

FREE_TEXT = (
    " Some actions type into a field and leave the words to you: when you "
    "choose one of those, put exactly what to type in `text`."
)
CONFIDENCE = (
    " Also report `confidence`, from 0 to 1, that the chosen action is the "
    "right next step, and `taskComplete`, from 0 to 1, whether the screen "
    "shows the task already fully accomplished."
)

WRITER_BRIEF = (
    "You fill in text fields for a person using a mobile app. Given the task "
    "they want done and the fields on the current screen, say exactly what "
    "they would type into each field. Use details from the task wherever it "
    "gives them. Use an empty string for a field the task does not need, such "
    "as a search box that is not part of getting the task done."
)

# The first brief left a required field empty whenever the task did not spell
# out its contents ("add an address labelled Office" names no street), and the
# form could not be saved. A person would just make one up.
WRITER_BRIEF_V2 = WRITER_BRIEF + (
    " If a field is needed to finish the task but the task does not say what "
    "goes in it, write a plausible value a person would use."
)


class _Gemini:
    def __init__(self, model: str, think: bool) -> None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.model = model
        self.think = think
        self._url = GEMINI_URL.format(model=model, key=key)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session:
            await self._session.close()

    async def _call(self, system: str, user: str,
                    schema: dict[str, Any]) -> tuple[dict | None, dict, float]:
        assert self._session is not None
        config: dict[str, Any] = {
            "temperature": 0.0,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        }
        if not self.think:
            # Suppress reasoning so this tier is the LLM's fastest case.
            config["thinkingConfig"] = {"thinkingBudget": 0}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": config,
        }
        started = time.perf_counter()
        async with self._session.post(self._url, json=body) as response:
            payload = await response.json()
        elapsed = time.perf_counter() - started

        usage = payload.get("usageMetadata", {})
        text = ""
        try:
            for part in payload["candidates"][0]["content"]["parts"]:
                if not part.get("thought"):
                    text += part.get("text", "")
        except (KeyError, IndexError):
            pass
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if parsed is None and "error" in payload:
            raise RuntimeError(f"Gemini error: {json.dumps(payload)[:300]}")
        return parsed, usage, elapsed

    def _cost(self, usage: dict) -> tuple[int, int, float]:
        tin = int(usage.get("promptTokenCount", 0))
        tout = (int(usage.get("candidatesTokenCount", 0))
                + int(usage.get("thoughtsTokenCount", 0)))
        rate_in, rate_out = RATES[self.model]
        return tin, tout, tin * rate_in + tout * rate_out


class GeminiDecider(_Gemini):
    """Answers the same question Jev does, by writing JSON."""

    def __init__(self, model: str, think: bool, free_text: bool) -> None:
        super().__init__(model, think)
        self.free_text = free_text
        self.name = model

    async def decide(self, state: dict[str, Any],
                     actions: list[Action]) -> Decision:
        ids = [a.id for a in actions]
        props: dict[str, Any] = {
            "action": {"type": "STRING", "enum": ids},
            "confidence": {"type": "NUMBER"},
            "taskComplete": {"type": "NUMBER"},
        }
        if self.free_text:
            props["text"] = {"type": "STRING"}
        schema = {"type": "OBJECT", "properties": props,
                  "required": ["action", "confidence", "taskComplete"]}
        system = (CHOICE_INSTRUCTIONS
                  + (FREE_TEXT if self.free_text else "") + CONFIDENCE)
        user = json.dumps({
            "state": state,
            "options": {a.id: a.description for a in actions},
        })

        seconds = cost = 0.0
        tin = tout = retries = 0
        for attempt in range(3):
            parsed, usage, elapsed = await self._call(system, user, schema)
            i, o, c = self._cost(usage)
            seconds += elapsed
            tin += i
            tout += o
            cost += c
            if parsed and parsed.get("action") in ids:
                return Decision(
                    action_id=parsed["action"],
                    confidence=float(parsed.get("confidence", 0.0)),
                    complete=float(parsed.get("taskComplete", 0.0)),
                    probabilities={},
                    seconds=seconds, input_tokens=tin, output_tokens=tout,
                    cost=cost, text=parsed.get("text"), retries=retries,
                )
            retries += 1
        return Decision(action_id="", confidence=0.0, complete=0.0,
                        probabilities={}, seconds=seconds, input_tokens=tin,
                        output_tokens=tout, cost=cost, retries=retries)


class GeminiWriter(_Gemini):
    """Supplies the strings for text fields, and nothing else."""

    def __init__(self, model: str, brief: str = WRITER_BRIEF) -> None:
        super().__init__(model, think=False)
        self.brief = brief
        self.calls = 0
        self.seconds = 0.0
        self.cost = 0.0
        self.input_tokens = 0
        self.output_tokens = 0

    async def values_for(self, task: str, screen: str,
                         fields: list[Element]) -> dict[str, str]:
        names = [f.key or f.identifier or f.label for f in fields]
        schema = {
            "type": "OBJECT",
            "properties": {n: {"type": "STRING"} for n in names},
            "required": names,
        }
        user = json.dumps({"task": task, "screen": screen, "fields": names})
        parsed, usage, elapsed = await self._call(self.brief, user, schema)
        tin, tout, cost = self._cost(usage)
        self.calls += 1
        self.seconds += elapsed
        self.cost += cost
        self.input_tokens += tin
        self.output_tokens += tout
        return {n: str((parsed or {}).get(n, "")) for n in names}
