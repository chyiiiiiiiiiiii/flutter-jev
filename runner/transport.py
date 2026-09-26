#!/usr/bin/env python3.13
"""One kept-open connection to the running Flutter app.

The `marionette` CLI is stateless: every command spawns a Dart process and
opens a fresh VM service connection, measured at 240ms per call on this
machine. With Jev deciding in ~300ms, the transport was costing almost as much
as the model. This talks to the same `ext.flutter.marionette.*` service
extensions directly over one websocket instead, which also means the app
returns structured JSON rather than the CLI's formatted text.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import aiohttp

from elements import Element, parse

EXT = "ext.flutter.marionette"

# How often to ask the app what is on screen, and how long it has to hold
# still to count as settled. Polling faster is not free: every query runs
# through the same isolate the app renders in, so a tight loop slows down the
# thing it is measuring. Tunable so the trade-off can be measured.
POLL = float(os.environ.get("JEV_POLL", "0.08"))
QUIET = float(os.environ.get("JEV_QUIET", "0.30"))


class MarionetteError(RuntimeError):
    pass


class Marionette:
    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._isolate = ""
        self._next_id = 0
        self.call_seconds = 0.0
        self.calls = 0
        self.settle_seconds = 0.0
        self.settles = 0

    async def __aenter__(self) -> Marionette:
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self._uri, heartbeat=30)
        await self._resolve_isolate()
        await self._rpc(f"{EXT}.getVersion", ext=True)
        return self

    async def _resolve_isolate(self) -> None:
        vm = await self._rpc("getVM")
        isolates = vm.get("isolates") or []
        if not isolates:
            raise MarionetteError("the app reported no isolates")
        self._isolate = isolates[0]["id"]

    async def __aexit__(self, *_: object) -> None:
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()

    async def _rpc(self, method: str, params: dict[str, Any] | None = None,
                   *, ext: bool = False) -> dict[str, Any]:
        assert self._ws is not None
        self._next_id += 1
        rid = str(self._next_id)
        payload = dict(params or {})
        if ext:
            payload["isolateId"] = self._isolate
        started = time.perf_counter()
        await self._ws.send_json(
            {"jsonrpc": "2.0", "id": rid, "method": method, "params": payload})
        # The VM service multiplexes streams onto the same socket, so skip
        # anything that is not the reply we are waiting for.
        while True:
            frame = await self._ws.receive()
            if frame.type is not aiohttp.WSMsgType.TEXT:
                raise MarionetteError(f"connection closed ({frame.type})")
            message = json.loads(frame.data)
            if message.get("id") != rid:
                continue
            self.call_seconds += time.perf_counter() - started
            self.calls += 1
            if "error" in message:
                raise MarionetteError(json.dumps(message["error"])[:300])
            return message.get("result", {})

    async def elements(self) -> list[Element]:
        return parse(await self._rpc(f"{EXT}.interactiveElements", ext=True))

    @staticmethod
    def fingerprint(elements: list[Element]) -> tuple[int, ...]:
        return (len(elements),
                *(hash((e.type, e.key, e.text, e.value, e.enabled))
                  for e in elements[:20]))

    async def changed_from(self, previous: tuple[int, ...] | None,
                           timeout: float = 6.0,
                           poll: float | None = None) -> list[Element]:
        """Return the screen as soon as it differs from `previous`.

        Deliberately does not wait for quiet. The caller uses this to start
        thinking about a screen while `quiet_since` confirms in parallel that
        the screen has stopped moving, because the model call and the rest of
        the settle wait are both just waiting and there is no reason to do
        them one after the other.
        """
        poll = POLL if poll is None else poll
        entered = time.perf_counter()
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                elements = await self.elements()
                if not any(e.addressable for e in elements):
                    await asyncio.sleep(poll)
                    continue
                if previous is None or self.fingerprint(elements) != previous:
                    return elements
                await asyncio.sleep(poll)
            return await self.elements()
        finally:
            self.settle_seconds += time.perf_counter() - entered
            self.settles += 1

    async def quiet_since(self, expected: tuple[int, ...],
                          quiet_for: float | None = None,
                          timeout: float = 5.0,
                          poll: float | None = None) -> list[Element] | None:
        """Confirm the screen has held `expected` for `quiet_for` seconds.

        Returns None when it moved on instead, so the caller knows the screen
        it was reasoning about is already out of date. Measuring the quiet in
        seconds rather than in polls means the poll interval can be tightened
        for resolution without changing how long a busy window has to be to
        get stepped over.
        """
        poll = POLL if poll is None else poll
        quiet_for = QUIET if quiet_for is None else quiet_for
        entered = time.perf_counter()
        deadline = time.monotonic() + timeout
        try:
            stable_since = time.monotonic()
            last = expected
            while time.monotonic() < deadline:
                elements = await self.elements()
                current = self.fingerprint(elements)
                if current != last:
                    return None
                if time.monotonic() - stable_since >= quiet_for:
                    return elements
                await asyncio.sleep(poll)
            return None
        finally:
            self.settle_seconds += time.perf_counter() - entered
            self.settles += 1

    async def settled_after(self, previous: tuple[int, ...] | None,
                            timeout: float = 6.0,
                            poll: float = 0.15,
                            hold_polls: int = 4) -> list[Element]:
        """Read the screen once it has changed from `previous` and gone quiet.

        Plain stability is not enough. An action that kicks off async work
        leaves the old screen standing and perfectly still for as long as the
        request takes, so a stability check settles on the screen the action
        was supposed to replace and the next decision is made against stale
        state. Waiting for an actual change first is what removes that whole
        class of flake.

        Some actions legitimately change nothing, so the timeout falls through
        to whatever is there rather than failing.
        """
        entered = time.perf_counter()
        deadline = time.monotonic() + timeout
        try:
            return await self._settle_loop(previous, deadline, poll, hold_polls)
        finally:
            self.settle_seconds += time.perf_counter() - entered
            self.settles += 1

    async def _settle_loop(self, previous: tuple[int, ...] | None,
                           deadline: float, poll: float,
                           hold_polls: int) -> list[Element]:
        while time.monotonic() < deadline:
            elements = await self.elements()
            current = self.fingerprint(elements)
            if previous is not None and current == previous:
                await asyncio.sleep(poll)
                continue

            # It changed, but a change is not an arrival. Pressing a submit
            # button disables it while the request is in flight, and that
            # busy screen holds perfectly still for as long as the work takes.
            # Requiring the same tree across several consecutive polls steps
            # over that window instead of settling inside it.
            holds = 1
            while holds < hold_polls and time.monotonic() < deadline:
                await asyncio.sleep(poll)
                latest = await self.elements()
                if self.fingerprint(latest) == current:
                    holds += 1
                    continue
                current = self.fingerprint(latest)
                elements = latest
                holds = 1
            if holds >= hold_polls and any(e.addressable for e in elements):
                return elements
            previous = None  # still moving; keep watching
        return await self.settled_elements()

    async def settled_elements(self, attempts: int = 45,
                               quiet_for: float = 0.12) -> list[Element]:
        """Wait for the widget tree to stop moving before reading it.

        Right after a tap the tree can be transiently empty or mid-transition.
        Reading it then produces a screen the model cannot act on, and the
        resulting failure looks exactly like the model choosing wrong. This is
        the single biggest source of flake in a loop like this.
        """
        previous: tuple[int, ...] | None = None
        for _ in range(attempts):
            elements = await self.elements()
            # A tree with text but nothing to touch means the app is still
            # building. Two identical reads of that state is not "settled" —
            # it is a restart or a route transition caught mid-flight.
            usable = any(e.addressable for e in elements)
            fingerprint = (len(elements),
                           *(hash((e.type, e.key, e.text)) for e in elements[:12]))
            if usable and fingerprint == previous:
                return elements
            previous = fingerprint
            await asyncio.sleep(quiet_for)
        return await self.elements()

    async def tap(self, selector: dict[str, str]) -> None:
        await self._rpc(f"{EXT}.tap", selector, ext=True)

    async def enter_text(self, selector: dict[str, str], text: str) -> None:
        await self._rpc(f"{EXT}.enterText", {**selector, "input": text}, ext=True)

    async def scroll_to(self, selector: dict[str, str]) -> None:
        await self._rpc(f"{EXT}.scrollTo", selector, ext=True)

    async def swipe(self, selector: dict[str, str], direction: str = "up") -> None:
        await self._rpc(f"{EXT}.swipe", {**selector, "direction": direction},
                        ext=True)

    async def scroll(self, elements: list[Element], up: bool = True) -> None:
        """Scroll the content area by a screen's worth.

        Marionette's element-matched swipe reports success on a Scrollable but
        does not move the viewport, so the agent kept choosing "scroll" against
        a screen that never changed. A coordinate drag does move it, and the
        coordinates come from the bounds the app itself reported rather than
        from a guess about window size.
        """
        if not elements:
            raise MarionetteError("no elements to derive a scroll area from")
        left = min(e.x for e in elements)
        right = max(e.x + e.w for e in elements)
        top = min(e.y for e in elements)
        bottom = max(e.y + e.h for e in elements)
        mid_x = round((left + right) / 2)
        span = max(bottom - top, 200.0)
        near = round(top + span * 0.75)
        far = round(top + span * 0.20)
        start_y, end_y = (near, far) if up else (far, near)
        await self._rpc(f"{EXT}.swipe", {
            "startX": mid_x, "startY": start_y,
            "endX": mid_x, "endY": end_y,
        }, ext=True)

    async def scroll_to_key(self, key: str, attempts: int = 8) -> None:
        """Bring a named element into view even when it is not on screen.

        Off-screen widgets are absent from `interactiveElements` entirely, not
        merely flagged invisible, so a key known ahead of time is the only way
        to reach one.

        A coordinate drag goes first, checking after each one. Marionette's own
        `scrollTo` stops the moment the target is technically on screen, which
        can leave the button directly below it still off-screen and therefore
        absent from the tree — so a script that scrolls to one button then
        reaches for its neighbour fails. On a screen with several Scrollables
        it can also drag the wrong one and give up after 24 attempts against a
        list that was never going to contain the target. It is kept only as a
        fallback for content a plain drag cannot reach.

        A transient overlay counts as off-screen: a SnackBar sitting over the
        bottom of the page takes the button under it out of the tree entirely
        until it dismisses itself. So this waits as well as scrolls, which is
        what a hand-written test needs and nobody writes until it has failed
        once.
        """
        deadline = time.monotonic() + 9.0
        scrolls = 0
        while time.monotonic() < deadline:
            elements = await self.elements()
            if any(e.key == key for e in elements):
                return
            if scrolls < attempts:
                await self.scroll(elements, up=True)
                scrolls += 1
            await asyncio.sleep(0.4)

        try:
            await self._rpc(f"{EXT}.scrollTo", {"key": key}, ext=True)
        except MarionetteError as err:
            raise MarionetteError(f"{key} never came into view: {err}") from err

    async def press_key(self, key: str) -> None:
        await self._rpc(f"{EXT}.pressKey", {"key": key}, ext=True)

    async def screenshot(self, path: str) -> bool:
        """Pull the current screen on demand.

        Preferred over the screencast for anything that has to line up with a
        step: a stream can hand back stale frames when the window is not
        frontmost, whereas this is a request answered from the live tree.

        The payload has been seen both as bare base64 strings and as objects,
        so accept either rather than assuming.
        """
        import base64
        result = await self._rpc(f"{EXT}.takeScreenshots", ext=True)
        shots = result.get("screenshots") or []
        if not shots:
            return False
        first = shots[0]
        data = first if isinstance(first, str) else (
            first.get("data") or first.get("bytes") or "")
        if not data:
            return False
        if "," in data[:64] and data.lstrip().startswith("data:"):
            data = data.split(",", 1)[1]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(base64.b64decode(data))
        return True

    async def stop_screencast(self) -> None:
        """Make sure no frame stream is left running.

        A recorder that does not shut down cleanly leaves `startScreencast`
        streaming frames through the same isolate every query goes through.
        Measured cost of one leaked stream: interactiveElements went from 4ms
        to 350ms, which looks exactly like "the app got slow" and poisons every
        later measurement.
        """
        try:
            await self._rpc(f"{EXT}.stopScreencast", ext=True)
        except MarionetteError:
            pass

    async def set_chaos(self, seed: int) -> dict[str, Any]:
        """Churn the app the way a development team does.

        The demo app registers this itself through
        `registerMarionetteExtension`, so it lands as a plain service
        extension outside the marionette namespace. A non-zero seed renames
        widget keys, swaps button labels, reorders the order list and
        sometimes inserts a confirmation step, reproducibly.
        """
        return await self._rpc("ext.flutter.boxtide.setChaos",
                               {"seed": str(seed)}, ext=True)

    async def state(self) -> dict[str, Any]:
        """What the app actually holds: orders, cart, addresses, tickets.

        A run is judged against this rather than against the agent's own
        verdict, because a model that says "pass" early is the failure the
        confidence floors exist to catch.
        """
        result = await self._rpc("ext.flutter.boxtide.state", {}, ext=True)
        raw = result.get("json") or (result.get("data") or {}).get("json")
        if raw is None:
            raise MarionetteError(f"unexpected state reply: {str(result)[:200]}")
        return json.loads(raw)

    async def hot_restart(self) -> None:
        """Put the app back to a known state between runs.

        A bare `reloadSources` is a hot *reload*: it swaps code but keeps the
        navigation stack, so the next run starts wherever the last one stopped.
        The CLI knows how to do a real restart, and paying its 240ms once
        during setup costs nothing.
        """
        import asyncio.subprocess as sp
        proc = await asyncio.create_subprocess_exec(
            "marionette", "--uri", self._uri, "hot-restart",
            stdout=sp.PIPE, stderr=sp.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise MarionetteError(f"hot restart failed: {err.decode()[:200]}")
        # A restart replaces the isolate. Keeping the old id means every later
        # query runs against a dead tree and quietly returns nothing, which
        # reads exactly like "the app has no widgets".
        await asyncio.sleep(0.6)
        await self._resolve_isolate()
