from __future__ import annotations

import json
from typing import Annotated

import typer

from app_automate.cli._shared import app


@app.command("search")
def search_command(
    query: Annotated[
        str,
        typer.Argument(help="Search query for UI elements."),
    ],
    app_name: Annotated[
        str,
        typer.Option("--app", help="Application name to search in."),
    ] = "",
    role: Annotated[
        str | None,
        typer.Option(
            "--role",
            help=(
                "Filter by element role (button, link, textfield, "
                "menuitem, checkbox, radio, etc.)."
            ),
        ),
    ] = None,
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", help="Max AX tree depth to traverse."),
    ] = 10,
    max_results: Annotated[
        int,
        typer.Option("--max-results", help="Maximum results to return."),
    ] = 20,
    actionable_only: Annotated[
        bool,
        typer.Option(
            "--actionable/--all",
            help="Only return actionable elements.",
        ),
    ] = True,
    click: Annotated[
        bool,
        typer.Option(
            "--click",
            help="Click the top-ranked result.",
        ),
    ] = False,
    type_text: Annotated[
        str | None,
        typer.Option(
            "--type",
            help="Type text into the top-ranked text field result.",
        ),
    ] = None,
    index: Annotated[
        int,
        typer.Option(
            "--index",
            help="1-based index of result to act on (default: top result).",
        ),
    ] = 1,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Show what would be done without executing.",
        ),
    ] = True,
    as_json: Annotated[
        bool,
        typer.Option(
            "--json/--text",
            help="Output format.",
        ),
    ] = False,
) -> None:
    try:
        from app_automate.accessibility.search import search_elements

        if not app_name:
            app_name = _foreground_app()
            if not app_name:
                typer.echo(
                    "No --app specified and cannot detect foreground app.",
                    err=True,
                )
                raise typer.Exit(code=1)
            typer.echo(f"Detected foreground app: {app_name}", err=True)

        elements = _list_elements(app_name, max_depth, actionable_only)
        if not elements:
            typer.echo(f"No elements found for '{app_name}'.", err=True)
            raise typer.Exit(code=1)

        results = search_elements(
            elements,
            query,
            role_filter=role,
            actionable_only=actionable_only,
            enabled_only=True,
            max_results=max_results,
        )

        if not results:
            typer.echo(f"No matches for '{query}' in {app_name}.")
            return

        if click or type_text is not None:
            idx = index - 1
            if idx < 0 or idx >= len(results):
                typer.echo(
                    f"Index {index} out of range (1-{len(results)}).",
                    err=True,
                )
                raise typer.Exit(code=1)
            target = results[idx]
            _act_on_result(target, click=click, type_text=type_text, dry_run=dry_run)
            return

        if as_json:
            typer.echo(json.dumps([r.as_dict() for r in results], indent=2))
            return

        typer.echo(f"\n{len(results)} results for '{query}' in {app_name}:\n")
        typer.echo(
            f"  {'#':>2}  {'Score':>5}  {'Match':<22}  "
            f"{'Label':<30}  {'Role':<20}  {'X':>5}  {'Y':>5}"
        )
        typer.echo(
            f"  {'':>2}  {'':>5}  {'':<22}  "
            f"{'-' * 30}  {'-' * 20}  {'-' * 5}  {'-' * 5}"
        )
        for i, r in enumerate(results):
            label = (r.element.label or "")[:30]
            role_str = (r.element.role or r.element.class_name or "")[:20]
            typer.echo(
                f"  {i + 1:>2}  {r.score:>5.1f}  {r.match_type:<22}  "
                f"{label:<30}  {role_str:<20}  "
                f"{r.element.x or 0:>5}  {r.element.y or 0:>5}"
            )
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"search failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _foreground_app() -> str | None:
    from app_automate.platform_utils import is_macos, is_windows

    if is_windows():
        import ctypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
            buf = ctypes.create_unicode_buffer(length)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
            title = buf.value
            if title:
                for sep in (" - ", " — "):
                    if sep in title:
                        title = title.split(sep)[-1].strip()
                return title
    elif is_macos():
        import subprocess

        result = subprocess.run(
            [
                "osascript",
                "-e",
                (
                    'tell application "System Events" to get name '
                    "of first process whose frontmost is true"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


def _list_elements(app_name: str, max_depth: int, actionable_only: bool) -> list:
    from app_automate.platform_utils import is_linux, is_macos, is_windows

    if is_macos():
        from app_automate.accessibility.macos_ax import list_app_ui_elements

        return list_app_ui_elements(
            app_name, max_depth=max_depth, actionable_only=actionable_only
        )
    elif is_windows():
        from app_automate.accessibility.windows_uia import list_app_ui_elements

        return list_app_ui_elements(
            app_name, max_depth=max_depth, actionable_only=actionable_only
        )
    elif is_linux():
        from app_automate.accessibility.linux_atspi import list_app_ui_elements

        return list_app_ui_elements(
            app_name, max_depth=max_depth, actionable_only=actionable_only
        )
    else:
        return []


def _act_on_result(
    result, *, click: bool, type_text: str | None, dry_run: bool
) -> None:
    el = result.element
    label = el.label or "(unnamed)"
    role_str = el.role or el.class_name or ""
    cx = (el.x or 0) + (el.width or 0) // 2
    cy = (el.y or 0) + (el.height or 0) // 2

    if dry_run:
        if click:
            typer.echo(f"[dry-run] Would click '{label}' ({role_str}) at ({cx}, {cy})")
        if type_text is not None:
            typer.echo(
                f"[dry-run] Would type '{type_text}' into '{label}' "
                f"({role_str}) at ({cx}, {cy})"
            )
        return

    from app_automate.cli._shared import create_action_adapter

    adapter = create_action_adapter()
    if click:
        adapter.click(cx, cy)
        typer.echo(f"Clicked '{label}' at ({cx}, {cy})")
    if type_text is not None:
        adapter.click(cx, cy)
        import time

        time.sleep(0.1)
        adapter.write_text(type_text)
        typer.echo(f"Typed '{type_text}' into '{label}' at ({cx}, {cy})")
