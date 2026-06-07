"""Demo: drive Safari using keyboard shortcuts + AX elements.

Performs a navigation workflow:
  new tab → type URL → wait → find text → close tab

Uses the native axtool binary for all input operations.

Usage:
    uv run python demos/safari_shortcuts.py --dry-run
    uv run python demos/safari_shortcuts.py --execute

Prerequisites:
    - Safari must be running and focused (for --execute)
    - axtool built at native/axtool/.build/debug/axtool
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

PROFILE = Path("examples/profiles/safari/profile.json")
AXTOOL = Path("native/axtool/.build/debug/axtool")


def axtool(*args: str, timeout: float = 10) -> str:
    result = subprocess.run(
        [str(AXTOOL), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        print(f"  axtool error: {result.stderr.strip()}")
    return result.stdout.strip()


def load_profile() -> dict:
    with open(PROFILE) as f:
        return json.load(f)


def resolve_shortcut(profile: dict, command: str) -> dict | None:
    elements = profile.get("semantic_elements", {})
    command_lower = command.lower().replace("…", "").replace("...", "")
    for _elem_id, elem in elements.items():
        if elem.get("action") != "shortcut":
            continue
        label = elem.get("label", "").lower().replace("…", "").replace("...", "")
        aliases = [
            a.lower().replace("…", "").replace("...", "")
            for a in elem.get("aliases", [])
        ]
        if label == command_lower or command_lower in aliases:
            return elem.get("shortcut", {})
    return None


def main() -> None:
    if not PROFILE.exists():
        print(f"Profile not found: {PROFILE}")
        sys.exit(1)
    if not AXTOOL.exists():
        print(f"axtool not found: {AXTOOL}")
        print("Build it with: swift build --package-path native/axtool")
        sys.exit(1)

    execute = "--execute" in sys.argv
    mode = "EXECUTE" if execute else "DRY-RUN"

    profile = load_profile()
    shortcuts = profile.get("shortcuts", {})
    print(f"Safari Demo ({mode})")
    print(f"Profile: {profile['profile_id']} — {profile['app_name']}")
    print(f"Shortcuts: {len(shortcuts)} available")
    print()

    steps = [
        ("new_tab", "Open new tab"),
        ("open_location…", "Focus URL bar"),
        ("type_url", "Type apple.com"),
        ("reload_page", "Reload page"),
        ("find", "Open find bar"),
        ("close_window", "Close tab"),
    ]

    for command, description in steps:
        if command == "type_url":
            if execute:
                axtool("type", "--text", "apple.com")
                axtool("hotkey", "--keys", "return")
                print(f"  {description:30s} [typed apple.com]")
                time.sleep(2)
            else:
                print(f"  {description:30s} [type 'apple.com' + Enter]")
            continue

        sc = resolve_shortcut(profile, command)
        if sc is None:
            print(f"  {description:30s} [NOT FOUND: {command}]")
            continue

        keys = sc.get("keys", "")
        if execute:
            axtool("hotkey", "--keys", keys)
            print(f"  {description:30s} [sent {keys}]")
            time.sleep(0.5)
        else:
            print(f"  {description:30s} [shortcut: {keys}]")

    print()
    if not execute:
        print("Run with --execute to send real keypresses to Safari.")


if __name__ == "__main__":
    main()
