"""Convert ShortcutMapper data to app-automate profiles.

Usage:
    python scripts/convert_shortcutmapper.py /tmp/ShortcutMapper examples/profiles

Reads intermediate JSON files from ShortcutMapper sources and converts them
to app-automate profile.json + shortcuts.json format. Also handles generated
JSON for apps without intermediate data (like Blender).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LINUX_KEYS = {"ctrl", "alt", "shift"}
MAC_TO_GENERIC = {"cmd": "ctrl", "command": "ctrl", "option": "alt"}


def normalize_keys(raw: str) -> str:
    raw = raw.strip()
    raw = raw.replace(" + ", "+").replace("+ ", "+").replace(" +", "+")
    raw = re.sub(r"\s+or\s+.*", "", raw)
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split("+")]
    normalized = []
    for p in parts:
        lower = p.lower()
        if lower in ("ctrl", "control"):
            normalized.append("ctrl")
        elif lower in ("alt",):
            normalized.append("alt")
        elif lower in ("shift",):
            normalized.append("shift")
        elif lower in ("cmd", "command"):
            normalized.append("cmd")
        elif lower in ("option",):
            normalized.append("alt")
        elif lower == "up arrow":
            normalized.append("up")
        elif lower == "down arrow":
            normalized.append("down")
        elif lower == "left arrow":
            normalized.append("left")
        elif lower == "right arrow":
            normalized.append("right")
        elif lower == "backspace":
            normalized.append("backspace")
        elif lower == "delete":
            normalized.append("delete")
        elif lower == "enter":
            normalized.append("enter")
        elif lower == "return":
            normalized.append("enter")
        elif lower == "escape":
            normalized.append("escape")
        elif lower == "space":
            normalized.append("space")
        elif lower == "page up":
            normalized.append("pageup")
        elif lower == "page down":
            normalized.append("pagedown")
        elif lower == "tab":
            normalized.append("tab")
        elif lower == "caps lock":
            normalized.append("capslock")
        elif lower.startswith("numpad "):
            normalized.append(f"num{lower[7:]}")
        elif len(lower) == 1:
            normalized.append(lower)
        elif lower.startswith("f") and lower[1:].isdigit():
            normalized.append(lower)
        else:
            normalized.append(lower)
    return "+".join(normalized)


def slugify(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def make_alias(label: str) -> list[str]:
    aliases = [label.lower()]
    clean = label.lower()
    if "/" in clean:
        parts = [p.strip() for p in clean.split("/")]
        aliases.extend(parts)
    if " - " in clean:
        parts = [p.strip() for p in clean.split(" - ")]
        aliases.extend(parts)
    return list(dict.fromkeys(aliases))


def is_valid_shortcut(keys: str) -> bool:
    if not keys:
        return False
    if " or " in keys:
        return False
    if any(c in keys for c in "()[]{}<>"):
        return False
    if len(keys) > 40:
        return False
    return True


def _dedupe_slug(slug: str, ctx_name: str, seen: dict[str, int]) -> str:
    if slug not in seen:
        seen[slug] = 1
        return slug
    ctx_slug = f"{slug}_{slugify(ctx_name)}"
    if ctx_slug not in seen:
        seen[ctx_slug] = 1
        return ctx_slug
    n = seen[ctx_slug]
    seen[ctx_slug] += 1
    final = f"{ctx_slug}_{n}"
    seen[final] = 1
    return final


def convert_intermediate(
    data: dict,
    app_id: str,
    app_name: str,
) -> tuple[dict, dict]:
    shortcuts: dict[str, dict] = {}
    elements: dict[str, dict] = {}
    seen_slugs: dict[str, int] = {}

    for ctx_name, actions in data.get("contexts", {}).items():
        for action_label, keys_data in actions.items():
            if isinstance(keys_data, list):
                if len(keys_data) >= 2:
                    win_keys = normalize_keys(keys_data[0])
                    mac_keys = normalize_keys(keys_data[1])
                elif len(keys_data) == 1:
                    win_keys = normalize_keys(keys_data[0])
                    mac_keys = win_keys
                else:
                    continue
            elif isinstance(keys_data, str):
                win_keys = normalize_keys(keys_data)
                mac_keys = win_keys
            else:
                continue

            slug = slugify(action_label)
            if not slug or len(slug) < 2:
                continue

            base_keys = win_keys
            if not is_valid_shortcut(base_keys):
                if is_valid_shortcut(mac_keys):
                    base_keys = mac_keys
                else:
                    continue

            slug = _dedupe_slug(slug, ctx_name, seen_slugs)

            entry: dict = {"keys": base_keys, "description": action_label}
            if mac_keys != base_keys and mac_keys and is_valid_shortcut(mac_keys):
                mac_entry = {
                    "keys": mac_keys,
                    "description": action_label,
                    "platform": "macos",
                }
                shortcuts[f"{slug}_mac"] = mac_entry
            shortcuts[slug] = entry

            aliases = make_alias(action_label)
            elements[slug] = {
                "label": action_label,
                "aliases": aliases,
                "action": "shortcut",
                "shortcut": {"keys": base_keys, "description": action_label},
            }

    return shortcuts, elements


def convert_generated(
    data: dict,
) -> tuple[dict, dict]:
    shortcuts: dict[str, dict] = {}
    elements: dict[str, dict] = {}
    seen_slugs: dict[str, int] = {}

    for ctx_name, keys_map in data.get("contexts", {}).items():
        for key_name, actions in keys_map.items():
            for action in actions:
                label = action.get("name", "")
                mods = action.get("mods", [])
                slug = slugify(label)
                if not slug or len(slug) < 2:
                    continue

                key_base = key_name.lower().replace("numpad_", "num")
                if key_base.startswith("numpad "):
                    key_base = f"num{key_base[7:]}"

                parts = [m.lower() for m in mods]
                if "control" in parts:
                    parts[parts.index("control")] = "ctrl"
                if "command" in parts:
                    parts[parts.index("command")] = "cmd"
                parts.append(key_base)
                keys_str = "+".join(parts)

                if not is_valid_shortcut(keys_str):
                    continue

                slug = _dedupe_slug(slug, ctx_name, seen_slugs)

                shortcuts[slug] = {"keys": keys_str, "description": label}
                aliases = make_alias(label)
                elements[slug] = {
                    "label": label,
                    "aliases": aliases,
                    "action": "shortcut",
                    "shortcut": {"keys": keys_str, "description": label},
                }

    return shortcuts, elements


def build_profile(
    app_id: str,
    app_name: str,
    version: str,
    shortcuts: dict,
    elements: dict,
) -> dict:
    return {
        "profile_id": app_id,
        "app_name": app_name,
        "type": "semantic",
        "backend": "shortcut",
        "platform_hint": None,
        "notes": f"Auto-generated from ShortcutMapper. {len(shortcuts)} shortcuts.",
        "shortcuts": shortcuts,
        "semantic_elements": elements,
    }


def process_intermediate_file(
    src: Path,
    out_dir: Path,
) -> str | None:
    data = json.loads(src.read_text())
    app_name = data.get("name", src.parent.parent.name)
    version = data.get("version", "")
    app_id = slugify(app_name)

    shortcuts, elements = convert_intermediate(data, app_id, app_name)
    if not shortcuts:
        return f"SKIP {app_id}: no valid shortcuts"

    profile = build_profile(app_id, app_name, version, shortcuts, elements)
    dest = out_dir / app_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "profile.json").write_text(json.dumps(profile, indent=2))
    standalone = {k: v for k, v in shortcuts.items() if not k.endswith("_mac")}
    (dest / f"{app_id}-shortcuts.json").write_text(json.dumps(standalone, indent=2))
    return f"OK {app_id}: {len(shortcuts)} shortcuts, {len(elements)} elements"


def process_generated_file(
    src: Path,
    out_dir: Path,
    os_filter: str = "windows",
) -> str | None:
    data = json.loads(src.read_text())
    app_name = data.get("name", "")
    version = data.get("version", "")
    app_id = slugify(app_name)
    file_os = data.get("os", "")

    if file_os != os_filter:
        return None

    shortcuts, elements = convert_generated(data)
    if not shortcuts:
        return f"SKIP {app_id}: no valid shortcuts"

    profile = build_profile(app_id, app_name, version, shortcuts, elements)
    dest = out_dir / app_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "profile.json").write_text(json.dumps(profile, indent=2))
    (dest / f"{app_id}-shortcuts.json").write_text(json.dumps(shortcuts, indent=2))
    return (
        f"OK {app_id}: {len(shortcuts)} shortcuts, "
        f"{len(elements)} elements (from generated)"
    )


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python convert_shortcutmapper.py <shortcutmapper_dir> <output_dir>"
        )
        sys.exit(1)

    sm_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])

    if not sm_dir.exists():
        print(f"Error: {sm_dir} does not exist")
        sys.exit(1)

    results = []

    # Process intermediate files
    for idir in sorted((sm_dir / "sources").iterdir()):
        if not idir.is_dir():
            continue
        intermediate_dir = idir / "intermediate"
        if not intermediate_dir.exists():
            continue
        for json_file in sorted(intermediate_dir.glob("*.json")):
            result = process_intermediate_file(json_file, out_dir)
            if result:
                results.append(result)

    # Process generated files for apps without intermediate (like Blender)
    intermediate_apps = set()
    for idir in (sm_dir / "sources").iterdir():
        if (idir / "intermediate").exists():
            intermediate_apps.add(idir.name)

    generated_dir = sm_dir / "content" / "generated"
    if generated_dir.exists():
        processed_generated = set()
        for json_file in sorted(generated_dir.glob("*_windows.json")):
            stem = json_file.stem.replace("_windows", "")
            parts = stem.rsplit("_", 1)
            if len(parts) == 2:
                app_slug = parts[0]
            else:
                app_slug = stem

            if app_slug in intermediate_apps:
                continue
            if app_slug in processed_generated:
                continue

            result = process_generated_file(json_file, out_dir, os_filter="windows")
            if result:
                results.append(result)
                processed_generated.add(app_slug)

    print(f"\nProcessed {len(results)} apps:")
    for r in results:
        print(f"  {r}")


if __name__ == "__main__":
    main()
