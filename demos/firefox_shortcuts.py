"""Demo: drive Firefox using the Consumer SDK.

Performs a navigation workflow:
  open tab → focus URL bar → type URL → wait → find text → close tab

Usage:
    uv run python demos/firefox_shortcuts.py --dry-run
    uv run python demos/firefox_shortcuts.py --execute

Prerequisites:
    - Firefox must be running and focused (for --execute)
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from app_automate.consumer import Consumer

logging.basicConfig(level=logging.WARNING)

PROFILE = Path("examples/profiles/firefox/profile.json")


def main() -> None:
    if not PROFILE.exists():
        print(f"Profile not found: {PROFILE}")
        sys.exit(1)

    execute = "--execute" in sys.argv
    mode = "EXECUTE" if execute else "DRY-RUN"

    c = Consumer.from_file(PROFILE, adapter=None)

    print(f"Firefox SDK Demo ({mode})")
    print(f"Profile: {c.profile_id} — {c.app_name}")
    print(f"Commands: {len(c.list_commands())} available")
    print()

    steps = [
        ("new tab", "Open new tab", None),
        ("address bar", "Focus URL bar", None),
        ("find", "Open find bar", None),
        ("back", "Go back", None),
        ("close tab", "Close tab", None),
    ]

    for command, description, _text in steps:
        element = c.resolve(command)
        if not execute:
            keys = element.shortcut.keys_for_platform() if element.shortcut else None
            detail = f" → {keys}" if keys else ""
            print(f"  {description:30s} [{element.action.value}]{detail}")
        else:
            result = c.execute(command)
            print(f"  {description:30s} [{result.action}]")
            time.sleep(0.5)

    print()
    if not execute:
        print("Run with --execute to send real keypresses to Firefox.")


if __name__ == "__main__":
    main()
