#!/usr/bin/env python3.13
"""Drive a running Flutter app with Jev decisions.

The loop is the whole idea: marionette reports what is on screen, this file turns
that into a closed list of legal actions, Jev picks one, marionette executes it.
Jev never generates a string, so any text that gets typed is supplied here.

  python3.13 jev_agent.py --uri ws://127.0.0.1:8181/ws "sign in and open the orders tab"
  python3.13 jev_agent.py --fixture fixtures/signin.txt "sign in"   # no app needed
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field

API_HOST = "api.typesafe.ai"
API_PATH = "/v1/systemone"
MODEL = "jev-latest"

# $0.042 per million input tokens, output free.
INPUT_COST_PER_TOKEN = 0.042 / 1_000_000

# Below this the model is guessing. Better to stop and say so than to flail.
MIN_CONFIDENCE = 0.55

ELEMENT_RE = re.compile(r"^Type:\s*(?P<type>[^,]+?)(?:,\s*Key:\s*\"(?P<key>[^\"]*)\")?"
                        r"(?:,\s*Identifier:\s*\"(?P<identifier>[^\"]*)\")?"
                        r"(?:,\s*Text:\s*\"(?P<text>[^\"]*)\")?\s*$")

TAPPABLE = {
    "ElevatedButton", "TextButton", "OutlinedButton", "IconButton", "FilledButton",
    "InkWell", "GestureDetector", "ListTile", "Checkbox", "Switch", "Radio",
    "Tab", "NavigationDestination", "BottomNavigationBarItem", "Chip", "ActionChip",
    "FloatingActionButton", "PopupMenuButton", "DropdownButton", "Card",
}
TYPEABLE = {"TextField", "TextFormField", "CupertinoTextField", "EditableText"}


@dataclass
class Element:
    type: str
    key: str | None = None
    identifier: str | None = None
    text: str | None = None

    @property
    def label(self) -> str:
        return self.text or self.identifier or self.key or self.type

    def selector(self) -> tuple[str, str]:
        """marionette prefers key, then Semantics identifier, then visible text."""
        if self.key:
            return "--key", self.key
        if self.identifier:
            return "--identifier", self.identifier
        if self.text:
            return "--text", self.text
        return "--type", self.type

    def render(self, ref: str) -> str:
        parts = [f"{ref} [{self.type}]"]
        if self.key:
            parts.append(f'key="{self.key}"')
        if self.identifier:
            parts.append(f'id="{self.identifier}"')
        if self.text:
            parts.append(f'"{self.text}"')
        return " ".join(parts)


@dataclass
class Action:
    id: str
    kind: str  # press | fill | scroll | finish
    description: str
    element: Element | None = None
    text: str | None = None
    verdict: str | None = None  # finish actions only


@dataclass
class Metrics:
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_seconds: float = 0.0
    device_seconds: float = 0.0
    step_latencies: list[float] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return self.input_tokens * INPUT_COST_PER_TOKEN

    def summary(self, total: float, steps: int) -> str:
        lat = self.step_latencies
        median = sorted(lat)[len(lat) // 2] if lat else 0.0
        return (
            f"steps {steps} · model calls {self.model_calls} · "
            f"{self.input_tokens} in / {self.output_tokens} out tokens · "
            f"${self.cost_usd:.4f}\n"
            f"wall {total:.2f}s  (model {self.model_seconds:.2f}s, "
            f"device {self.device_seconds:.2f}s)  median decision "
            f"{median * 1000:.0f}ms"
        )


def parse_elements(text: str) -> list[Element]:
    """Parse `marionette get-interactive-elements` stdout.

    The CLI prints a human-readable line per element, so this is the one place
    that has to care about its exact wording.
    """
    elements: list[Element] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("Type:"):
            continue
        m = ELEMENT_RE.match(line)
        if not m:
            continue
        elements.append(Element(
            type=m.group("type").strip(),
            key=m.group("key") or None,
            identifier=m.group("identifier") or None,
            text=m.group("text") or None,
        ))
    return elements


def build_actions(elements: list[Element], values: dict[str, str]) -> list[Action]:
    """Turn the screen into the closed set of things Jev is allowed to pick.

    `values` supplies the text for input fields, keyed by the field's key,
    identifier or label. Jev selects an action that already carries its string.
    """
    actions: list[Action] = []
    for i, el in enumerate(elements, start=1):
        ref = f"@e{i}"
        if el.type in TYPEABLE:
            value = (values.get(el.key or "") or values.get(el.identifier or "")
                     or values.get(el.label, ""))
            if value:
                actions.append(Action(
                    id=f"a{len(actions) + 1}", kind="fill", element=el, text=value,
                    description=f'Type "{value}" into the {el.type} {ref} ({el.label}).',
                ))
            else:
                actions.append(Action(
                    id=f"a{len(actions) + 1}", kind="press", element=el,
                    description=f"Focus the {el.type} {ref} ({el.label}).",
                ))
        elif el.type in TAPPABLE or el.text:
            actions.append(Action(
                id=f"a{len(actions) + 1}", kind="press", element=el,
                description=f'Tap the {el.type} {ref} labelled "{el.label}".',
            ))

    actions.append(Action(id="scroll", kind="scroll",
                          description="Scroll down to reveal content below the fold."))
    actions.append(Action(id="pass", kind="finish", verdict="pass",
                          description="The task is complete and verified on screen."))
    actions.append(Action(id="fail", kind="finish", verdict="fail",
                          description="The task cannot be completed; something is wrong."))
    return actions


class Jev:
    """One kept-alive connection, so the reported latency is the model's own."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key
        self._conn = http.client.HTTPSConnection(API_HOST, timeout=30)

    def decide(self, state: dict, actions: list[Action]) -> tuple[dict, dict, float]:
        body = json.dumps({
            "model": MODEL,
            "state": state,
            "questions": {
                "nextAction": {
                    "type": "choice",
                    "instructions": (
                        "Choose the single next action that makes progress on `task`, "
                        "given what is currently on `screen`. Prefer an action that "
                        "changes the screen. Do not repeat `previousAction` unless the "
                        "screen shows it had no effect."
                    ),
                    "criteria": {a.id: a.description for a in actions},
                },
                "taskComplete": {
                    "type": "noul",
                    "instructions": (
                        "Judging only from `screen`, has `task` already been fully "
                        "accomplished?"
                    ),
                },
            },
        })
        started = time.perf_counter()
        self._conn.request("POST", API_PATH, body=body, headers={
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        })
        raw = self._conn.getresponse().read()
        elapsed = time.perf_counter() - started
        payload = json.loads(raw)
        if "answers" not in payload:
            raise RuntimeError(f"TypeSafe API error: {raw.decode()[:400]}")
        return payload["answers"], payload.get("usage", {}), elapsed


class Device:
    """The marionette side. Swap this class to drive something other than Flutter."""

    def __init__(self, uri: str) -> None:
        self._base = ["marionette", "--uri", uri]

    def _run(self, *args: str) -> str:
        out = subprocess.run([*self._base, *args], capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"marionette {' '.join(args)} failed: {out.stderr.strip()}")
        return out.stdout

    def snapshot(self) -> str:
        return self._run("get-interactive-elements")

    def perform(self, action: Action) -> None:
        if action.kind == "scroll":
            self._run("swipe", "--type", "Scrollable", "--direction", "up")
            return
        assert action.element is not None
        flag, value = action.element.selector()
        if action.kind == "fill":
            self._run("enter-text", flag, value, "--input", action.text or "")
        else:
            self._run("tap", flag, value)


class Fixture:
    """Replays canned screens so the decision logic can be tested without a device."""

    def __init__(self, path: str) -> None:
        self._screens = [s for s in open(path).read().split("\n---\n") if s.strip()]
        self._i = 0

    def snapshot(self) -> str:
        return self._screens[min(self._i, len(self._screens) - 1)]

    def perform(self, action: Action) -> None:
        self._i += 1


def run(task: str, device, values: dict[str, str], max_steps: int, verbose: bool) -> int:
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        print("TYPESAFE_API_KEY is not set", file=sys.stderr)
        return 2

    jev = Jev(key)
    metrics = Metrics()
    started = time.perf_counter()
    previous_screen = None
    previous_action = None
    verdict = "incomplete"

    for step in range(1, max_steps + 1):
        t0 = time.perf_counter()
        snapshot_text = device.snapshot()
        metrics.device_seconds += time.perf_counter() - t0

        elements = parse_elements(snapshot_text)
        if not elements:
            print(f"  step {step}: no interactive elements found, stopping")
            verdict = "fail"
            break

        actions = build_actions(elements, values)
        screen = "\n".join(el.render(f"@e{i}")
                           for i, el in enumerate(elements, start=1))

        answers, usage, model_s = jev.decide({
            "task": task,
            "screen": screen,
            "previousScreen": previous_screen,
            "previousAction": previous_action,
        }, actions)

        metrics.model_calls += 1
        metrics.input_tokens += usage.get("input_tokens", 0)
        metrics.output_tokens += usage.get("output_tokens", 0)
        metrics.model_seconds += model_s
        metrics.step_latencies.append(model_s)

        pick = answers["nextAction"]
        chosen = next(a for a in actions if a.id == pick["choice"])
        complete = answers["taskComplete"]["noul"]

        print(f"  step {step}: {chosen.description}")
        print(f"          {model_s * 1000:.0f}ms · confidence {pick['confidence']:.2f}"
              f" · complete {complete:.2f}")
        if verbose:
            top = sorted(pick["probabilities"].items(), key=lambda kv: -kv[1])[:3]
            print("          " + ", ".join(f"{k}={v:.2f}" for k, v in top))

        if pick["confidence"] < MIN_CONFIDENCE:
            print(f"          confidence below {MIN_CONFIDENCE}, stopping rather than guessing")
            verdict = "uncertain"
            break

        if chosen.kind == "finish":
            verdict = chosen.verdict or "unknown"
            break

        t0 = time.perf_counter()
        device.perform(chosen)
        metrics.device_seconds += time.perf_counter() - t0

        previous_screen = screen
        previous_action = chosen.description
    else:
        verdict = "incomplete"
        print(f"  hit the {max_steps}-step cap")

    total = time.perf_counter() - started
    print(f"\n  {verdict.upper()}")
    print("  " + metrics.summary(total, metrics.model_calls).replace("\n", "\n  "))
    return 0 if verdict == "pass" else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("task")
    p.add_argument("--uri", help="VM service URI from `flutter run`")
    p.add_argument("--fixture", help="replay canned screens instead of a live app")
    p.add_argument("--value", action="append", default=[],
                   metavar="KEY=TEXT", help="text to type into a field, repeatable")
    p.add_argument("--max-steps", type=int, default=25)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    if not args.uri and not args.fixture:
        p.error("pass --uri or --fixture")

    values = dict(v.split("=", 1) for v in args.value)
    device = Fixture(args.fixture) if args.fixture else Device(args.uri)

    print(f'task: "{args.task}"')
    return run(args.task, device, values, args.max_steps, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
