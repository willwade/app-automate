from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

import typer

from app_automate.accessibility.models import UIElement
from app_automate.adapters.base import ActionAdapter
from app_automate.config.validation import load_profile
from app_automate.platform_utils import is_windows

app = typer.Typer(
    help=(
        "App Automate builds app-specific UI maps and executes actions using "
        "saved profiles and local computer vision."
    )
)


def _profile_path(profile: Path) -> Path:
    if profile.is_dir():
        return profile / "profile.json"
    return profile


def _runtime_context(
    *,
    profile: Path,
    primary_x: float | None,
    primary_y: float | None,
    secondary_x: float | None,
    secondary_y: float | None,
    screenshot: Path | None = None,
    state_id: str | None = None,
) -> Any:
    profile_json_path = _profile_path(profile)
    loaded = load_profile(profile_json_path)
    RuntimeContext, detect_runtime_context, _, _ = _load_runtime_api()

    if primary_x is not None or primary_y is not None:
        if primary_x is None or primary_y is None:
            raise typer.BadParameter(
                "--primary-x and --primary-y must be supplied together"
            )
        if (secondary_x is None) ^ (secondary_y is None):
            raise typer.BadParameter(
                "--secondary-x and --secondary-y must be supplied together"
            )
        return RuntimeContext(
            profile=loaded,
            live_primary=(primary_x, primary_y),
            live_secondary=(
                (secondary_x, secondary_y)
                if secondary_x is not None and secondary_y is not None
                else None
            ),
            screenshot_path=screenshot,
        )

    return detect_runtime_context(
        profile=loaded,
        profile_dir=profile_json_path.parent,
        screenshot_path=screenshot,
        state_id=state_id,
    )


def _create_action_adapter() -> ActionAdapter:
    if is_windows():
        from app_automate.adapters.windows_input import WindowsInputAdapter

        return WindowsInputAdapter()
    from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter

    return PyAutoGuiAdapter()


def _load_macos_accessibility():
    from app_automate.accessibility import macos_ax

    return macos_ax


def _load_windows_accessibility():
    from app_automate.accessibility import windows_uia

    return windows_uia


def _load_cdp_accessibility():
    from app_automate.accessibility import cdp

    return cdp


def _load_training_api():
    from app_automate.builder.training import (
        create_training_bundle,
        rebuild_profile_with_anchor_overrides,
    )

    return create_training_bundle, rebuild_profile_with_anchor_overrides


def _load_runtime_api():
    from app_automate.runner.runtime import (
        RuntimeContext,
        detect_runtime_context,
        dry_run_command,
        summarize_detected_anchors,
    )

    return (
        RuntimeContext,
        detect_runtime_context,
        dry_run_command,
        summarize_detected_anchors,
    )


def _load_profile_describer():
    from app_automate.debug.inspect import describe_profile

    return describe_profile


def _load_debug_overlay_api():
    from app_automate.debug.overlay import crop_window_overlay, draw_runtime_overlay

    return crop_window_overlay, draw_runtime_overlay


def _load_runner_actions():
    from app_automate.runner.actions import click_resolved_command

    return click_resolved_command


def _write_debug_outputs(
    *,
    context: Any,
    result,
    output_dir: Path,
) -> tuple[Path, Path | None]:
    crop_window_overlay, draw_runtime_overlay = _load_debug_overlay_api()
    if context.screenshot_path is None:
        raise RuntimeError(
            "debug output requires a screenshot path in the runtime context"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = output_dir / "target-overlay.png"
    draw_runtime_overlay(
        context.screenshot_path,
        overlay_path,
        context=context,
        result=result,
    )

    window_path = None
    try:
        window_path = output_dir / "window-crop.png"
        crop_window_overlay(
            context.screenshot_path,
            window_path,
            context=context,
        )
    except Exception:
        window_path = None

    return overlay_path, window_path


def _format_semantic_elements(elements: list[UIElement]) -> str:
    lines = []
    for element in elements:
        indent = "  " * element.depth
        bounds = (
            f"{element.x},{element.y} {element.width}x{element.height}"
            if None not in {element.x, element.y, element.width, element.height}
            else "unknown"
        )
        status = "enabled" if element.enabled else "disabled"
        lines.append(
            f"{indent}{element.class_name}: {element.label} "
            f"[{bounds}] ({status}, children={element.child_count})"
        )
    return "\n".join(lines)


def _element_center(element) -> tuple[float, float]:
    if None in {element.x, element.y, element.width, element.height}:
        raise RuntimeError(f"element has no usable bounds: {element.path}")
    return (
        element.x + (element.width / 2.0),
        element.y + (element.height / 2.0),
    )


def _select_semantic_element(
    *,
    finder,
    app_name: str,
    contains: str,
    max_depth: int,
    index: int,
    control_type: str | None = None,
) -> object:
    query_kwargs = {
        "contains": contains,
        "max_depth": max_depth,
        "actionable_only": True,
        "enabled_only": True,
    }
    if control_type is not None:
        query_kwargs["control_type"] = control_type
    matches = finder(app_name, **query_kwargs)
    if not matches:
        raise RuntimeError(f'no accessible elements matched "{contains}" in {app_name}')
    if index < 1 or index > len(matches):
        raise RuntimeError(
            f"match index {index} is out of range; found {len(matches)} matches"
        )
    return matches[index - 1]


def _run_ax_action(
    *,
    adapter: ActionAdapter,
    element,
    action: str,
    drag_dx: float,
    drag_dy: float,
    scroll_clicks: int,
) -> dict[str, object]:
    x, y = _element_center(element)
    payload = {
        "path": element.path,
        "label": element.label,
        "class_name": element.class_name,
        "x": round(x, 2),
        "y": round(y, 2),
        "action": action,
    }

    if action == "click":
        adapter.click(x, y)
    elif action == "right-click":
        adapter.right_click(x, y)
    elif action == "double-click":
        adapter.double_click(x, y)
    elif action == "scroll":
        if scroll_clicks == 0:
            raise RuntimeError("--scroll-clicks must be non-zero for scroll")
        adapter.scroll(x, y, scroll_clicks)
        payload["scroll_clicks"] = scroll_clicks
    elif action == "drag":
        if drag_dx == 0 and drag_dy == 0:
            raise RuntimeError("--drag-dx or --drag-dy must be non-zero for drag")
        end_x = x + drag_dx
        end_y = y + drag_dy
        adapter.drag(x, y, end_x, end_y)
        payload["end_x"] = round(end_x, 2)
        payload["end_y"] = round(end_y, 2)
    else:
        raise RuntimeError(f"unsupported AX action: {action}")

    return payload


def _type_into_element(
    *,
    adapter: ActionAdapter,
    element,
    text: str,
    replace: bool,
    interval: float,
) -> dict[str, object]:
    x, y = _element_center(element)
    adapter.click(x, y)
    if replace:
        adapter.hotkey("ctrl", "a")
        adapter.hotkey("backspace")
    adapter.write_text(text, interval=interval)
    return {
        "path": element.path,
        "label": element.label,
        "class_name": element.class_name,
        "x": round(x, 2),
        "y": round(y, 2),
        "text": text,
        "replace": replace,
    }


def _parse_crop_box(raw: str) -> Any:
    from app_automate.builder.models import CropBox

    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 4:
        raise typer.BadParameter("crop box must be x,y,width,height")
    try:
        x, y, width, height = [int(part) for part in parts]
    except ValueError as exc:
        raise typer.BadParameter("crop box must contain integers") from exc
    return CropBox(x=x, y=y, width=width, height=height)


def _prompt_crop_box(label: str) -> Any | None:
    raw = typer.prompt(
        f"Enter replacement {label} crop as x,y,width,height (blank to keep current)",
        default="",
        show_default=False,
    ).strip()
    if not raw:
        return None
    return _parse_crop_box(raw)


def _run_train_review(
    *,
    bundle,
    output_dir: Path,
    settings_path: Path | None,
) -> None:
    _, rebuild_profile_with_anchor_overrides = _load_training_api()
    if bundle.review_path is None or bundle.review_image_path is None:
        return

    report = json.loads(bundle.review_path.read_text())
    typer.echo(f"Saved anchor review: {bundle.review_path}")
    typer.echo(f"Saved anchor review image: {bundle.review_image_path}")
    typer.echo(
        "Selected primary anchor: "
        f"{report['selected_primary']['anchor_id']} "
        f"(score {report['selected_primary']['quality_score']})"
    )
    selected_secondary = report.get("selected_secondary")
    if selected_secondary is not None:
        typer.echo(
            "Selected secondary anchor: "
            f"{selected_secondary['anchor_id']} "
            f"(score {selected_secondary['quality_score']})"
        )

    if typer.confirm("Accept selected anchors?", default=True):
        return

    primary_crop = _prompt_crop_box("primary")
    secondary_crop = None
    if selected_secondary is not None:
        secondary_crop = _prompt_crop_box("secondary")
    profile_path, review_path, review_image_path = (
        rebuild_profile_with_anchor_overrides(
            screenshot_path=bundle.screenshot_path,
            output_dir=output_dir,
            settings_path=settings_path,
            primary_crop=primary_crop,
            secondary_crop=secondary_crop,
        )
    )
    typer.echo(f"Updated profile: {profile_path}")
    typer.echo(f"Updated anchor review: {review_path}")
    typer.echo(f"Updated anchor review image: {review_image_path}")


@app.command("train")
def train(
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help=(
                "Optional path to an existing screenshot. Captures the main "
                "display if omitted."
            ),
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app",
            help=(
                "Capture and crop the front window of an app "
                "by name (macOS or Windows)."
            ),
        ),
    ] = None,
    settings: Annotated[
        Path | None,
        typer.Option(
            "--settings",
            help="Path to app-automate settings TOML.",
        ),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory for generated training assets.",
        ),
    ] = Path("examples/profiles/new-profile"),
    grid_size: Annotated[
        int | None,
        typer.Option(
            "--grid-size",
            min=40,
            help="Grid cell size in pixels for the numbered overlay.",
        ),
    ] = None,
    run_llm: Annotated[
        bool,
        typer.Option(
            "--run-llm/--skip-llm",
            help="Call the configured LLM and save a generated profile.",
        ),
    ] = True,
    review: Annotated[
        bool,
        typer.Option(
            "--review/--no-review",
            help="Prompt for manual anchor review after LLM training completes.",
        ),
    ] = False,
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            help=(
                "Build a semantic profile from a live accessibility backend "
                "instead of the visual/LLM path. Use 'uia' or 'cdp'."
            ),
        ),
    ] = None,
) -> None:
    if backend is not None:
        if not app_name and backend == "uia":
            typer.echo("--app is required with --backend uia", err=True)
            raise typer.Exit(code=1)
        try:
            from app_automate.builder.semantic_profile import build_semantic_profile

            path = build_semantic_profile(
                app_name=app_name or "",
                backend=backend,
                output_dir=output_dir,
            )
        except Exception as exc:
            typer.echo(f"train failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Saved semantic profile: {path}")
        return
    try:
        create_training_bundle, _ = _load_training_api()
        bundle = create_training_bundle(
            output_dir=output_dir,
            screenshot_path=screenshot,
            app_name=app_name,
            settings_path=settings,
            grid_size=grid_size,
            run_llm=run_llm,
        )
    except Exception as exc:
        typer.echo(f"train failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Saved screenshot: {bundle.screenshot_path}")
    typer.echo(f"Saved grid overlay: {bundle.grid_path}")
    typer.echo(f"Saved prompt input: {bundle.prompt_path}")
    if bundle.llm_output_path is not None:
        typer.echo(f"Saved LLM output: {bundle.llm_output_path}")
    if bundle.profile_path is not None:
        typer.echo(f"Saved profile: {bundle.profile_path}")
    if bundle.review_path is not None:
        typer.echo(f"Saved anchor review: {bundle.review_path}")
    if bundle.review_image_path is not None:
        typer.echo(f"Saved anchor review image: {bundle.review_image_path}")
    if review and run_llm:
        _run_train_review(
            bundle=bundle,
            output_dir=output_dir,
            settings_path=settings,
        )


@app.command("inspect")
def inspect_profile(
    profile: Annotated[
        Path,
        typer.Argument(help="Path to a profile directory or profile JSON file."),
    ],
) -> None:
    loaded = load_profile(_profile_path(profile))
    if loaded.type == "semantic":
        typer.echo(f"Profile: {loaded.profile_id} (semantic, backend={loaded.backend})")
        typer.echo(f"App: {loaded.app_name}")
        typer.echo(f"Elements: {len(loaded.semantic_elements)}")
        typer.echo("")
        for eid, el in sorted(loaded.semantic_elements.items()):
            parts = [f"  {eid}: {el.label} [{el.action.value}]"]
            if el.role:
                parts.append(f"role={el.role}")
            if el.automation_id:
                parts.append(f"automation_id={el.automation_id}")
            if el.selector:
                parts.append(f"selector={el.selector}")
            typer.echo(" ".join(parts))
        return
    describe_profile = _load_profile_describer()
    typer.echo(describe_profile(loaded))


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
        elements = _load_macos_accessibility().list_app_ui_elements(
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

    typer.echo(_format_semantic_elements(elements))


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
        element = _select_semantic_element(
            finder=_load_macos_accessibility().find_matching_elements,
            app_name=app_name,
            contains=contains,
            max_depth=max_depth,
            index=index,
        )
        x, y = _element_center(element)
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

        payload = _run_ax_action(
            adapter=_create_action_adapter(),
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
        elements = _load_windows_accessibility().list_app_ui_elements(
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

    typer.echo(_format_semantic_elements(elements))


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
        windows_accessibility = _load_windows_accessibility()
        element = _select_semantic_element(
            finder=windows_accessibility.find_matching_elements,
            app_name=app_name,
            contains=contains,
            control_type=control_type,
            max_depth=max_depth,
            index=index,
        )
        x, y = _element_center(element)
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
            x, y = _element_center(element)
            payload = {
                "path": element.path,
                "label": element.label,
                "class_name": element.class_name,
                "x": round(x, 2),
                "y": round(y, 2),
                "action": action,
            }
        else:
            payload = _run_ax_action(
                adapter=_create_action_adapter(),
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
        windows_accessibility = _load_windows_accessibility()
        element = _select_semantic_element(
            finder=windows_accessibility.find_matching_elements,
            app_name=app_name,
            contains=contains,
            control_type=control_type,
            max_depth=max_depth,
            index=index,
        )
        x, y = _element_center(element)
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
            x, y = _element_center(element)
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
            payload = _type_into_element(
                adapter=_create_action_adapter(),
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


@app.command("list-elements")
def list_elements(
    profile: Annotated[
        Path,
        typer.Argument(help="Path to a profile directory or profile JSON file."),
    ],
) -> None:
    loaded = load_profile(_profile_path(profile))
    if loaded.type == "semantic":
        for eid, el in sorted(loaded.semantic_elements.items()):
            typer.echo(f"{eid}: {el.label} [{el.action.value}]")
        return
    for element_id, element in sorted(loaded.elements.items()):
        typer.echo(f"{element_id}: {element.label} [{element.layout.value}]")


@app.command("dry-run")
def dry_run(
    command: Annotated[
        str,
        typer.Argument(help="Natural language element name or alias."),
    ],
    profile: Annotated[
        Path,
        typer.Option(
            "--profile", help="Path to a profile directory or profile JSON file."
        ),
    ] = Path("examples/profiles/camera-demo/profile.json"),
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help="Optional full-screen screenshot path for anchor detection.",
        ),
    ] = None,
    primary_x: Annotated[
        float | None,
        typer.Option("--primary-x", help="Live primary anchor x-coordinate."),
    ] = None,
    primary_y: Annotated[
        float | None,
        typer.Option("--primary-y", help="Live primary anchor y-coordinate."),
    ] = None,
    secondary_x: Annotated[
        float | None,
        typer.Option("--secondary-x", help="Live secondary anchor x-coordinate."),
    ] = None,
    secondary_y: Annotated[
        float | None,
        typer.Option("--secondary-y", help="Live secondary anchor y-coordinate."),
    ] = None,
) -> None:
    loaded = load_profile(_profile_path(profile))
    if loaded.type == "semantic":
        from app_automate.runner.runtime import dry_run_semantic_command

        result = dry_run_semantic_command(command, loaded)
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    context = _runtime_context(
        profile=profile,
        screenshot=screenshot,
        primary_x=primary_x,
        primary_y=primary_y,
        secondary_x=secondary_x,
        secondary_y=secondary_y,
    )
    _, _, dry_run_command, _ = _load_runtime_api()
    result = dry_run_command(command, context)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@app.command("click")
def click(
    command: Annotated[
        str,
        typer.Argument(help="Natural language element name or alias."),
    ],
    profile: Annotated[
        Path,
        typer.Option(
            "--profile", help="Path to a profile directory or profile JSON file."
        ),
    ] = Path("examples/profiles/camera-demo/profile.json"),
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help="Optional full-screen screenshot path for anchor detection.",
        ),
    ] = None,
    primary_x: Annotated[
        float | None,
        typer.Option("--primary-x", help="Live primary anchor x-coordinate."),
    ] = None,
    primary_y: Annotated[
        float | None,
        typer.Option("--primary-y", help="Live primary anchor y-coordinate."),
    ] = None,
    secondary_x: Annotated[
        float | None,
        typer.Option("--secondary-x", help="Live secondary anchor x-coordinate."),
    ] = None,
    secondary_y: Annotated[
        float | None,
        typer.Option("--secondary-y", help="Live secondary anchor y-coordinate."),
    ] = None,
    text: Annotated[
        str | None,
        typer.Option("--text", help="Text to type for semantic type actions."),
    ] = None,
) -> None:
    loaded = load_profile(_profile_path(profile))
    if loaded.type == "semantic":
        from app_automate.runner.runtime import execute_semantic_command

        result = execute_semantic_command(command, loaded, text=text)
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    context = _runtime_context(
        profile=profile,
        screenshot=screenshot,
        primary_x=primary_x,
        primary_y=primary_y,
        secondary_x=secondary_x,
        secondary_y=secondary_y,
    )
    _, _, dry_run_command, _ = _load_runtime_api()
    result = dry_run_command(command, context)
    adapter = _create_action_adapter()
    click_resolved_command = _load_runner_actions()
    click_resolved_command(adapter, result)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@app.command("locate-anchors")
def locate_anchors(
    profile: Annotated[
        Path,
        typer.Option(
            "--profile", help="Path to a profile directory or profile JSON file."
        ),
    ] = Path("examples/profiles/camera-demo/profile.json"),
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help=(
                "Optional full-screen screenshot path. Captures the main "
                "display if omitted."
            ),
        ),
    ] = None,
) -> None:
    context = _runtime_context(
        profile=profile,
        screenshot=screenshot,
        primary_x=None,
        primary_y=None,
        secondary_x=None,
        secondary_y=None,
    )
    _, _, _, summarize_detected_anchors = _load_runtime_api()
    typer.echo(json.dumps(summarize_detected_anchors(context).model_dump(), indent=2))


@app.command("debug-target")
def debug_target(
    command: Annotated[
        str,
        typer.Argument(help="Natural language element name or alias."),
    ],
    profile: Annotated[
        Path,
        typer.Option(
            "--profile", help="Path to a profile directory or profile JSON file."
        ),
    ] = Path("examples/profiles/camera-demo/profile.json"),
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help=(
                "Optional full-screen screenshot path. Captures the main "
                "display if omitted."
            ),
        ),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory for annotated debug images.",
        ),
    ] = Path("debug-output"),
    primary_x: Annotated[
        float | None,
        typer.Option("--primary-x", help="Live primary anchor x-coordinate."),
    ] = None,
    primary_y: Annotated[
        float | None,
        typer.Option("--primary-y", help="Live primary anchor y-coordinate."),
    ] = None,
    secondary_x: Annotated[
        float | None,
        typer.Option("--secondary-x", help="Live secondary anchor x-coordinate."),
    ] = None,
    secondary_y: Annotated[
        float | None,
        typer.Option("--secondary-y", help="Live secondary anchor y-coordinate."),
    ] = None,
) -> None:
    context = _runtime_context(
        profile=profile,
        screenshot=screenshot,
        primary_x=primary_x,
        primary_y=primary_y,
        secondary_x=secondary_x,
        secondary_y=secondary_y,
    )
    _, _, dry_run_command, summarize_detected_anchors = _load_runtime_api()
    result = dry_run_command(command, context)
    overlay_path, window_path = _write_debug_outputs(
        context=context,
        result=result,
        output_dir=output_dir,
    )

    payload = {
        "result": result.model_dump(mode="json"),
        "overlay_path": str(overlay_path),
        "window_path": str(window_path) if window_path is not None else None,
        "anchors": summarize_detected_anchors(context).model_dump(mode="json"),
    }
    typer.echo(json.dumps(payload, indent=2))


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
        cdp = _load_cdp_accessibility()
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
        cdp = _load_cdp_accessibility()
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
    typer.echo(_format_semantic_elements(elements))


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
        cdp = _load_cdp_accessibility()
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
            x, y = _element_center(element)
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
        x, y = _element_center(element)
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
        cdp = _load_cdp_accessibility()
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
            x, y = _element_center(element)
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
        x, y = _element_center(element)
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


@app.command("whats-here")
def whats_here(
    radius: Annotated[
        int,
        typer.Option(
            "--radius",
            help="Half-width of the search box around the cursor in pixels.",
        ),
    ] = 96,
    backend: Annotated[
        str,
        typer.Option(
            "--backend",
            help="Backend to use: uia or cdp.",
        ),
    ] = "uia",
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app",
            help="App to query (required for UIA). If omitted, queries all windows.",
        ),
    ] = None,
    port: Annotated[
        int,
        typer.Option("--port", help="CDP port."),
    ] = 9222,
) -> None:
    try:
        import pyautogui

        mx, my = pyautogui.position()
        print(f"Cursor at ({mx}, {my}), searching {radius * 2}x{radius * 2} box...")

        x1 = mx - radius
        y1 = my - radius
        x2 = mx + radius
        y2 = my + radius

        if backend == "uia":
            _whats_here_uia(app_name, x1, y1, x2, y2)
        elif backend == "cdp":
            _whats_here_cdp(port, x1, y1, x2, y2)
        else:
            print(f"Unknown backend: {backend}")
            raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"whats-here failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _foreground_app_name() -> str | None:
    if not is_windows():
        return None
    import ctypes

    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return None
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(length)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
    title = buf.value
    if not title:
        return None
    for sep in (" - ", " — "):
        if sep in title:
            title = title.split(sep)[-1].strip()
    return title


def _whats_here_uia(app_name: str | None, x1: int, y1: int, x2: int, y2: int) -> None:
    from app_automate.accessibility import windows_uia

    if app_name:
        elements = windows_uia.list_app_ui_elements(
            app_name, max_depth=15, actionable_only=False
        )
    else:
        app_name = _foreground_app_name()
        if app_name:
            print(f"  Foreground window: {app_name}")
        elements = windows_uia.list_app_ui_elements(
            app_name or "", max_depth=15, actionable_only=False
        )

    nearby = []
    for el in elements:
        if el.x is None or el.y is None:
            continue
        el_x1 = el.x
        el_y1 = el.y
        el_x2 = el.x + (el.width or 0)
        el_y2 = el.y + (el.height or 0)
        if el_x2 < x1 or el_x1 > x2 or el_y2 < y1 or el_y1 > y2:
            continue
        nearby.append(el)

    if not nearby:
        print("No UIA elements found near cursor.")
        return

    nearby.sort(key=lambda e: (e.width or 0) * (e.height or 0))

    print(f"\n{len(nearby)} elements found:\n")
    print(f"  {'Label':<30} {'Role':<20} {'X':>5} {'Y':>5} {'W':>5} {'H':>5}")
    print(f"  {'-' * 30} {'-' * 20} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5}")
    for el in nearby:
        label = (el.label or "")[:30]
        role = (el.role or el.class_name or "")[:20]
        print(
            f"  {label:<30} {role:<20} "
            f"{el.x or 0:>5} {el.y or 0:>5} "
            f"{el.width or 0:>5} {el.height or 0:>5}"
        )


def _whats_here_cdp(port: int, x1: int, y1: int, x2: int, y2: int) -> None:
    from app_automate.accessibility import cdp

    elements = cdp.list_cdp_elements(port, actionable_only=False)

    nearby = []
    for el in elements:
        if el.x is None or el.y is None:
            continue
        el_x1 = el.x
        el_y1 = el.y
        el_x2 = el.x + (el.width or 0)
        el_y2 = el.y + (el.height or 0)
        if el_x2 < x1 or el_x1 > x2 or el_y2 < y1 or el_y1 > y2:
            continue
        nearby.append(el)

    if not nearby:
        print("No CDP elements found near cursor.")
        return

    nearby.sort(key=lambda e: (e.width or 0) * (e.height or 0))

    print(f"\n{len(nearby)} elements found:\n")
    print(f"  {'Label':<30} {'Role':<20} {'X':>5} {'Y':>5} {'W':>5} {'H':>5}")
    print(f"  {'-' * 30} {'-' * 20} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5}")
    for el in nearby:
        label = (el.label or "")[:30]
        role = (el.role or "")[:20]
        print(
            f"  {label:<30} {role:<20} "
            f"{el.x or 0:>5} {el.y or 0:>5} "
            f"{el.width or 0:>5} {el.height or 0:>5}"
        )


@app.command("probe")
def probe(
    app_name: Annotated[
        str,
        typer.Argument(help="App name or window title to probe."),
    ],
) -> None:
    result = _probe_app(app_name)
    typer.echo(json.dumps(result, indent=2))


def _probe_app(app_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "app_name": app_name,
        "uia": None,
        "cdp": None,
        "recommendation": None,
    }

    uia_elements = _probe_uia(app_name)
    result["uia"] = uia_elements

    cdp_info = _probe_cdp()
    result["cdp"] = cdp_info

    if (
        uia_elements["interactive_with_bounds"] >= 20
        and not uia_elements["title_bar_only"]
    ):
        result["recommendation"] = "uia"
        result["reason"] = (
            f"UIA found {uia_elements['interactive_with_bounds']} "
            "interactive elements with bounds"
        )
    elif cdp_info["available"]:
        result["recommendation"] = "cdp"
        result["reason"] = (
            f"CDP available (page: {cdp_info['page_title']}), "
            f"UIA only found {uia_elements['interactive_with_bounds']} elements"
        )
    else:
        result["recommendation"] = "cv"
        result["reason"] = (
            "UIA coverage is poor and CDP is not available; "
            "use visual profile with train --app"
        )

    return result


def _probe_uia(app_name: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "interactive_with_bounds": 0,
        "title_bar_only": False,
    }
    try:
        wa = _load_windows_accessibility()
        elements = wa.list_app_ui_elements(app_name, max_depth=15, actionable_only=True)
        with_bounds = [e for e in elements if e.has_bounds]
        info["available"] = True
        info["interactive_with_bounds"] = len(with_bounds)
        info["total_elements"] = len(elements)
        roles = set(e.class_name for e in with_bounds)
        info["roles"] = sorted(roles)
        title_roles = {
            "ButtonControl",
            "MenuBarControl",
            "MenuItemControl",
            "TitleBarControl",
        }
        non_title = [e for e in with_bounds if e.class_name not in title_roles]
        if with_bounds and not non_title:
            info["title_bar_only"] = True
    except Exception:
        info["available"] = False
        info["error"] = "no matching window found or UIA unavailable"
    return info


def _probe_cdp() -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "port": 9222,
    }
    try:
        cdp = _load_cdp_accessibility()
        status = cdp.cdp_status()
        if status.get("listening") == "true":
            info["available"] = True
            info["page_title"] = status.get("page_title", "")
            info["page_url"] = status.get("page_url", "")
            try:
                elements = cdp.list_cdp_elements(actionable_only=True)
                info["interactive_elements"] = len(elements)
            except Exception:
                info["interactive_elements"] = "error"
    except Exception:
        info["available"] = False
    return info


def main() -> None:
    app()
