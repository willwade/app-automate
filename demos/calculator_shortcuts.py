"""Demo: drive Galculator using keyboard shortcuts via app-automate profile.

Performs the calculation 2 + 3 = 5 using the galculator shortcut profile.

Usage:
    uv run python demos/calculator_shortcuts.py

Prerequisites:
    - Galculator must be installed: sudo apt install galculator
    - Galculator must be running and focused
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

PROFILE = Path("examples/profiles/galculator/profile.json")


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

    print("Calculator Shortcuts Demo")
    print("=" * 40)
    print()

    print("1. Listing profile elements:")
    run("list-elements", [str(PROFILE)])
    print()

    print("2. Dry-run for digit 2:")
    result = run("dry-run", ["2", "--profile", str(PROFILE)])
    print(f"   action={result.get('action')} backend={result.get('backend')}")
    print()

    print("3. Dry-run for add:")
    result = run("dry-run", ["+", "--profile", str(PROFILE)])
    print(f"   action={result.get('action')} keys matched")
    print()

    print("4. Dry-run for equals:")
    result = run("dry-run", ["equals", "--profile", str(PROFILE)])
    print(f"   action={result.get('action')}")
    print()

    print("To execute real keypresses (requires Galculator focused):")
    p = "examples/profiles/galculator/profile.json"
    print(f'  uv run app-automate click "2" --profile {p}')
    print(f'  uv run app-automate click "+" --profile {p}')
    print(f'  uv run app-automate click "3" --profile {p}')
    print(f'  uv run app-automate click "equals" --profile {p}')
    print()
    print("Or all at once:")
    print()
    print("  uv run python demos/calculator_shortcuts.py --execute")
    print()

    if "--execute" in sys.argv:
        print("Executing: 2 + 3 = ...")
        time.sleep(0.5)
        run("click", ["2", "--profile", str(PROFILE)])
        time.sleep(0.2)
        run("click", ["+", "--profile", str(PROFILE)])
        time.sleep(0.2)
        run("click", ["3", "--profile", str(PROFILE)])
        time.sleep(0.2)
        run("click", ["equals", "--profile", str(PROFILE)])
        print("Done! Result should be 5 in Galculator.")


if __name__ == "__main__":
    main()
