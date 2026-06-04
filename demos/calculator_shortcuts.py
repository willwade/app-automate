"""Demo: drive Galculator using the Consumer SDK.

Performs the calculation 2 + 3 = 5 using keyboard shortcuts.

Usage:
    uv run python demos/calculator_shortcuts.py --dry-run
    uv run python demos/calculator_shortcuts.py --execute

Prerequisites:
    - Galculator must be installed (sudo apt install galculator)
    - Galculator must be running and focused (for --execute)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from app_automate.consumer import Consumer

PROFILE = Path("examples/profiles/galculator/profile.json")


def main() -> None:
    if not PROFILE.exists():
        print(f"Profile not found: {PROFILE}")
        sys.exit(1)

    execute = "--execute" in sys.argv
    mode = "EXECUTE" if execute else "DRY-RUN"

    c = Consumer.from_file(PROFILE)

    print(f"Calculator SDK Demo ({mode})")
    print(f"Profile: {c.profile_id} — {c.app_name}")
    print()

    calculation = [
        ("2", "Press 2"),
        ("plus", "Press +"),
        ("3", "Press 3"),
        ("equals", "Press ="),
    ]

    print("  2 + 3 = ?")
    print()

    for command, description in calculation:
        element = c.resolve(command)
        keys = element.shortcut.keys_for_platform() if element.shortcut else None
        if not execute:
            detail = f" → {keys}" if keys else ""
            print(f"    {description:15s} [{element.action.value}]{detail}")
        else:
            result = c.execute(command)
            print(f"    {description:15s} [{result.action}]")
            time.sleep(0.3)

    print()
    if not execute:
        print("  Run with --execute to send real keypresses to Galculator.")
    else:
        print("  Done! Result should be 5.")


if __name__ == "__main__":
    main()
