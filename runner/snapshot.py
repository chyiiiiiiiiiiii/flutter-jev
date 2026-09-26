#!/usr/bin/env python3.13
"""Parse and compress `marionette get-interactive-elements` output.

Marionette prints every property it knows about each element: controllers,
decorations, colour spaces, text scalers. A nine-element sign-in screen comes
to ~4.7KB, and an orders list several times that. Feeding that to a model
verbatim is what makes agent-driven testing expensive, so this module is the
part that decides what the model is allowed to see.

Run it directly against a live app to eyeball the compression:

  python3.13 snapshot.py --uri ws://127.0.0.1:53954/xxx=/ws
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass

# A record starts at a line-initial "Type:" and runs until the next one, since
# a Text element's value can contain newlines.
RECORD_SPLIT = re.compile(r"^Type:\s*", re.MULTILINE)

FIELD = {
    "type": re.compile(r"^([A-Za-z_<>\[\]]+)"),
    "key": re.compile(r'\bKey:\s*"([^"]*)"'),
    "identifier": re.compile(r'\bidentifier:\s*"([^"]*)"'),
    "enabled": re.compile(r'\benabled:\s*"(true|false)"'),
    "visible": re.compile(r"\bvisible:\s*(true|false)"),
    "bounds": re.compile(r"\bbounds:\s*(\{[^}]*\})"),
    # Text is quoted and may span lines; stop at the next ", <field>: ".
    "text": re.compile(r'\bText:\s*"(.*?)"(?=,\s*[a-zA-Z]+:\s|\s*$)', re.DOTALL),
}

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
    "ExpansionTile", "Card", "RefreshIndicator",
}

TYPEABLE = {"TextField", "TextFormField", "CupertinoTextField", "EditableText"}

# Pure presentation; their text is context, they are never a target.
TEXTUAL = {"Text", "RichText", "SelectableText"}


@dataclass
class Element:
    type: str
    key: str | None
    identifier: str | None
    text: str | None
    enabled: bool
    visible: bool
    x: float
    y: float
    w: float
    h: float

    @property
    def actionable(self) -> bool:
        return self.type in ACTIONABLE and self.visible and self.enabled

    @property
    def typeable(self) -> bool:
        return self.type in TYPEABLE

    @property
    def label(self) -> str:
        """What to call this element when describing an action.

        Key names carry the meaning here, which is the whole argument for
        naming them well: the agent's prompt is only as good as they are.
        """
        return self.key or self.identifier or (self.text or self.type)

    def selector(self) -> tuple[str, str]:
        if self.key:
            return "--key", self.key
        if self.identifier:
            return "--identifier", self.identifier
        if self.text:
            return "--text", self.text
        return "--type", self.type

    def render(self, ref: str) -> str:
        bits = [f"{ref} {self.type}"]
        if self.key:
            bits.append(f"key={self.key}")
        elif self.identifier:
            bits.append(f"id={self.identifier}")
        if self.text and self.type not in TEXTUAL:
            bits.append(f'"{_tidy(self.text)}"')
        if not self.enabled:
            bits.append("(disabled)")
        return " ".join(bits)


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse(raw: str) -> list[Element]:
    elements: list[Element] = []
    for chunk in RECORD_SPLIT.split(raw)[1:]:
        m = FIELD["type"].match(chunk)
        if not m:
            continue
        bounds = {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
        if b := FIELD["bounds"].search(chunk):
            try:
                bounds = json.loads(b.group(1))
            except json.JSONDecodeError:
                pass

        def grab(name: str) -> str | None:
            found = FIELD[name].search(chunk)
            return found.group(1) if found else None

        enabled_raw = grab("enabled")
        visible_raw = grab("visible")
        elements.append(Element(
            type=m.group(1),
            key=grab("key"),
            identifier=grab("identifier"),
            text=grab("text"),
            # Only interactive widgets report `enabled`; absence means "not
            # a thing that can be disabled", not "disabled".
            enabled=enabled_raw != "false",
            visible=visible_raw != "false",
            x=float(bounds.get("x", 0)),
            y=float(bounds.get("y", 0)),
            w=float(bounds.get("width", 0)),
            h=float(bounds.get("height", 0)),
        ))

    # Reading order, so @e numbering matches what a person would scan.
    elements.sort(key=lambda e: (round(e.y), round(e.x)))
    return elements


def render_screen(elements: list[Element]) -> tuple[str, list[Element]]:
    """Return the compact screen the model sees, plus the addressable elements.

    The returned list is what `@eN` refers to, so the caller can map a chosen
    action back to a selector without re-parsing.
    """
    targets = [e for e in elements if e.type in ACTIONABLE and e.visible]
    lines = [e.render(f"@e{i}") for i, e in enumerate(targets, start=1)]

    copy = [
        _tidy(e.text)
        for e in elements
        if e.type in TEXTUAL and e.visible and e.text and _tidy(e.text)
    ]
    if copy:
        # Deduplicate while keeping order; repeated labels add no information.
        seen: dict[str, None] = {}
        for c in copy:
            seen.setdefault(c, None)
        lines.append("visible text: " + " | ".join(list(seen)[:25]))

    return "\n".join(lines), targets


def fetch(uri: str) -> str:
    out = subprocess.run(
        ["marionette", "--uri", uri, "get-interactive-elements"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"marionette failed: {out.stderr.strip()}")
    return out.stdout


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri", required=True)
    p.add_argument("--raw", action="store_true", help="also print the raw output")
    args = p.parse_args()

    raw = fetch(args.uri)
    elements = parse(raw)
    screen, targets = render_screen(elements)

    if args.raw:
        print(raw)
        print("=" * 60)
    print(screen)
    print("=" * 60)
    print(f"raw            {len(raw):6d} chars  (~{len(raw) // 4} tokens)")
    print(f"compact        {len(screen):6d} chars  (~{len(screen) // 4} tokens)")
    print(f"reduction      {100 - len(screen) * 100 // max(len(raw), 1):5d}%")
    print(f"elements       {len(elements):6d} parsed, {len(targets)} addressable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
