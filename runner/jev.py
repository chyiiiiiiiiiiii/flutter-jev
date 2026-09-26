#!/usr/bin/env python3.13
"""The decision layer, and an LLM stand-in to compare it against.

Jev answers a Choice and a Noul in the same request, so asking "which action"
and "are we done" costs one round trip rather than two. The Choice options are
built from the screen, which is what makes a wrong answer structurally
impossible: it can only pick an action the code already offered.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from elements import Action

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"

# $0.042 per million input tokens, output free.
JEV_INPUT_COST = 0.042 / 1_000_000

CHOICE_INSTRUCTIONS = (
    "Choose the single next action that makes progress on `task`, given what is "
    "currently on `screen`. Prefer an action that changes the screen. Do not "
    "repeat `previousAction` unless the screen shows it had no effect. "
    "If the screen shows a form field that is still empty and the task needs "
    "it, fill that field before pressing a submit or confirm button. "
    "`actionsAlreadyTaken` lists what has been done so far; a checkbox or "
    "switch already toggled there is already in the state the task wants, so "
    "do not toggle it again. "
    "Choose `pass` only when the screen itself confirms the task is done."
)
NOUL_INSTRUCTIONS = (
    "Judging only from `screen`, has `task` already been fully accomplished?"
)


@dataclass
class Decision:
    action_id: str
    confidence: float
    complete: float
    probabilities: dict[str, float]
    seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    # Set by deciders that price output or reasoning; Jev bills input only.
    cost: float | None = None
    # A decider that writes may also supply the text to type.
    text: str | None = None
    # Answers thrown away because they did not parse or named no offered action.
    retries: int = 0


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    cost: float = 0.0
    retries: int = 0
    latencies: list[float] = field(default_factory=list)

    def add(self, d: Decision) -> None:
        self.cost += (d.cost if d.cost is not None
                      else d.input_tokens * JEV_INPUT_COST)
        self.retries += d.retries
        self.calls += 1
        self.input_tokens += d.input_tokens
        self.output_tokens += d.output_tokens
        self.seconds += d.seconds
        self.latencies.append(d.seconds)


class Jev:
    name = "jev"

    def __init__(self) -> None:
        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise RuntimeError("TYPESAFE_API_KEY is not set")
        self._key = key
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Jev:
        # One session, so the reported latency is the model's and not TLS setup.
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._key}",
                     "Content-Type": "application/json"})
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session:
            await self._session.close()

    @property
    def cost_per_input_token(self) -> float:
        return JEV_INPUT_COST

    async def decide(self, state: dict[str, Any],
                     actions: list[Action]) -> Decision:
        assert self._session is not None
        body = {
            "model": JEV_MODEL,
            "state": state,
            "questions": {
                "nextAction": {
                    "type": "choice",
                    "instructions": CHOICE_INSTRUCTIONS,
                    "criteria": {a.id: a.description for a in actions},
                },
                "taskComplete": {"type": "noul",
                                 "instructions": NOUL_INSTRUCTIONS},
            },
        }
        started = time.perf_counter()
        async with self._session.post(JEV_URL, json=body) as response:
            raw = await response.text()
        elapsed = time.perf_counter() - started
        payload = json.loads(raw)
        if "answers" not in payload:
            raise RuntimeError(f"TypeSafe API error: {raw[:400]}")

        pick = payload["answers"]["nextAction"]
        usage = payload.get("usage", {})
        return Decision(
            action_id=pick["choice"],
            confidence=float(pick.get("confidence", 0.0)),
            complete=float(payload["answers"]["taskComplete"]["noul"]),
            probabilities={k: float(v) for k, v in
                           (pick.get("probabilities") or {}).items()},
            seconds=elapsed,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
