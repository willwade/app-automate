"""Demo: drive Firefox using keyboard shortcuts via app-automate profile.

Demonstrates cross-platform keyboard shortcut automation:
- Opens a new tab (ctrl+t)
- Focuses the URL bar (ctrl+l)
- Navigates to a URL
- Finds text on page (ctrl+f)
- Closes the tab (ctrl+w)

Usage:
    uv run python demos/firefox_shortcuts.py --dry-run
    uv run python demos/firefox_shortcuts.py --execute

Prerequisites:
    - Firefox must be running and focused
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

PROFILE = Path("examples/profiles/firefox/profile.json")


def run(cmd: str, args: list[str] | None = None) -> dict:
    command = ["uv", "run", "app-automate", cmd]
    if args:
        command.extend(args)
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAIL: {' '.join(command)}")
        print(result.stderr)
        sys.exit(1)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(result.stdout)
        return {}


def main() -> None:
    if not PROFILE.exists():
        print(f"Profile not found: {PROFILE}")
        sys.exit(1)

    dry_run = "--execute" not in sys.argv
    mode = "DRY-RUN" if dry_run else "EXECUTE"

    print(f"Firefox Shortcuts Demo ({mode})")
    print("=" * 40)
    print()

    steps = [
        ("new_tab", "Open new tab", []),
        ("url_bar", "Focus URL bar", []),
        ("find", "Open find bar", []),
        ("close_tab", "Close tab", []),
        ("back", "Go back", []),
        ("reload", "Reload page", []),
    ]

    for element_id, description, extra_args in steps:
        print(f"  {description}: ", end="")
        args = [element_id, "--profile", str(PROFILE)] + extra_args

        if dry_run:
            result = run("dry-run", args)
        else:
            result = run("click", args)
            time.sleep(0.5)

        backend = result.get("backend", "?")
        action = result.get("action", "?")
        print(f"[{backend}/{action}]")

    print()
    if dry_run:
        print("All steps resolved successfully in dry-run mode.")
        print("Run with --execute to send real keypresses to Firefox.")
    else:
        print("All steps executed!")


if __name__ == "__main__":
    main()
