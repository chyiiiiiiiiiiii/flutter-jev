#!/usr/bin/env python3.13
"""Drive the running Flutter app, either from a script or from Jev.

Both modes share one transport, so a comparison between them isolates the
decision layer instead of confounding it with how the app is reached.

  # hand-written baseline
  python3.13 agent.py scripted return-flow --uri ws://127.0.0.1:53954/x=/ws

  # same flow, described in a sentence
  python3.13 agent.py jev "open order 5207 and submit a return" --uri ...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from pathlib import Path

from elements import _ADVANCES, Action, build_actions, render_screen
from jev import Jev, Usage
from transport import Marionette, MarionetteError

# Confidence on a Choice measures how flat the distribution is, which means
# "no option is a clear winner" — not "the answer is wrong". Two actions that
# both make progress split the mass between them, so a single global threshold
# blocks perfectly good steps. TypeSafe's own guidance is to scale the
# threshold with what the action costs if it is wrong, so this is a risk table
# rather than a number.
CONFIDENCE_FLOOR = {
    "scroll": 0.20,   # nothing happens that a scroll back cannot undo
    "fill": 0.30,     # typing in a field is recoverable
    "tap": 0.35,      # navigation is recoverable
    "submit": 0.70,   # writes something the user would notice
    "finish": 0.60,   # a wrong verdict makes the whole test lie
}

# Keys whose taps commit something rather than just navigate.
COMMITTING = re.compile(
    r"submit|confirm|send|place_order|checkout|delete|remove|signout|"
    r"cancel_confirm|save"
)


def risk_of(kind: str, target: str) -> str:
    if kind == "tap" and COMMITTING.search(target or ""):
        return "submit"
    return kind

DEFAULT_VALUES = {
    "email_field": "demo@example.com",
    "password_field": "hunter2",
    "orders_search": "pour-over",
    "contact_order_field": "5213",
    "contact_message_field": "My parcel has not moved in four days.",
    "shop_search": "speaker",
    "support_search": "refund",
    "address_label_field": "Office",
    "address_lines_field": "9F, 100 Taiyuan Rd",
}

SCRIPTS: dict[str, list[tuple[str, dict[str, str], str]]] = {
    "return-flow": [
        ("fill", {"key": "email_field"}, "demo@example.com"),
        ("fill", {"key": "password_field"}, "hunter2"),
        ("tap", {"key": "signin_button"}, ""),
        ("tap", {"key": "nav_orders"}, ""),
        ("tap", {"key": "order_5207"}, ""),
        ("tap", {"key": "start_return_button"}, ""),
        ("tap", {"key": "return_next_button"}, ""),
        ("tap", {"key": "return_next_button"}, ""),
        ("tap", {"key": "return_confirm"}, ""),
        ("tap", {"key": "return_next_button"}, ""),
    ],
    "cart-flow": [
        ("fill", {"key": "email_field"}, "demo@example.com"),
        ("fill", {"key": "password_field"}, "hunter2"),
        ("tap", {"key": "signin_button"}, ""),
        ("tap", {"key": "nav_shop"}, ""),
        ("tap", {"key": "product_p-speaker"}, ""),
        # Both buttons sit in a bar pinned to the bottom of the product page.
        ("tap", {"key": "add_to_cart_button"}, ""),
        ("tap", {"key": "view_cart_button"}, ""),
    ],
    "support-flow": [
        ("fill", {"key": "email_field"}, "demo@example.com"),
        ("fill", {"key": "password_field"}, "hunter2"),
        ("tap", {"key": "signin_button"}, ""),
        ("tap", {"key": "nav_support"}, ""),
        ("scroll_to", {"key": "contact_us_button"}, ""),
        ("tap", {"key": "contact_us_button"}, ""),
        ("fill", {"key": "contact_order_field"}, "5213"),
        ("fill", {"key": "contact_message_field"},
         "My parcel has not moved in four days."),
        ("tap", {"key": "contact_send_button"}, ""),
    ],
    # The first version of the support script, kept so the failure it hits can
    # be reproduced on demand: contact_us_button sits below the FAQ list, off
    # screen, and marionette can only tap what is on screen.
    "support-flow-naive": [
        ("fill", {"key": "email_field"}, "demo@example.com"),
        ("fill", {"key": "password_field"}, "hunter2"),
        ("tap", {"key": "signin_button"}, ""),
        ("tap", {"key": "nav_support"}, ""),
        ("tap", {"key": "contact_us_button"}, ""),
        ("fill", {"key": "contact_order_field"}, "5213"),
        ("fill", {"key": "contact_message_field"},
         "My parcel has not moved in four days."),
        ("tap", {"key": "contact_send_button"}, ""),
    ],
    # A write-and-verify path: the interesting assertion is that the row is
    # there afterwards, not that a confirmation flashed up.
    "address-flow": [
        ("fill", {"key": "email_field"}, "demo@example.com"),
        ("fill", {"key": "password_field"}, "hunter2"),
        ("tap", {"key": "signin_button"}, ""),
        ("tap", {"key": "nav_account"}, ""),
        ("tap", {"key": "profile_addresses"}, ""),
        ("scroll_to", {"key": "add_address_button"}, ""),
        ("tap", {"key": "add_address_button"}, ""),
        ("fill", {"key": "address_label_field"}, "Office"),
        ("fill", {"key": "address_lines_field"}, "9F, 100 Taiyuan Rd"),
        ("tap", {"key": "address_save_button"}, ""),
    ],
}


class Report:
    def __init__(self, mode: str, label: str) -> None:
        self.mode = mode
        self.label = label
        self.steps = 0
        self.verdict = "incomplete"
        self.usage = Usage()
        self.transport_seconds = 0.0
        self.transport_calls = 0
        self.settle_seconds = 0.0
        self.settles = 0
        self.raw_chars = 0
        self.compact_chars = 0
        self.wall = 0.0
        self.empty_reads = 0
        self.writer_calls = 0
        self.writer_cost = 0.0
        self.writer_seconds = 0.0
        self.trace: list[dict[str, object]] = []

    @property
    def cost(self) -> float:
        return self.usage.cost + self.writer_cost

    def summary(self) -> str:
        lat = self.usage.latencies
        median = statistics.median(lat) if lat else 0.0
        lines = [
            f"  {self.verdict.upper()}",
            f"  steps {self.steps} · model calls {self.usage.calls} · "
            f"{self.usage.input_tokens} in / {self.usage.output_tokens} out "
            f"tokens · ${self.cost:.4f}",
            f"  wall {self.wall:.2f}s  "
            f"(model {self.usage.seconds:.2f}s, "
            f"settle {self.settle_seconds:.2f}s over {self.settles} waits, "
            f"transport {self.transport_seconds:.2f}s over "
            f"{self.transport_calls} calls)",
        ]
        if lat:
            lines.append(f"  median decision {median * 1000:.0f}ms · "
                         f"median transport call "
                         f"{self.transport_seconds / max(self.transport_calls, 1) * 1000:.0f}ms")
        if self.raw_chars:
            saved = 100 - self.compact_chars * 100 // max(self.raw_chars, 1)
            lines.append(f"  screen compression {self.raw_chars} → "
                         f"{self.compact_chars} chars ({saved}% smaller)")
        return "\n".join(lines)

    def to_json(self) -> dict[str, object]:
        lat = self.usage.latencies
        return {
            "mode": self.mode,
            "label": self.label,
            "verdict": self.verdict,
            "steps": self.steps,
            "model_calls": self.usage.calls,
            "input_tokens": self.usage.input_tokens,
            "output_tokens": self.usage.output_tokens,
            "cost_usd": round(self.cost, 6),
            "wall_seconds": round(self.wall, 3),
            "model_seconds": round(self.usage.seconds, 3),
            "transport_seconds": round(self.transport_seconds, 3),
            "transport_calls": self.transport_calls,
            "settle_seconds": round(self.settle_seconds, 3),
            "settles": self.settles,
            "median_decision_ms": round(statistics.median(lat) * 1000, 1) if lat else None,
            "retries": self.usage.retries,
            "empty_reads": self.empty_reads,
            "writer_calls": self.writer_calls,
            "writer_cost_usd": round(self.writer_cost, 6),
            "writer_seconds": round(self.writer_seconds, 3),
            "raw_chars": self.raw_chars,
            "compact_chars": self.compact_chars,
            "trace": self.trace,
        }


async def perform(app: Marionette, kind: str, selector: dict[str, str],
                  text: str, elements: list | None = None) -> None:
    if kind == "fill":
        await app.enter_text(selector, text)
    elif kind == "pick":
        # Open the menu, then reach the item by its visible text, which is the
        # only handle an overlay entry has.
        await app.tap(selector)
        await asyncio.sleep(0.35)
        await app.tap({"text": text})
    elif kind == "scroll_to":
        await app.scroll_to_key(selector["key"])
    elif kind == "scroll":
        await app.scroll(elements or [], up=True)
    else:
        await app.tap(selector)


async def perform_with_retry(app: Marionette, kind: str,
                             selector: dict[str, str], text: str,
                             elements: list, attempts: int = 6,
                             gap: float = 0.25) -> None:
    """What a real hand-written test does: wait for the target, then act.

    Without this the baseline is flaky at the shorter settle the Jev path
    uses, because a script reaches for one specific key and fails outright if
    the screen has not caught up. The agent tolerates a half-settled screen by
    choosing from whatever is actually on it, which is a real difference
    between the two approaches, but it is not a difference a fair timing
    comparison should be paying for.
    """
    last: MarionetteError | None = None
    for attempt in range(attempts):
        try:
            await perform(app, kind, selector, text, elements)
            return
        except MarionetteError as err:
            last = err
            await asyncio.sleep(gap)
            elements = await app.elements()
    raise last or MarionetteError("action never succeeded")


async def run_scripted(app: Marionette, flow: str) -> Report:
    report = Report("scripted", flow)
    steps = SCRIPTS[flow]
    print(f"scripted flow: {flow} ({len(steps)} hand-written steps)")
    started = time.perf_counter()

    before: tuple[int, ...] | None = None
    for i, (kind, selector, text) in enumerate(steps, start=1):
        # Identical settle policy to the Jev path. Tuning the wait on one side
        # only would have made the comparison measure my parameters rather
        # than the decision layer.
        elements = await app.changed_from(before)
        settled = await app.quiet_since(app.fingerprint(elements))
        if settled is not None:
            elements = settled
        before = app.fingerprint(elements)
        t0 = time.perf_counter()
        try:
            await perform_with_retry(app, kind, selector, text, elements)
        except MarionetteError as err:
            print(f"  step {i}: FAILED {kind} {selector}\n          {err}")
            report.trace.append({
                "step": i, "kind": kind,
                "target": selector.get("key", str(selector)),
                "at": round(time.perf_counter() - started, 3),
                "cost": 0.0, "failed": True,
            })
            report.verdict = "fail"
            report.steps = i
            report.wall = time.perf_counter() - started
            report.transport_seconds = app.call_seconds
            report.transport_calls = app.calls
            report.settle_seconds = app.settle_seconds
            report.settles = app.settles
            return report
        label = selector.get("key", str(selector))
        print(f"  step {i}: {kind} {label:32} "
              f"{(time.perf_counter() - t0) * 1000:6.0f}ms")
        report.trace.append({
            "step": i, "kind": kind, "target": label,
            "at": round(time.perf_counter() - started, 3),
            "cost": 0.0,
        })

    report.steps = len(steps)
    report.verdict = "pass"
    report.wall = time.perf_counter() - started
    report.transport_seconds = app.call_seconds
    report.transport_calls = app.calls
    report.settle_seconds = app.settle_seconds
    report.settles = app.settles
    return report


def offer_free_text(actions: list[Action]) -> list[Action]:
    """Let a decider that can write choose what goes into an empty field.

    Without a value table every text field is only offered as "focus", so
    this turns those into fills whose text the decider supplies, then applies
    the same fill-before-submit rule `build_actions` applies to table fills.
    """
    out = []
    for a in actions:
        el = a.element
        if a.id.startswith("focus_") and el is not None and not el.value:
            out.append(Action(
                id="fill" + a.id[len("focus"):], kind="fill", element=el,
                description=f"Type text of your choosing into the empty "
                            f"{el.label} field (put it in `text`)."))
        else:
            out.append(a)
    if any(a.kind == "fill" for a in out):
        out = [a for a in out
               if not (a.kind == "tap" and a.element is not None
                       and _ADVANCES.search(a.element.key or ""))]
    return out


async def run_jev(app: Marionette, task: str, values: dict[str, str],
                  max_steps: int, verbose: bool, *, decider=None,
                  writer=None, free_text: bool = False,
                  mode: str = "jev", on_step=None) -> Report:
    """The agent loop. Jev decides unless another `decider` is given.

    `writer`, when given, supplies text for fields the value table lacks, and
    `free_text` lets the decider write that text itself. `on_step`, when
    given, is awaited after every step with (step, action, decision), so a
    recorder can capture the screen that step left behind.
    """
    report = Report(mode, task)
    values = dict(values)
    asked: set[str] = set()
    print(f'{mode} task: "{task}"')
    started = time.perf_counter()
    previous_screen: str | None = None
    previous_action: str | None = None
    # Marionette reports a CheckboxListTile's key and bounds but not whether
    # it is checked, so the screen alone cannot tell the model that it already
    # ticked something. Without this it toggles the same box on and then off.
    history: list[str] = []

    async with (decider or Jev()) as model:
        before: tuple[int, ...] | None = None
        # An action the app ignores leaves the screen unchanged, so the same
        # action stays the best-looking option and the loop spins. Twenty
        # identical scrolls in one run is what this is here to stop.
        barren: dict[str, int] = {}
        stale = 0
        dismissed = False
        last_kind = ""
        step = 0
        while step < max_steps:
            step += 1
            # Overlapping the model call with the settle wait only pays off
            # when the screen settles quickly. A scroll keeps moving under
            # Flutter's momentum, so every overlapped decision after one was
            # discarded as stale and the run spent its budget re-reading.
            if last_kind == "scroll":
                elements = await app.settled_after(before)
                overlap = False
            else:
                elements = await app.changed_from(before)
                overlap = True
            screen, targets = render_screen(elements)
            if not targets:
                report.empty_reads += 1
                kinds = ", ".join(sorted({e.type for e in elements})) or "none"
                print(f"  step {step}: nothing addressable on screen "
                      f"({len(elements)} elements: {kinds})")
                # Most often this is an overlay whose entries carry no keys.
                # Dismissing it puts the run back on a screen it can act on,
                # which beats reporting a failure the app did not have.
                if not dismissed:
                    dismissed = True
                    print("          looks like an overlay; pressing escape")
                    try:
                        await app.press_key("escape")
                    except MarionetteError:
                        pass
                    before = None
                    step -= 1
                    continue
                report.verdict = "fail"
                break

            # Track what compression is buying, using the same field set the
            # CLI would have printed.
            report.raw_chars += sum(
                len(json.dumps(e.__dict__, default=str)) for e in elements)
            report.compact_chars += len(screen)

            if writer is not None:
                fresh = [t for t in targets if t.typeable
                         and (t.key or t.label) not in asked]
                if fresh:
                    asked.update(t.key or t.label for t in fresh)
                    before_cost = writer.cost
                    t0 = time.perf_counter()
                    wrote = await writer.values_for(task, screen, fresh)
                    report.writer_seconds += time.perf_counter() - t0
                    report.writer_calls += 1
                    report.writer_cost += writer.cost - before_cost
                    values.update({k: v for k, v in wrote.items() if v})
                    print(f"          writer: {wrote}")

            offered = build_actions(targets, values)
            if free_text:
                offered = offer_free_text(offered)
            actions = [a for a in offered if barren.get(a.id, 0) < 2]

            # Ask the model and confirm the screen has stopped moving at the
            # same time. Both are just waiting, and doing them in sequence was
            # the single largest avoidable cost in the loop: ~300ms of model
            # latency stacked on top of the settle wait on every step.
            state = {
                "task": task,
                "screen": screen,
                "previousScreen": previous_screen,
                "previousAction": previous_action,
                "actionsAlreadyTaken": history[-8:],
            }
            if overlap:
                thinking = asyncio.create_task(model.decide(state, actions))
                confirmed = await app.quiet_since(app.fingerprint(elements))
                decision = await thinking
            else:
                confirmed = elements
                decision = await model.decide(state, actions)
            report.usage.add(decision)

            if confirmed is None:
                # The screen moved on while the model was thinking, so the
                # answer is about a screen that no longer exists. One wasted
                # call is cheaper than acting on stale state.
                stale += 1
                step -= 1
                before = None
                print(f"          screen moved while deciding; re-reading "
                      f"({stale} in a row)")
                if stale > 3:
                    report.verdict = "fail"
                    break
                continue

            chosen = next((a for a in actions if a.id == decision.action_id), None)
            if chosen is None:
                print(f"  step {step}: model chose unknown action "
                      f"{decision.action_id!r}")
                report.verdict = "invalid"
                break

            typed = chosen.text or decision.text or ""
            print(f"  step {step}: {chosen.description}"
                  + (f'  ← "{typed}"' if chosen.kind == "fill"
                     and not chosen.text else ""))
            print(f"          {decision.seconds * 1000:.0f}ms · "
                  f"confidence {decision.confidence:.2f} · "
                  f"complete {decision.complete:.2f}")
            if verbose:
                top = sorted(decision.probabilities.items(),
                             key=lambda kv: -kv[1])[:3]
                print("          " + ", ".join(f"{k}={v:.2f}" for k, v in top))

            report.trace.append({
                "step": step,
                "action": chosen.description,
                "typed": typed if chosen.kind == "fill" else None,
                "target": (chosen.element.key if chosen.element else chosen.id),
                "kind": chosen.kind,
                "confidence": round(decision.confidence, 3),
                "complete": round(decision.complete, 3),
                "ms": round(decision.seconds * 1000, 1),
                "at": round(time.perf_counter() - started, 3),
                "cost": round(report.cost, 6),
            })
            report.steps = step

            target = chosen.element.key if chosen.element else chosen.id
            risk = risk_of(chosen.kind, target or "")
            floor = CONFIDENCE_FLOOR[risk]
            if decision.confidence < floor:
                print(f"          confidence {decision.confidence:.2f} below "
                      f"the {risk} floor of {floor}; stopping rather than "
                      f"guessing")
                report.verdict = "uncertain"
                break

            if chosen.kind == "finish":
                report.verdict = chosen.verdict or "unknown"
                if on_step is not None:
                    await on_step(step, chosen, decision, typed)
                break

            assert chosen.element is not None or chosen.kind == "scroll"
            selector = chosen.element.selector() if chosen.element else {}
            try:
                await perform(app, chosen.kind, selector, typed, elements)
            except MarionetteError as err:
                print(f"          action failed: {err}")
                report.verdict = "fail"
                break

            after = app.fingerprint(await app.elements())
            if after == app.fingerprint(elements):
                barren[chosen.id] = barren.get(chosen.id, 0) + 1
                print(f"          that changed nothing "
                      f"({barren[chosen.id]}x); it will not be offered again "
                      f"after one more try")
            else:
                barren.pop(chosen.id, None)

            if on_step is not None:
                await on_step(step, chosen, decision, typed)
            before = app.fingerprint(elements)
            previous_screen = screen
            previous_action = chosen.description
            last_kind = chosen.kind
            history.append(chosen.description if chosen.text or
                           chosen.kind != "fill"
                           else f'{chosen.description} Typed "{typed}".')
            stale = 0  # progress was made, so the budget resets
        else:
            print(f"  hit the {max_steps}-step cap")

    report.wall = time.perf_counter() - started
    report.transport_seconds = app.call_seconds
    report.transport_calls = app.calls
    report.settle_seconds = app.settle_seconds
    report.settles = app.settles
    return report


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["scripted", "jev", "overhead"])
    p.add_argument("target", nargs="?", default="")
    p.add_argument("--uri", required=True)
    p.add_argument("--value", action="append", default=[], metavar="KEY=TEXT")
    p.add_argument("--max-steps", type=int, default=25)
    p.add_argument("--restart", action="store_true",
                   help="hot restart the app first, for a clean starting state")
    p.add_argument("--chaos", type=int, default=0,
                   help="churn the app first: rename keys, swap labels, "
                        "reorder lists. 0 leaves it as the scripts expect")
    p.add_argument("--out", help="write the run report as JSON")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    values = {**DEFAULT_VALUES, **dict(v.split("=", 1) for v in args.value)}

    async with Marionette(args.uri) as app:
        if args.restart:
            await app.hot_restart()
            await asyncio.sleep(2.5)
        if args.chaos:
            churn = await app.set_chaos(args.chaos)
            print(f"chaos seed {args.chaos}: keys now end "
                  f"{churn.get('keySuffix')}, extra confirm step "
                  f"{churn.get('extraConfirmStep')}")
            await asyncio.sleep(0.6)

        if args.mode == "overhead":
            timings = []
            for _ in range(12):
                t0 = time.perf_counter()
                await app.elements()
                timings.append(time.perf_counter() - t0)
            print(f"persistent websocket, {len(timings)} interactiveElements calls")
            print(f"  min    {min(timings) * 1000:7.1f}ms")
            print(f"  median {statistics.median(timings) * 1000:7.1f}ms")
            print(f"  max    {max(timings) * 1000:7.1f}ms")
            return 0

        if args.mode == "scripted":
            if args.target not in SCRIPTS:
                print(f"unknown flow; try one of {', '.join(SCRIPTS)}",
                      file=sys.stderr)
                return 2
            report = await run_scripted(app, args.target)
        else:
            if not args.target:
                print("jev mode needs a task sentence", file=sys.stderr)
                return 2
            report = await run_jev(app, args.target, values, args.max_steps,
                                   args.verbose)

    print()
    print(report.summary())
    if args.out:
        Path(args.out).write_text(json.dumps(report.to_json(), indent=2))
        print(f"\n  report → {args.out}")
    return 0 if report.verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
