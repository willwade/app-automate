from __future__ import annotations

import json
from typing import Annotated, Literal

import typer

from app_automate.cli._shared import (
    app,
    create_action_adapter,
    element_center,
    format_semantic_elements,
    load_macos_accessibility,
    load_windows_accessibility,
    run_ax_action,
    select_semantic_element,
    type_into_element,
)


@app.command("ax-list")
def ax_list(
    app_name: Annotated[
        str,
        typer.Option("--app", help="macOS app name to inspect."),
    ],
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", min=0, help="Maximum UI tree depth to inspect."),
    ] = 3,
    actionable_only: Annotated[
        bool,
        typer.Option(
            "--actionable-only/--all",
            help="Show only actionable controls such as buttons and fields.",
        ),
    ] = False,
    contains: Annotated[
        str | None,
        typer.Option(
            "--contains",
            help="Filter by case-insensitive label/description substring.",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json/--table", help="Emit JSON instead of a text table."),
    ] = False,
) -> None:
    try:
        elements = load_macos_accessibility().list_app_ui_elements(
            app_name,
            max_depth=max_depth,
            actionable_only=actionable_only,
        )
    except Exception as exc:
        typer.echo(f"ax-list failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if contains is not None:
        needle = contains.lower()
        elements = [
            element
            for element in elements
            if needle in element.label.lower()
            or needle in (element.role or "").lower()
            or needle in (element.subrole or "").lower()
        ]

    if as_json:
        typer.echo(json.dumps([element.as_dict() for element in elements], indent=2))
        return

    typer.echo(format_semantic_elements(elements))


@app.command("ax-click")
def ax_click(
    app_name: Annotated[
        str,
        typer.Option("--app", help="macOS app name to inspect."),
    ],
    contains: Annotated[
        str,
        typer.Option("--contains", help="Substring match for the target label."),
    ],
    action: Annotated[
        Literal["click", "right-click", "double-click", "scroll", "drag"],
        typer.Option(
            "--action",
            help="Semantic action to perform on the matched element.",
        ),
    ] = "click",
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", min=0, help="Maximum UI tree depth to inspect."),
    ] = 3,
    index: Annotated[
        int,
        typer.Option(
            "--index",
            min=1,
            help="1-based match index when multiple accessible elements match.",
        ),
    ] = 1,
    drag_dx: Annotated[
        float,
        typer.Option("--drag-dx", help="Drag delta in x for action=drag."),
    ] = 0.0,
    drag_dy: Annotated[
        float,
        typer.Option("--drag-dy", help="Drag delta in y for action=drag."),
    ] = 0.0,
    scroll_clicks: Annotated[
        int,
        typer.Option(
            "--scroll-clicks",
            help="Signed scroll delta for action=scroll.",
        ),
    ] = 0,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Preview the AX target and action without sending input.",
        ),
    ] = True,
) -> None:
    try:
        element = select_semantic_element(
            finder=load_macos_accessibility().find_matching_elements,
            app_name=app_name,
            contains=contains,
            max_depth=max_depth,
            index=index,
        )
        x, y = element_center(element)
        payload = {
            "path": element.path,
            "label": element.label,
            "class_name": element.class_name,
            "action": action,
            "x": round(x, 2),
            "y": round(y, 2),
            "bounds": {
                "x": element.x,
                "y": element.y,
                "width": element.width,
                "height": element.height,
            },
        }
        if action == "drag":
            payload["end_x"] = round(x + drag_dx, 2)
            payload["end_y"] = round(y + drag_dy, 2)
        if action == "scroll":
            payload["scroll_clicks"] = scroll_clicks

        if dry_run:
            typer.echo(json.dumps(payload, indent=2))
            return

        payload = run_ax_action(
            adapter=create_action_adapter(),
            element=element,
            action=action,
            drag_dx=drag_dx,
            drag_dy=drag_dy,
            scroll_clicks=scroll_clicks,
        )
    except Exception as exc:
        typer.echo(f"ax-click failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(payload, indent=2))


@app.command("uia-list")
def uia_list(
    app_name: Annotated[
        str,
        typer.Option("--app", help="Windows app or window name to inspect."),
    ],
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", min=0, help="Maximum UI tree depth to inspect."),
    ] = 8,
    actionable_only: Annotated[
        bool,
        typer.Option(
            "--actionable-only/--all",
            help="Show only actionable controls such as buttons and fields.",
        ),
    ] = False,
    contains: Annotated[
        str | None,
        typer.Option(
            "--contains",
            help="Filter by case-insensitive label, role, or automation id.",
        ),
    ] = None,
    control_type: Annotated[
        str | None,
        typer.Option(
            "--control-type",
            help="Filter by an exact UIA control type name.",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json/--table", help="Emit JSON instead of a text table."),
    ] = False,
) -> None:
    try:
        elements = load_windows_accessibility().list_app_ui_elements(
            app_name,
            max_depth=max_depth,
            actionable_only=actionable_only,
        )
    except Exception as exc:
        typer.echo(f"uia-list failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if contains is not None:
        needle = contains.lower()
        elements = [
            element
            for element in elements
            if needle in element.label.lower()
            or needle in (element.role or "").lower()
            or needle in (element.subrole or "").lower()
            or needle in (element.automation_id or "").lower()
        ]
    if control_type is not None:
        elements = [
            element for element in elements if element.class_name == control_type
        ]

    if as_json:
        typer.echo(json.dumps([element.as_dict() for element in elements], indent=2))
        return

    typer.echo(format_semantic_elements(elements))


@app.command("uia-click")
def uia_click(
    app_name: Annotated[
        str,
        typer.Option("--app", help="Windows app or window name to inspect."),
    ],
    contains: Annotated[
        str,
        typer.Option("--contains", help="Substring match for the target label."),
    ],
    action: Annotated[
        Literal["click", "right-click", "double-click", "scroll", "drag"],
        typer.Option(
            "--action",
            help="Semantic action to perform on the matched element.",
        ),
    ] = "click",
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", min=0, help="Maximum UI tree depth to inspect."),
    ] = 8,
    index: Annotated[
        int,
        typer.Option(
            "--index",
            min=1,
            help="1-based match index when multiple accessible elements match.",
        ),
    ] = 1,
    control_type: Annotated[
        str | None,
        typer.Option(
            "--control-type",
            help="Require an exact UIA control type name match.",
        ),
    ] = None,
    drag_dx: Annotated[
        float,
        typer.Option("--drag-dx", help="Drag delta in x for action=drag."),
    ] = 0.0,
    drag_dy: Annotated[
        float,
        typer.Option("--drag-dy", help="Drag delta in y for action=drag."),
    ] = 0.0,
    scroll_clicks: Annotated[
        int,
        typer.Option(
            "--scroll-clicks",
            help="Signed scroll delta for action=scroll.",
        ),
    ] = 0,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Preview the UIA target and action without sending input.",
        ),
    ] = True,
) -> None:
    try:
        windows_accessibility = load_windows_accessibility()
        element = select_semantic_element(
            finder=windows_accessibility.find_matching_elements,
            app_name=app_name,
            contains=contains,
            control_type=control_type,
            max_depth=max_depth,
            index=index,
        )
        x, y = element_center(element)
        payload = {
            "path": element.path,
            "label": element.label,
            "class_name": element.class_name,
            "automation_id": element.automation_id,
            "action": action,
            "x": round(x, 2),
            "y": round(y, 2),
            "bounds": {
                "x": element.x,
                "y": element.y,
                "width": element.width,
                "height": element.height,
            },
        }
        if action == "drag":
            payload["end_x"] = round(x + drag_dx, 2)
            payload["end_y"] = round(y + drag_dy, 2)
        if action == "scroll":
            payload["scroll_clicks"] = scroll_clicks

        if dry_run:
            typer.echo(json.dumps(payload, indent=2))
            return

        direct_click = getattr(windows_accessibility, "click_matching_element", None)
        if action == "click" and direct_click is not None:
            element = direct_click(
                app_name,
                contains=contains,
                control_type=control_type,
                max_depth=max_depth,
                index=index,
            )
            x, y = element_center(element)
            payload = {
                "path": element.path,
                "label": element.label,
                "class_name": element.class_name,
                "x": round(x, 2),
                "y": round(y, 2),
                "action": action,
            }
        else:
            payload = run_ax_action(
                adapter=create_action_adapter(),
                element=element,
                action=action,
                drag_dx=drag_dx,
                drag_dy=drag_dy,
                scroll_clicks=scroll_clicks,
            )
        payload["automation_id"] = element.automation_id
    except Exception as exc:
        typer.echo(f"uia-click failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(payload, indent=2))


@app.command("uia-type")
def uia_type(
    app_name: Annotated[
        str,
        typer.Option("--app", help="Windows app or window name to inspect."),
    ],
    contains: Annotated[
        str,
        typer.Option("--contains", help="Substring match for the target label."),
    ],
    text: Annotated[
        str,
        typer.Option("--text", help="Text to type into the matched element."),
    ],
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", min=0, help="Maximum UI tree depth to inspect."),
    ] = 12,
    index: Annotated[
        int,
        typer.Option(
            "--index",
            min=1,
            help="1-based match index when multiple accessible elements match.",
        ),
    ] = 1,
    control_type: Annotated[
        str | None,
        typer.Option(
            "--control-type",
            help="Require an exact UIA control type name match.",
        ),
    ] = None,
    replace: Annotated[
        bool,
        typer.Option(
            "--replace/--append",
            help="Select all existing text before typing.",
        ),
    ] = False,
    interval: Annotated[
        float,
        typer.Option(
            "--interval",
            min=0.0,
            help="Delay between typed characters in seconds.",
        ),
    ] = 0.0,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Preview the UIA target and text without sending input.",
        ),
    ] = True,
) -> None:
    try:
        windows_accessibility = load_windows_accessibility()
        element = select_semantic_element(
            finder=windows_accessibility.find_matching_elements,
            app_name=app_name,
            contains=contains,
            control_type=control_type,
            max_depth=max_depth,
            index=index,
        )
        x, y = element_center(element)
        payload = {
            "path": element.path,
            "label": element.label,
            "class_name": element.class_name,
            "automation_id": element.automation_id,
            "x": round(x, 2),
            "y": round(y, 2),
            "text": text,
            "replace": replace,
            "bounds": {
                "x": element.x,
                "y": element.y,
                "width": element.width,
                "height": element.height,
            },
        }
        if dry_run:
            typer.echo(json.dumps(payload, indent=2))
            return

        direct_type = getattr(windows_accessibility, "type_into_matching_element", None)
        if direct_type is not None:
            element = direct_type(
                app_name,
                contains=contains,
                text=text,
                control_type=control_type,
                max_depth=max_depth,
                index=index,
                replace=replace,
                interval=interval,
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
        else:
            payload = type_into_element(
                adapter=create_action_adapter(),
                element=element,
                text=text,
                replace=replace,
                interval=interval,
            )
        payload["automation_id"] = element.automation_id
    except Exception as exc:
        typer.echo(f"uia-type failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(payload, indent=2))


def _load_atspi_accessibility():
    from app_automate.accessibility import linux_atspi

    return linux_atspi


@app.command("atspi-list")
def atspi_list(
    app_name: Annotated[
        str,
        typer.Option("--app", help="Linux app name to inspect."),
    ],
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", min=0, help="Maximum UI tree depth to inspect."),
    ] = 10,
    actionable_only: Annotated[
        bool,
        typer.Option(
            "--actionable-only/--all",
            help="Show only actionable controls such as buttons and fields.",
        ),
    ] = False,
    contains: Annotated[
        str | None,
        typer.Option(
            "--contains",
            help="Filter by case-insensitive label or role substring.",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json/--table", help="Emit JSON instead of a text table."),
    ] = False,
) -> None:
    try:
        atspi = _load_atspi_accessibility()
        elements = atspi.list_app_ui_elements(
            app_name,
            max_depth=max_depth,
            actionable_only=actionable_only,
        )
    except Exception as exc:
        typer.echo(f"atspi-list failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if contains is not None:
        needle = contains.lower()
        elements = [
            element
            for element in elements
            if needle in element.label.lower() or needle in (element.role or "").lower()
        ]

    if as_json:
        typer.echo(json.dumps([element.as_dict() for element in elements], indent=2))
        return

    typer.echo(format_semantic_elements(elements))


@app.command("atspi-click")
def atspi_click(
    app_name: Annotated[
        str,
        typer.Option("--app", help="Linux app name."),
    ],
    contains: Annotated[
        str,
        typer.Option("--contains", help="Substring match for the target label."),
    ],
    action: Annotated[
        Literal["click", "right-click", "double-click", "scroll", "drag"],
        typer.Option(
            "--action",
            help="Semantic action to perform on the matched element.",
        ),
    ] = "click",
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", min=0, help="Maximum UI tree depth."),
    ] = 10,
    index: Annotated[
        int,
        typer.Option("--index", min=1, help="1-based match index."),
    ] = 1,
    drag_dx: Annotated[
        float,
        typer.Option("--drag-dx", help="Drag delta in x for action=drag."),
    ] = 0.0,
    drag_dy: Annotated[
        float,
        typer.Option("--drag-dy", help="Drag delta in y for action=drag."),
    ] = 0.0,
    scroll_clicks: Annotated[
        int,
        typer.Option("--scroll-clicks", help="Signed scroll delta for action=scroll."),
    ] = 0,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Preview the target without acting.",
        ),
    ] = True,
) -> None:
    try:
        atspi = _load_atspi_accessibility()
        element = select_semantic_element(
            finder=atspi.find_matching_elements,
            app_name=app_name,
            contains=contains,
            max_depth=max_depth,
            index=index,
        )
        x, y = element_center(element)
        payload = {
            "path": element.path,
            "label": element.label,
            "class_name": element.class_name,
            "action": action,
            "x": round(x, 2),
            "y": round(y, 2),
            "bounds": {
                "x": element.x,
                "y": element.y,
                "width": element.width,
                "height": element.height,
            },
        }
        if action == "drag":
            payload["end_x"] = round(x + drag_dx, 2)
            payload["end_y"] = round(y + drag_dy, 2)
        if action == "scroll":
            payload["scroll_clicks"] = scroll_clicks

        if dry_run:
            typer.echo(json.dumps(payload, indent=2))
            return

        if action == "click":
            atspi.click_matching_element(
                app_name, contains=contains, max_depth=max_depth, index=index
            )
        else:
            payload = run_ax_action(
                adapter=create_action_adapter(),
                element=element,
                action=action,
                drag_dx=drag_dx,
                drag_dy=drag_dy,
                scroll_clicks=scroll_clicks,
            )
    except Exception as exc:
        typer.echo(f"atspi-click failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(payload, indent=2))


@app.command("atspi-type")
def atspi_type(
    app_name: Annotated[
        str,
        typer.Option("--app", help="Linux app name."),
    ],
    contains: Annotated[
        str,
        typer.Option("--contains", help="Substring match for the target field."),
    ],
    text: Annotated[
        str,
        typer.Option("--text", help="Text to type."),
    ],
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", min=0, help="Maximum UI tree depth."),
    ] = 12,
    index: Annotated[
        int,
        typer.Option("--index", min=1, help="1-based match index."),
    ] = 1,
    replace: Annotated[
        bool,
        typer.Option("--replace/--append", help="Select all existing text first."),
    ] = False,
    interval: Annotated[
        float,
        typer.Option("--interval", min=0.0, help="Delay between characters."),
    ] = 0.0,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--execute", help="Preview without typing."),
    ] = True,
) -> None:
    try:
        atspi = _load_atspi_accessibility()
        element = select_semantic_element(
            finder=atspi.find_matching_elements,
            app_name=app_name,
            contains=contains,
            max_depth=max_depth,
            index=index,
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
            "bounds": {
                "x": element.x,
                "y": element.y,
                "width": element.width,
                "height": element.height,
            },
        }
        if dry_run:
            typer.echo(json.dumps(payload, indent=2))
            return

        atspi.type_into_matching_element(
            app_name,
            contains=contains,
            text=text,
            max_depth=max_depth,
            index=index,
            replace=replace,
            interval=interval,
        )
    except Exception as exc:
        typer.echo(f"atspi-type failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(payload, indent=2))
