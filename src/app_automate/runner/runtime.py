from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app_automate.config.models import Anchors, AppProfile, ElementDefinition
from app_automate.runner.resolver import resolve_element_position
from app_automate.runner.transform import compute_transform_from_anchors


@dataclass(slots=True)
class RuntimeContext:
    profile: AppProfile
    live_primary: tuple[float, float]
    live_secondary: tuple[float, float] | None = None
    screenshot_path: Path | None = None
    primary_confidence: float | None = None
    secondary_confidence: float | None = None
    active_state_id: str | None = None
    anchors: Anchors | None = None
    elements: dict[str, ElementDefinition] | None = None


class ResolvedCommand(BaseModel):
    element_id: str
    label: str
    action: str
    x: float
    y: float
    layout: str
    state_id: str | None = None


class SemanticResolvedCommand(BaseModel):
    element_id: str
    label: str
    action: str
    backend: str
    selector: str | None = None
    automation_id: str | None = None
    role: str | None = None
    x: float | None = None
    y: float | None = None
    state_id: str | None = None


class AnchorDetectionResult(BaseModel):
    screenshot_path: str
    primary: dict[str, float]
    secondary: dict[str, float] | None = None
    detected_state: str | None = None


class StateMatchResult(BaseModel):
    state_id: str
    matched: bool
    region_results: list[dict[str, Any]]


def detect_active_state(
    *,
    profile: AppProfile,
    profile_dir: Path,
    screenshot_path: Path,
) -> tuple[str | None, dict[str, StateMatchResult]]:
    from app_automate.runner.anchors import locate_anchor

    if not profile.states:
        return None, {}

    state_matches: dict[str, StateMatchResult] = {}

    for state_id, state in profile.states.items():
        if state.signature is None:
            state_matches[state_id] = StateMatchResult(
                state_id=state_id,
                matched=False,
                region_results=[],
            )
            continue

        region_results: list[dict[str, Any]] = []
        all_required_matched = True
        any_region_checked = False

        for region in state.signature.check_regions:
            template_path = profile_dir / region.path
            if not template_path.exists():
                region_results.append(
                    {
                        "path": region.path,
                        "matched": False,
                        "confidence": 0.0,
                        "error": "template not found",
                    }
                )
                if region.required:
                    all_required_matched = False
                continue

            any_region_checked = True
            try:
                match = locate_anchor(
                    template_path,
                    screenshot_path,
                    threshold=region.confidence_threshold,
                )
                match_x = getattr(match, "x", 0)
                match_y = getattr(match, "y", 0)
                match_conf = getattr(match, "confidence", 0.0)
                expected_x = abs(float(match_x) - region.x) < 5
                expected_y = abs(float(match_y) - region.y) < 5
                matched = expected_x and expected_y

                region_results.append(
                    {
                        "path": region.path,
                        "matched": matched,
                        "confidence": match_conf,
                        "expected": (region.x, region.y),
                        "actual": (float(match_x), float(match_y)),
                    }
                )

                if region.required and not matched:
                    all_required_matched = False
            except Exception as exc:
                region_results.append(
                    {
                        "path": region.path,
                        "matched": False,
                        "error": str(exc),
                    }
                )
                if region.required:
                    all_required_matched = False

        state_matched = any_region_checked and all_required_matched
        state_matches[state_id] = StateMatchResult(
            state_id=state_id,
            matched=state_matched,
            region_results=region_results,
        )

    for state_id, result in state_matches.items():
        if result.matched:
            return state_id, state_matches

    return profile.default_state, state_matches


def detect_runtime_context(
    *,
    profile: AppProfile,
    profile_dir: Path,
    screenshot_path: Path | None = None,
    state_id: str | None = None,
) -> RuntimeContext:
    from app_automate.runner.anchors import locate_anchor
    from app_automate.vision.screenshots import capture_main_display_temp

    active_screenshot = screenshot_path or capture_main_display_temp()

    detected_state_id = state_id
    if profile.states and detected_state_id is None:
        detected_state_id, _ = detect_active_state(
            profile=profile,
            profile_dir=profile_dir,
            screenshot_path=active_screenshot,
        )

    if profile.states and detected_state_id:
        active_state = profile.states.get(detected_state_id)
        if active_state is None:
            raise ValueError(f"state '{detected_state_id}' not found in profile")
        anchors = active_state.anchors
        elements = active_state.elements
    elif profile.anchors is not None:
        anchors = profile.anchors
        elements = profile.elements
    else:
        raise ValueError("profile has no valid anchors configuration")

    primary_template = profile_dir / anchors.primary.path
    primary_match = locate_anchor(
        primary_template,
        active_screenshot,
        threshold=anchors.primary.confidence_threshold,
    )

    secondary_match = None
    if anchors.secondary is not None:
        secondary_template = profile_dir / anchors.secondary.path
        secondary_match = locate_anchor(
            secondary_template,
            active_screenshot,
            threshold=anchors.secondary.confidence_threshold,
        )

    primary_x = getattr(primary_match, "x", 0)
    primary_y = getattr(primary_match, "y", 0)
    primary_conf = getattr(primary_match, "confidence", 0.0)
    secondary_x = 0
    secondary_y = 0
    secondary_conf = 0.0
    if secondary_match is not None:
        secondary_x = getattr(secondary_match, "x", 0)
        secondary_y = getattr(secondary_match, "y", 0)
        secondary_conf = getattr(secondary_match, "confidence", 0.0)

    return RuntimeContext(
        profile=profile,
        live_primary=(float(primary_x), float(primary_y)),
        live_secondary=(
            (float(secondary_x), float(secondary_y))
            if secondary_match is not None
            else None
        ),
        screenshot_path=active_screenshot,
        primary_confidence=primary_conf,
        secondary_confidence=(secondary_conf if secondary_match is not None else None),
        active_state_id=detected_state_id,
        anchors=anchors,
        elements=elements,
    )


def summarize_detected_anchors(context: RuntimeContext) -> AnchorDetectionResult:
    payload = {
        "x": context.live_primary[0],
        "y": context.live_primary[1],
        "confidence": context.primary_confidence or 0.0,
    }
    secondary = None
    if context.live_secondary is not None:
        secondary = {
            "x": context.live_secondary[0],
            "y": context.live_secondary[1],
            "confidence": context.secondary_confidence or 0.0,
        }
    return AnchorDetectionResult(
        screenshot_path=str(context.screenshot_path) if context.screenshot_path else "",
        primary=payload,
        secondary=secondary,
        detected_state=context.active_state_id,
    )


def resolve_element_id(command: str, context: RuntimeContext) -> str:
    normalized = command.strip().casefold()
    elements = context.elements or context.profile.elements
    for element_id, element in elements.items():
        candidates = [element.label, *element.aliases, element_id]
        if any(normalized == candidate.casefold() for candidate in candidates):
            return element_id
    raise KeyError(f"no element matches command: {command}")


def dry_run_command(command: str, context: RuntimeContext) -> ResolvedCommand:
    element_id = resolve_element_id(command, context)
    elements = context.elements or context.profile.elements
    element = elements[element_id]
    anchors = context.anchors or context.profile.anchors
    if anchors is None:
        raise ValueError("no anchors available for transform")
    transform = compute_transform_from_anchors(
        anchors,
        live_primary=context.live_primary,
        live_secondary=context.live_secondary,
    )
    x, y = resolve_element_position(element, transform)
    return ResolvedCommand(
        element_id=element_id,
        label=element.label,
        action=element.action.value,
        x=round(x, 2),
        y=round(y, 2),
        layout=element.layout.value,
        state_id=context.active_state_id,
    )


def resolve_semantic_element_id(command: str, profile: AppProfile) -> str:
    normalized = command.strip().casefold()
    for element_id, element in profile.semantic_elements.items():
        candidates = [element.label, *element.aliases, element_id]
        if any(normalized == candidate.casefold() for candidate in candidates):
            return element_id
    raise KeyError(f"no element matches command: {command}")


def dry_run_semantic_command(
    command: str, profile: AppProfile
) -> SemanticResolvedCommand:
    element_id = resolve_semantic_element_id(command, profile)
    element = profile.semantic_elements[element_id]

    if element.action.value == "shortcut" and element.shortcut:
        return SemanticResolvedCommand(
            element_id=element_id,
            label=element.label,
            action=element.action.value,
            backend="shortcut",
            selector=element.selector,
            automation_id=element.automation_id,
            role=element.role,
            x=None,
            y=None,
        )

    backend = profile.backend or "uia"

    x: float | None = None
    y: float | None = None

    if backend == "uia":
        x, y = _uia_locate(profile.app_name, element)
    elif backend == "cdp":
        x, y = _cdp_locate(element)
    elif backend == "atspi":
        x, y = _atspi_locate(profile.app_name, element)

    return SemanticResolvedCommand(
        element_id=element_id,
        label=element.label,
        action=element.action.value,
        backend=backend,
        selector=element.selector,
        automation_id=element.automation_id,
        role=element.role,
        x=round(x, 2) if x is not None else None,
        y=round(y, 2) if y is not None else None,
    )


def execute_semantic_command(
    command: str, profile: AppProfile, *, text: str | None = None
) -> SemanticResolvedCommand:
    element_id = resolve_semantic_element_id(command, profile)
    element = profile.semantic_elements[element_id]

    if element.action.value == "shortcut" and element.shortcut:
        import pyautogui

        keys = element.shortcut.keys.split("+")
        pyautogui.hotkey(*keys)
        return SemanticResolvedCommand(
            element_id=element_id,
            label=element.label,
            action=element.action.value,
            backend="shortcut",
            selector=element.selector,
            automation_id=element.automation_id,
            role=element.role,
            x=None,
            y=None,
        )

    backend = profile.backend or "uia"

    x: float | None = None
    y: float | None = None

    if backend == "uia":
        x, y = _uia_execute(profile.app_name, element, text=text)
    elif backend == "cdp":
        x, y = _cdp_execute(element, text=text)
    elif backend == "atspi":
        x, y = _atspi_execute(profile.app_name, element, text=text)

    return SemanticResolvedCommand(
        element_id=element_id,
        label=element.label,
        action=element.action.value,
        backend=backend,
        selector=element.selector,
        automation_id=element.automation_id,
        role=element.role,
        x=round(x, 2) if x is not None else None,
        y=round(y, 2) if y is not None else None,
    )


def _uia_locate(app_name: str, element: Any) -> tuple[float | None, float | None]:
    from app_automate.accessibility import windows_uia

    kwargs: dict[str, Any] = {
        "contains": element.label,
        "max_depth": 15,
        "actionable_only": True,
        "enabled_only": True,
    }
    if element.automation_id:
        matches = windows_uia.find_matching_elements(
            app_name, automation_id=element.automation_id, **kwargs
        )
    elif element.role:
        matches = windows_uia.find_matching_elements(
            app_name, control_type=element.role, **kwargs
        )
    else:
        matches = windows_uia.find_matching_elements(app_name, **kwargs)
    if not matches:
        raise RuntimeError(f"UIA could not find element matching '{element.label}'")
    target = matches[0]
    if target.x is None or target.y is None:
        return None, None
    return (
        target.x + (target.width or 0) / 2.0,
        target.y + (target.height or 0) / 2.0,
    )


def _uia_execute(
    app_name: str, element: Any, *, text: str | None = None
) -> tuple[float | None, float | None]:
    from app_automate.accessibility import windows_uia
    from app_automate.adapters.windows_input import WindowsInputAdapter

    action = element.action.value
    click_kwargs: dict[str, Any] = {
        "contains": element.label,
        "max_depth": 15,
    }
    find_kwargs: dict[str, Any] = {
        "contains": element.label,
        "max_depth": 15,
        "actionable_only": True,
        "enabled_only": True,
    }
    if element.automation_id:
        click_kwargs["automation_id"] = element.automation_id
        find_kwargs["automation_id"] = element.automation_id
    elif element.role:
        click_kwargs["control_type"] = element.role
        find_kwargs["control_type"] = element.role

    if action in ("hotkey", "wait"):
        adapter = WindowsInputAdapter()
        if action == "hotkey":
            keys = (element.hotkey or "").split("+")
            adapter.hotkey(*keys)
        elif action == "wait":
            import time

            time.sleep((element.wait_ms or 500) / 1000.0)
        return None, None

    if action == "click":
        target = windows_uia.click_matching_element(app_name, **click_kwargs)
    elif action == "type":
        type_text = text or element.text
        if type_text is None:
            raise RuntimeError(
                f"type action requires --text for element '{element.label}'"
            )
        target = windows_uia.type_into_matching_element(
            app_name, text=type_text, **click_kwargs
        )
    else:
        matches = windows_uia.find_matching_elements(app_name, **find_kwargs)
        if not matches:
            raise RuntimeError(f"UIA could not find element matching '{element.label}'")
        target = matches[0]

    if target.x is None or target.y is None:
        return None, None
    cx = target.x + (target.width or 0) / 2.0
    cy = target.y + (target.height or 0) / 2.0

    if action in ("drag", "double_click", "right_click", "scroll"):
        adapter = WindowsInputAdapter()
        if action == "drag":
            dx = element.drag_dx or 0
            dy = element.drag_dy or 0
            adapter.drag(cx, cy, cx + dx, cy + dy)
        elif action == "double_click":
            adapter.double_click(cx, cy)
        elif action == "right_click":
            adapter.right_click(cx, cy)
        elif action == "scroll":
            adapter.scroll(cx, cy, element.scroll_clicks or 0)

    return cx, cy


def _cdp_locate(element: Any) -> tuple[float | None, float | None]:
    from app_automate.accessibility import cdp

    if element.selector:
        return _cdp_locate_by_selector(element.selector)
    matches = cdp.find_cdp_elements(
        contains=element.label,
        actionable_only=True,
        enabled_only=True,
    )
    if not matches:
        raise RuntimeError(f"CDP could not find element matching '{element.label}'")
    target = matches[0]
    if target.x is None or target.y is None:
        return None, None
    return (
        target.x + (target.width or 0) / 2.0,
        target.y + (target.height or 0) / 2.0,
    )


def _cdp_locate_by_selector(selector: str) -> tuple[float | None, float | None]:
    from app_automate.accessibility.cdp import cdp_session

    with cdp_session() as page:
        locator = page.locator(selector)
        if locator.count() == 0:
            raise RuntimeError(f"CDP selector matched nothing: {selector}")
        box = locator.first.bounding_box()
        if box is None:
            return None, None
        return box["x"] + box["width"] / 2.0, box["y"] + box["height"] / 2.0


def _cdp_execute(
    element: Any, *, text: str | None = None
) -> tuple[float | None, float | None]:
    from app_automate.accessibility import cdp

    action = element.action.value

    if action in ("hotkey", "wait"):
        from app_automate.accessibility.cdp import cdp_session

        with cdp_session() as page:
            if action == "hotkey":
                keys = (element.hotkey or "").split("+")
                page.keyboard.press("+".join(keys))
            elif action == "wait":
                page.wait_for_timeout(element.wait_ms or 500)
        return None, None

    if action == "click":
        target = cdp.click_cdp_element(
            contains=element.label,
            selector=element.selector,
        )
    elif action == "type":
        type_text = text or element.text
        if type_text is None:
            raise RuntimeError(
                f"type action requires --text for element '{element.label}'"
            )
        target = cdp.type_into_cdp_element(
            contains=element.label,
            text=type_text,
            selector=element.selector,
        )
    elif action in ("drag", "double_click", "right_click", "scroll"):
        x, y = _cdp_locate(element)
        if x is None or y is None:
            raise RuntimeError(
                f"CDP could not locate element for {action}: {element.label}"
            )
        from app_automate.accessibility.cdp import cdp_session

        with cdp_session() as page:
            if action == "drag":
                dx = element.drag_dx or 0
                dy = element.drag_dy or 0
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.move(x + dx, y + dy, steps=20)
                page.mouse.up()
            elif action == "double_click":
                page.mouse.dblclick(x, y)
            elif action == "right_click":
                page.mouse.click(x, y, button="right")
            elif action == "scroll":
                page.mouse.wheel(0, element.scroll_clicks or 0)
        return x, y
    else:
        return _cdp_locate(element)

    if target.x is None or target.y is None:
        return None, None
    return (
        target.x + (target.width or 0) / 2.0,
        target.y + (target.height or 0) / 2.0,
    )


def _atspi_locate(app_name: str, element: Any) -> tuple[float | None, float | None]:
    from app_automate.accessibility import linux_atspi

    kwargs: dict[str, Any] = {
        "contains": element.label,
        "max_depth": 15,
        "actionable_only": True,
        "enabled_only": True,
    }
    if element.role:
        kwargs["control_type"] = element.role
    matches = linux_atspi.find_matching_elements(app_name, **kwargs)
    if not matches:
        raise RuntimeError(f"AT-SPI could not find element matching '{element.label}'")
    target = matches[0]
    if target.x is None or target.y is None:
        return None, None
    return (
        target.x + (target.width or 0) / 2.0,
        target.y + (target.height or 0) / 2.0,
    )


def _atspi_execute(
    app_name: str, element: Any, *, text: str | None = None
) -> tuple[float | None, float | None]:
    from app_automate.accessibility import linux_atspi

    action = element.action.value

    if action == "click":
        target = linux_atspi.click_matching_element(app_name, contains=element.label)
    elif action == "type":
        type_text = text or element.text
        if type_text is None:
            raise RuntimeError(
                f"type action requires --text for element '{element.label}'"
            )
        target = linux_atspi.type_into_matching_element(
            app_name,
            contains=element.label,
            text=type_text,
        )
    else:
        return _atspi_locate(app_name, element)

    if target.x is None or target.y is None:
        return None, None
    return (
        target.x + (target.width or 0) / 2.0,
        target.y + (target.height or 0) / 2.0,
    )
