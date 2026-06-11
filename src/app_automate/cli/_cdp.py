from __future__ import annotations

import json
from typing import Annotated

import typer

from app_automate.cli._shared import (
    app,
    element_center,
    format_semantic_elements,
    load_cdp_accessibility,
)


@app.command("cdp-setup")
def cdp_setup(
    app_name: Annotated[
        str,
        typer.Option(
            "--app",
            help=(
                "App name to restart with CDP. Sets "
                "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS and restarts the app."
            ),
        ),
    ] = "",
) -> None:
    try:
        cdp = load_cdp_accessibility()
        status = cdp.cdp_status()
        if status.get("listening") == "true":
            typer.echo(json.dumps(status, indent=2))
            return
        if app_name:
            result = cdp.ensure_cdp_enabled(app_name)
        else:
            result = {
                "listening": "false",
                "message": (
                    "CDP is not active. Re-run with --app <name> to enable "
                    "and restart a WebView2 app."
                ),
            }
        typer.echo(json.dumps(result, indent=2))
    except Exception as exc:
        typer.echo(f"cdp-setup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("cdp-list")
def cdp_list(
    actionable_only: Annotated[
        bool,
        typer.Option(
            "--actionable-only/--all",
            help="Show only interactive elements.",
        ),
    ] = False,
    contains: Annotated[
        str | None,
        typer.Option(
            "--contains",
            help="Filter by case-insensitive label substring.",
        ),
    ] = None,
    port: Annotated[
        int,
        typer.Option("--port", help="CDP remote debugging port."),
    ] = 9222,
    as_json: Annotated[
        bool,
        typer.Option("--json/--table", help="Emit JSON instead of text."),
    ] = False,
    exact: Annotated[
        bool,
        typer.Option(
            "--exact/--substring",
            help="Require exact label match instead of substring.",
        ),
    ] = False,
) -> None:
    try:
        cdp = load_cdp_accessibility()
        elements = cdp.list_cdp_elements(
            port,
            actionable_only=actionable_only,
            contains=contains,
            exact=exact,
        )
    except Exception as exc:
        typer.echo(f"cdp-list failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if as_json:
        typer.echo(json.dumps([e.as_dict() for e in elements], indent=2))
        return
    typer.echo(format_semantic_elements(elements))


@app.command("cdp-click")
def cdp_click(
    contains: Annotated[
        str,
        typer.Option("--contains", help="Substring match for the target label."),
    ],
    index: Annotated[
        int,
        typer.Option("--index", min=1, help="1-based match index."),
    ] = 1,
    port: Annotated[
        int,
        typer.Option("--port", help="CDP remote debugging port."),
    ] = 9222,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Preview target without clicking.",
        ),
    ] = True,
    exact: Annotated[
        bool,
        typer.Option(
            "--exact/--substring",
            help="Require exact label match instead of substring.",
        ),
    ] = False,
) -> None:
    try:
        cdp = load_cdp_accessibility()
        if dry_run:
            elements = cdp.find_cdp_elements(
                contains=contains, port=port, actionable_only=True, exact=exact
            )
            if not elements:
                raise RuntimeError(f'no CDP elements matched "{contains}"')
            if index < 1 or index > len(elements):
                raise RuntimeError(
                    f"index {index} out of range; {len(elements)} matches"
                )
            element = elements[index - 1]
            x, y = element_center(element)
            payload = {
                "path": element.path,
                "label": element.label,
                "class_name": element.class_name,
                "action": "click",
                "x": round(x, 2),
                "y": round(y, 2),
                "bounds": {
                    "x": element.x,
                    "y": element.y,
                    "width": element.width,
                    "height": element.height,
                },
            }
            typer.echo(json.dumps(payload, indent=2))
            return

        element = cdp.click_cdp_element(
            contains=contains, port=port, index=index, exact=exact
        )
        x, y = element_center(element)
        payload = {
            "path": element.path,
            "label": element.label,
            "class_name": element.class_name,
            "action": "click",
            "x": round(x, 2),
            "y": round(y, 2),
        }
        typer.echo(json.dumps(payload, indent=2))
    except Exception as exc:
        typer.echo(f"cdp-click failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("cdp-type")
def cdp_type(
    contains: Annotated[
        str,
        typer.Option("--contains", help="Substring match for the target field."),
    ],
    text: Annotated[
        str,
        typer.Option("--text", help="Text to type."),
    ],
    index: Annotated[
        int,
        typer.Option("--index", min=1, help="1-based match index."),
    ] = 1,
    port: Annotated[
        int,
        typer.Option("--port", help="CDP remote debugging port."),
    ] = 9222,
    replace: Annotated[
        bool,
        typer.Option(
            "--replace/--append",
            help="Replace existing text before typing.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Preview target without typing.",
        ),
    ] = True,
    exact: Annotated[
        bool,
        typer.Option(
            "--exact/--substring",
            help="Require exact label match instead of substring.",
        ),
    ] = False,
) -> None:
    try:
        cdp = load_cdp_accessibility()
        if dry_run:
            elements = cdp.find_cdp_elements(
                contains=contains, port=port, actionable_only=True, exact=exact
            )
            elements = [
                e for e in elements if e.role in ("textbox", "combobox", "searchbox")
            ]
            if not elements:
                raise RuntimeError(f'no CDP text fields matched "{contains}"')
            if index < 1 or index > len(elements):
                raise RuntimeError(
                    f"index {index} out of range; {len(elements)} matches"
                )
            element = elements[index - 1]
            x, y = element_center(element)
            payload = {
                "path": element.path,
                "label": element.label,
                "class_name": element.class_name,
                "x": round(x, 2),
                "y": round(y, 2),
                "text": text,
                "replace": replace,
            }
            typer.echo(json.dumps(payload, indent=2))
            return

        element = cdp.type_into_cdp_element(
            contains=contains,
            text=text,
            port=port,
            index=index,
            replace=replace,
            exact=exact,
        )
        x, y = element_center(element)
        payload = {
            "path": element.path,
            "label": element.label,
            "class_name": element.class_name,
            "x": round(x, 2),
            "y": round(y, 2),
            "text": text,
            "replace": replace,
        }
        typer.echo(json.dumps(payload, indent=2))
    except Exception as exc:
        typer.echo(f"cdp-type failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("cdp-shortcuts")
def cdp_shortcuts(
    port: Annotated[
        int,
        typer.Option("--port", help="CDP remote debugging port."),
    ] = 9222,
    as_json: Annotated[
        bool,
        typer.Option("--json/--table", help="Emit JSON instead of text."),
    ] = False,
) -> None:
    try:
        cdp_mod = load_cdp_accessibility()
        shortcuts = cdp_mod.list_cdp_shortcuts(port=port)
    except Exception as exc:
        typer.echo(f"cdp-shortcuts failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not shortcuts:
        typer.echo(
            "No keyboard shortcuts found via "
            "aria-keyshortcuts, accesskey, or accessibility tree."
        )
        return

    if as_json:
        typer.echo(json.dumps([s.as_dict() for s in shortcuts], indent=2))
        return

    for s in shortcuts:
        typer.echo(f"  {s.keys:25s} {s.label:40s} [{s.source}]")
