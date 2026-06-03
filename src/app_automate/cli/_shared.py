from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def profile_path(profile: Path) -> Path:
    if profile.is_dir():
        return profile / "profile.json"
    return profile


def runtime_context(
    *,
    profile: Path,
    primary_x: float | None,
    primary_y: float | None,
    secondary_x: float | None,
    secondary_y: float | None,
    screenshot: Path | None = None,
    state_id: str | None = None,
) -> Any:
    profile_json_path = profile_path(profile)
    loaded = load_profile(profile_json_path)
    RuntimeContext, detect_runtime_context, _, _ = load_runtime_api()

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


def create_action_adapter() -> ActionAdapter:
    if is_windows():
        from app_automate.adapters.windows_input import WindowsInputAdapter

        return WindowsInputAdapter()
    from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter

    return PyAutoGuiAdapter()


def load_macos_accessibility():
    from app_automate.accessibility import macos_ax

    return macos_ax


def load_windows_accessibility():
    from app_automate.accessibility import windows_uia

    return windows_uia


def load_cdp_accessibility():
    from app_automate.accessibility import cdp

    return cdp


def load_training_api():
    from app_automate.builder.training import (
        create_training_bundle,
        rebuild_profile_with_anchor_overrides,
    )

    return create_training_bundle, rebuild_profile_with_anchor_overrides


def load_runtime_api():
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


def load_profile_describer():
    from app_automate.debug.inspect import describe_profile

    return describe_profile


def load_debug_overlay_api():
    from app_automate.debug.overlay import crop_window_overlay, draw_runtime_overlay

    return crop_window_overlay, draw_runtime_overlay


def load_runner_actions():
    from app_automate.runner.actions import click_resolved_command

    return click_resolved_command


def write_debug_outputs(
    *,
    context: Any,
    result,
    output_dir: Path,
) -> tuple[Path, Path | None]:
    crop_window_overlay, draw_runtime_overlay = load_debug_overlay_api()
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


def format_semantic_elements(elements: list[UIElement]) -> str:
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


def element_center(element) -> tuple[float, float]:
    if None in {element.x, element.y, element.width, element.height}:
        raise RuntimeError(f"element has no usable bounds: {element.path}")
    return (
        element.x + (element.width / 2.0),
        element.y + (element.height / 2.0),
    )


def select_semantic_element(
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


def run_ax_action(
    *,
    adapter: ActionAdapter,
    element,
    action: str,
    drag_dx: float,
    drag_dy: float,
    scroll_clicks: int,
) -> dict[str, object]:
    x, y = element_center(element)
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


def type_into_element(
    *,
    adapter: ActionAdapter,
    element,
    text: str,
    replace: bool,
    interval: float,
) -> dict[str, object]:
    x, y = element_center(element)
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


def parse_crop_box(raw: str) -> Any:
    from app_automate.builder.models import CropBox

    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 4:
        raise typer.BadParameter("crop box must be x,y,width,height")
    try:
        x, y, width, height = [int(part) for part in parts]
    except ValueError as exc:
        raise typer.BadParameter("crop box must contain integers") from exc
    return CropBox(x=x, y=y, width=width, height=height)


def prompt_crop_box(label: str) -> Any | None:
    raw = typer.prompt(
        f"Enter replacement {label} crop as x,y,width,height (blank to keep current)",
        default="",
        show_default=False,
    ).strip()
    if not raw:
        return None
    return parse_crop_box(raw)


def run_train_review(
    *,
    bundle,
    output_dir: Path,
    settings_path: Path | None,
) -> None:
    _, rebuild_profile_with_anchor_overrides = load_training_api()
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

    primary_crop = prompt_crop_box("primary")
    secondary_crop = None
    if selected_secondary is not None:
        secondary_crop = prompt_crop_box("secondary")
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
