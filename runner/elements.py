#!/usr/bin/env python3.13
"""The screen model, and the compression that makes it affordable.

Marionette reports every property it knows about each element: controllers,
decorations, colour spaces, text scalers. A nine-element sign-in screen is
~4.7KB of it. Handing that to a model verbatim is the single biggest reason
agent-driven testing gets expensive, so this module decides what the model is
allowed to see.

Measured on the sign-in screen of the demo app: 1163 tokens raw, 80 compact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Types worth offering as an action. Everything else is context at best.
ACTIONABLE = {
    "TextField", "TextFormField", "CupertinoTextField", "EditableText",
    "ElevatedButton", "TextButton", "OutlinedButton", "FilledButton",
    "IconButton", "FloatingActionButton", "SegmentedButton",
    "ListTile", "CheckboxListTile", "SwitchListTile", "RadioListTile",
    "Checkbox", "Switch", "Radio", "InkWell", "GestureDetector",
    "NavigationDestination", "BottomNavigationBarItem", "Tab",
    "FilterChip", "ActionChip", "ChoiceChip", "Chip",
    "DropdownButton", "DropdownButtonFormField", "PopupMenuButton",
    "ExpansionTile",
}

TYPEABLE = {"TextField", "TextFormField", "CupertinoTextField", "EditableText"}

# Widgets whose tap flips a state rather than moving somewhere. Tapping one
# that is already in the wanted state undoes it, and marionette does not
# report which state that is.
TOGGLEABLE = {"Checkbox", "CheckboxListTile", "Switch", "SwitchListTile",
              "Radio", "RadioListTile"}

# Tapping one of these opens an overlay whose items marionette reports without
# keys, text or identifiers, so the menu is a dead end: nothing in it can be
# addressed and the run has nowhere to go. A dropdown already has a value
# selected, and changing it is a question about which value, which is not
# something a model that cannot emit a string gets to answer. So they are
# offered only when a value was supplied for them, same rule as a text field.
PICKABLE = {"DropdownButton", "DropdownButtonFormField",
            "DropdownButtonFormField<String>", "PopupMenuButton"}

# Pure presentation. Their text is context; they are never a target.
TEXTUAL = {"Text", "RichText", "SelectableText"}

# Keys whose taps move a form forward. Deliberately wider than the
# high-risk set in agent.py: "next" is not destructive, but it is still the
# button that says the form is currently valid, which is what these two rules
# need to know.
_ADVANCES = re.compile(
    r"signin|sign_in|submit|send|confirm|save|place_order|checkout|"
    r"next|continue|proceed|apply"
)

# Private-use codepoints are icon glyphs, which read as mojibake in a prompt.
_ICON_GLYPH = re.compile("[\ue000-\uf8ff]")

# A text field's current value is buried in its controller's toString,
# between the two box-drawing markers Flutter uses to delimit it.
_FIELD_VALUE = re.compile("TextEditingValue\\(text: \u2524(.*?)\u251c", re.DOTALL)


def _tidy(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", _ICON_GLYPH.sub("", value)).strip()


@dataclass(frozen=True)
class Element:
    type: str
    key: str | None
    identifier: str | None
    text: str
    enabled: bool
    visible: bool
    x: float
    y: float
    w: float
    h: float
    value: str = ""
    obscured: bool = False

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Element:
        bounds = raw.get("bounds") or {}
        controller = str(raw.get("controller") or "")
        found = _FIELD_VALUE.search(controller)
        return cls(
            type=str(raw.get("type", "")),
            key=raw.get("key") or None,
            identifier=raw.get("identifier") or None,
            text=_tidy(raw.get("text") or raw.get("data")),
            value=_tidy(found.group(1)) if found else "",
            obscured=str(raw.get("obscureText", "false")).lower() == "true",
            # Only widgets that can be disabled report `enabled`; a missing
            # field means "not that kind of widget", not "disabled".
            enabled=str(raw.get("enabled", "true")).lower() != "false",
            visible=bool(raw.get("visible", True)),
            x=float(bounds.get("x", 0) or 0),
            y=float(bounds.get("y", 0) or 0),
            w=float(bounds.get("width", 0) or 0),
            h=float(bounds.get("height", 0) or 0),
        )

    @property
    def addressable(self) -> bool:
        """Whether this element is worth offering as an action.

        A type allowlist alone is wrong in both directions. It misses an app's
        own composite widgets, which are exactly the ones carrying meaningful
        keys, and it admits the anonymous `InkWell` and `GestureDetector` that
        Flutter puts inside almost every tappable thing. Eight keyless
        `tap_gesturedetector` options crowd out the real ones and flatten the
        model's distribution, which shows up as low confidence on a choice
        that should have been obvious.

        So: a key or a Semantics identifier makes an element addressable
        whatever its type, and a known interactive type still needs a label
        to be worth naming.
        """
        if not self.visible or self.type in TEXTUAL:
            return False
        if self.w <= 0 or self.h <= 0:
            return False
        if self.key or self.identifier:
            return True
        return self.type in ACTIONABLE and bool(self.text)

    @property
    def typeable(self) -> bool:
        return self.type in TYPEABLE

    @property
    def label(self) -> str:
        """What to call this element when describing an action.

        Key names carry the meaning, which is the whole argument for naming
        them well: the agent's prompt is only as good as they are.
        """
        return self.key or self.identifier or self.text or self.type

    def selector(self) -> dict[str, str]:
        if self.key:
            return {"key": self.key}
        if self.identifier:
            return {"identifier": self.identifier}
        if self.text:
            return {"text": self.text}
        return {"type": self.type}

    def render(self, ref: str) -> str:
        bits = [f"{ref} {self.type}"]
        if self.key:
            bits.append(f"key={self.key}")
        elif self.identifier:
            bits.append(f"id={self.identifier}")
        if self.text and not self.typeable:
            bits.append(f'"{self.text}"')
        if self.typeable:
            # Without this the model cannot tell whether its last keystroke
            # landed, so it re-types or guesses at what to do next.
            if self.value:
                shown = "*" * len(self.value) if self.obscured else self.value
                bits.append(f'= "{shown}"')
            else:
                bits.append("= (empty)")
        if not self.enabled:
            bits.append("(disabled)")
        return " ".join(bits)


def parse(payload: dict[str, Any]) -> list[Element]:
    elements = [Element.from_json(e) for e in payload.get("elements", [])]
    # Reading order, so @eN numbering matches what a person would scan.
    return sorted(elements, key=lambda e: (round(e.y), round(e.x)))


def render_screen(elements: list[Element], max_copy: int = 20) -> tuple[str, list[Element]]:
    """Return the compact screen the model sees, and what `@eN` refers to."""
    targets = [e for e in elements if e.addressable]
    lines = [e.render(f"@e{i}") for i, e in enumerate(targets, start=1)]

    seen: dict[str, None] = {}
    for e in elements:
        if e.type in TEXTUAL and e.visible and e.text:
            seen.setdefault(e.text, None)
    if seen:
        lines.append("visible text: " + " | ".join(list(seen)[:max_copy]))

    return "\n".join(lines), targets


@dataclass(frozen=True)
class Action:
    id: str
    kind: str  # tap | fill | scroll | finish
    description: str
    element: Element | None = None
    text: str | None = None
    verdict: str | None = None


def build_actions(targets: list[Element], values: dict[str, str]) -> list[Action]:
    """Turn the screen into the closed set of things the model may choose.

    `values` supplies text for input fields, keyed by the field's key or label.
    Jev cannot generate a string, so an action carries its text already.
    """
    actions: list[Action] = []
    used: set[str] = set()

    def stable_id(prefix: str, el: Element, ref: str) -> str:
        """Name an action after what it touches, not where it sits.

        Positional ids (a1, a2, …) get renumbered whenever the set of offered
        actions changes, so `previousAction` stops lining up with the current
        options and the model loses the thread between steps.
        """
        base = f"{prefix}_{el.key or el.identifier or el.text or el.type}"
        base = re.sub(r"[^A-Za-z0-9_]+", "_", base).strip("_").lower()[:48]
        candidate = base or f"{prefix}_{ref.strip('@')}"
        while candidate in used:
            candidate += "_x"
        used.add(candidate)
        return candidate

    for i, el in enumerate(targets, start=1):
        ref = f"@e{i}"
        if not el.enabled:
            continue
        if el.typeable:
            value = values.get(el.key or "") or values.get(el.label, "")
            if value and el.value.strip() == value.strip():
                # Already filled; re-offering it invites a loop.
                continue
            if value:
                actions.append(Action(
                    id=stable_id("fill", el, ref), kind="fill",
                    element=el, text=value,
                    description=f'Type "{value}" into the empty '
                                f'{el.label} field at {ref}.',
                ))
            else:
                actions.append(Action(
                    id=stable_id("focus", el, ref), kind="tap", element=el,
                    description=f"Focus the text field {ref} ({el.label}).",
                ))
        elif el.type in PICKABLE or el.type.split("<")[0] in PICKABLE:
            wanted = values.get(el.key or "") or values.get(el.label, "")
            if not wanted:
                continue
            actions.append(Action(
                id=stable_id("pick", el, ref), kind="pick", element=el,
                text=wanted,
                description=f'Choose "{wanted}" in the {el.label} dropdown '
                            f'at {ref}.',
            ))
        else:
            label = f'"{el.text}"' if el.text else el.label
            actions.append(Action(
                id=stable_id("tap", el, ref), kind="tap", element=el,
                description=f"Tap {ref}, the {el.type} {label}.",
            ))

    def add(action: Action) -> None:
        actions.append(action)

    # Ordering that does not need a model. Every trace had the same waste in
    # it: the submit button was offered while a required field was still
    # empty, so the model pressed it, nothing happened, and a step was spent
    # discovering that. Which field to fill first is a judgement; that a form
    # must be filled before it is submitted is not.
    if any(a.kind == "fill" for a in actions):
        actions = [a for a in actions
                   if not (a.kind == "tap" and a.element is not None
                           and _ADVANCES.search(a.element.key or ""))]

    # Marionette reports a checkbox's key but not whether it is ticked, so the
    # model cannot see that a box is already in the state the task wants. Left
    # to itself it "helpfully" taps one that was pre-selected and thereby
    # clears it, then spends two more steps discovering that.
    #
    # The screen does carry the answer indirectly: a form whose commit button
    # is enabled is already valid, so nothing on it needs toggling. When that
    # button is disabled, a toggle is exactly what will enable it.
    # Only a real button counts as "the form is already valid". The
    # confirmation checkbox on the last step of the return flow is keyed
    # `return_confirm`, which matches the same pattern, so including toggles
    # here made that checkbox suppress itself and the run scrolled for ten
    # steps looking for a way forward that it had just hidden.
    commit_ready = any(
        e.enabled and _ADVANCES.search(e.key or "")
        for e in targets
        if e.key and not e.typeable and e.type not in TOGGLEABLE
    )
    if commit_ready:
        actions = [a for a in actions
                   if not (a.element is not None
                           and a.element.type in TOGGLEABLE)]

    add(Action(id="scroll", kind="scroll",
               description="Scroll down to reveal content below the fold."))
    add(Action(id="pass", kind="finish", verdict="pass",
               description="Stop and report success: the screen itself confirms "
                           "the task has been completed."))
    # "Cannot be done from here" is literally true on most screens along the
    # way, so saying that made giving up look correct at every step. This has
    # to mean "give up on the whole task", not "not on this screen".
    add(Action(id="fail", kind="finish", verdict="fail",
               description="Stop and report failure: the app is showing an "
                           "error, or the task is impossible no matter which "
                           "screens are visited next. Do not choose this "
                           "merely because the task is unfinished, or because "
                           "the next thing needed is on a different screen."))
    return actions
