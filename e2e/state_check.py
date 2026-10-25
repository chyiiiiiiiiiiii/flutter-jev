"""Judge an e2e run by what the app actually stored.

e2e drives the app from outside, so it cannot see the store. A debug build
still serves the Dart VM service, and the simulator log says where: this finds
the URI the running Boxtide process printed, reads `boxtide.state` over it, and
applies the same check `runner/arms.py` uses for the task.

    python3.13 state_check.py return-flow --label lite-run1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runner"))

from arms import TASKS  # noqa: E402
from transport import Marionette  # noqa: E402

UDID = "B0600F84-6242-446E-A687-3648EBC0A8BF"  # iPhone 17e, kept for this experiment
BUNDLE = "dev.yii.boxtide"


def running_pid(udid: str) -> str:
    out = subprocess.run(["xcrun", "simctl", "spawn", udid, "launchctl", "list"],
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if BUNDLE in line:
            pid = line.split()[0]
            if pid.isdigit():
                return pid
    raise RuntimeError("Boxtide is not running on the simulator")


def vm_uri(udid: str, pid: str) -> str:
    out = subprocess.run(
        ["xcrun", "simctl", "spawn", udid, "log", "show", "--last", "15m",
         "--style", "compact", "--predicate",
         'eventMessage CONTAINS "Dart VM service is listening"'],
        capture_output=True, text=True, check=True).stdout
    found = ""
    for line in out.splitlines():
        if f"Runner[{pid}:" in line:
            m = re.search(r"http://(127\.0\.0\.1:\d+/[^/\s]+=/)", line)
            if m:
                found = m.group(1)
    if not found:
        raise RuntimeError(f"no VM service line for pid {pid}")
    return f"ws://{found}ws"


async def read_state(uri: str) -> dict:
    async with Marionette(uri) as app:
        return await app.state()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("flow", choices=sorted(TASKS))
    p.add_argument("--label", default="")
    p.add_argument("--udid", default=UDID)
    args = p.parse_args()

    record: dict = {"flow": args.flow, "label": args.label}
    try:
        state = asyncio.run(read_state(vm_uri(args.udid, running_pid(args.udid))))
        record["done"] = bool(TASKS[args.flow][1](state))
        record["state"] = state
    except Exception as err:  # the verdict is "unknown", never a silent pass
        record["done"] = None
        record["error"] = str(err)[:300]
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
