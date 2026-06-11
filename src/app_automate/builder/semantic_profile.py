from __future__ import annotations

import re
from pathlib import Path

from app_automate.accessibility.models import UIElement
from app_automate.config.models import ActionType, AppProfile, SemanticElement
from app_automate.config.validation import save_profile

UIA_TYPEABLE_ROLES = {
    "Edit",
    "Text",
    "TextEdit",
    "RichEdit",
    "EditControl",
    "TextControl",
}

CDP_TYPEABLE_ROLES = {"textbox", "combobox", "searchbox"}

ATSPI_TYPEABLE_ROLES = {
    "entry",
    "text",
    "terminal",
    "spin button",
    "combo box",
}


def build_semantic_profile(
    *,
    app_name: str,
    backend: str,
    output_dir: Path,
    port: int = 9222,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    if backend == "uia":
        elements = _collect_uia_elements(app_name)
    elif backend == "cdp":
        elements = _collect_cdp_elements(port)
    elif backend == "atspi":
        elements = _collect_atspi_elements(app_name)
    else:
        raise ValueError(f"unknown backend: {backend}")

    semantic_elements: dict[str, SemanticElement] = {}
    for el in elements:
        eid = _slugify(el.label)
        if eid in semantic_elements:
            eid = f"{eid}_{el.path}"
        se = SemanticElement(
            label=el.label,
            role=el.class_name,
            automation_id=el.automation_id,
            selector=_build_cdp_selector(el) if backend == "cdp" else None,
            action=_infer_action(el),
        )
        semantic_elements[eid] = se

    profile = AppProfile(
        profile_id=_slugify(app_name),
        app_name=app_name,
        type="semantic",
        backend=backend,
        semantic_elements=semantic_elements,
    )

    path = output_dir / "profile.json"
    save_profile(profile, path)
    return path


def _collect_uia_elements(app_name: str) -> list[UIElement]:
    from app_automate.accessibility import windows_uia

    return windows_uia.list_app_ui_elements(
        app_name, max_depth=15, actionable_only=True
    )


def _collect_cdp_elements(port: int) -> list[UIElement]:
    from app_automate.accessibility import cdp

    return cdp.list_cdp_elements(port, actionable_only=True)


def _collect_atspi_elements(app_name: str) -> list[UIElement]:
    from app_automate.accessibility import linux_atspi

    return linux_atspi.list_app_ui_elements(
        app_name, max_depth=15, actionable_only=True
    )


def _slugify(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    if not slug:
        return "element"
    return slug


def _infer_action(el: UIElement) -> ActionType:
    role = (el.role or el.class_name or "").lower()
    class_name = el.class_name or ""

    if (
        class_name in UIA_TYPEABLE_ROLES
        or role in CDP_TYPEABLE_ROLES
        or role in ATSPI_TYPEABLE_ROLES
    ):
        return ActionType.TYPE
    return ActionType.CLICK


def _build_cdp_selector(el: UIElement) -> str | None:
    subrole = getattr(el, "subrole", None) or ""
    if subrole == "input":
        aria = el.name or el.label
        if aria:
            return f'[aria-label="{aria}"]'
    elif subrole == "textarea":
        aria = el.name or el.label
        if aria:
            return f'textarea[aria-label="{aria}"]'
    role = el.role or el.class_name
    name = el.name or el.label
    if role and name:
        return f'[role="{role}"] >> text={name}'
    return None
