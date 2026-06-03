from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from app_automate.config.models import AppProfile, SemanticElement
from app_automate.consumer.types import ExecuteResult


class InputAdapter(Protocol):
    def hotkey(self, *keys: str) -> None: ...

    def write_text(self, text: str, *, interval: float = 0.0) -> None: ...


class Consumer:
    def __init__(
        self,
        profile: AppProfile,
        *,
        adapter: InputAdapter | None = None,
    ) -> None:
        self._profile = profile
        self._adapter = adapter

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        adapter: InputAdapter | None = None,
    ) -> Consumer:
        p = Path(path)
        if p.is_dir():
            p = p / "profile.json"
        data = json.loads(p.read_text())
        return cls(AppProfile.model_validate(data), adapter=adapter)

    @classmethod
    def from_dict(cls, data: dict, *, adapter: InputAdapter | None = None) -> Consumer:
        return cls(AppProfile.model_validate(data), adapter=adapter)

    @property
    def profile(self) -> AppProfile:
        return self._profile

    @property
    def app_name(self) -> str:
        return self._profile.app_name

    @property
    def profile_id(self) -> str:
        return self._profile.profile_id

    def resolve(self, command: str) -> SemanticElement:
        element_id = self._resolve_id(command)
        return self._profile.semantic_elements[element_id]

    def resolve_id(self, command: str) -> str:
        return self._resolve_id(command)

    def list_commands(self) -> list[str]:
        commands: list[str] = []
        for element_id, element in self._profile.semantic_elements.items():
            commands.append(element.label)
            commands.extend(element.aliases)
            commands.append(element_id)
        return commands

    def list_elements(self) -> dict[str, SemanticElement]:
        return dict(self._profile.semantic_elements)

    def list_shortcuts(self) -> dict[str, str]:
        return {name: sdef.keys for name, sdef in self._profile.shortcuts.items()}

    def execute(
        self, command: str, *, text: str | None = None, dry_run: bool = False
    ) -> ExecuteResult:
        element_id = self._resolve_id(command)
        element = self._profile.semantic_elements[element_id]

        if dry_run:
            return ExecuteResult(
                element_id=element_id,
                label=element.label,
                action=element.action.value,
            )

        if element.action.value == "shortcut" and element.shortcut:
            self.send_shortcut(element.shortcut.keys)
            return ExecuteResult(
                element_id=element_id,
                label=element.label,
                action="shortcut",
            )

        if element.action.value == "hotkey" and element.hotkey:
            self.send_shortcut(element.hotkey)
            return ExecuteResult(
                element_id=element_id,
                label=element.label,
                action="hotkey",
            )

        if element.action.value == "type":
            type_text = text or element.text
            if type_text is None:
                raise ValueError(
                    f"type action requires text for element '{element.label}'"
                )
            self.type_text(type_text)
            return ExecuteResult(
                element_id=element_id,
                label=element.label,
                action="type",
            )

        if element.action.value == "wait":
            import time

            time.sleep((element.wait_ms or 500) / 1000.0)
            return ExecuteResult(
                element_id=element_id,
                label=element.label,
                action="wait",
            )

        raise NotImplementedError(
            f"action '{element.action.value}' requires a platform-specific backend. "
            f"Use shortcut-based elements for cross-platform consumer usage."
        )

    def _get_adapter(self) -> Any:
        if self._adapter is not None:
            return self._adapter
        from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter

        return PyAutoGuiAdapter()

    def send_shortcut(self, keys: str) -> None:
        adapter = self._get_adapter()
        parts = keys.split("+")
        adapter.hotkey(*parts)

    def type_text(self, text: str) -> None:
        adapter = self._get_adapter()
        adapter.write_text(text)

    def send_key(self, key: str) -> None:
        adapter = self._get_adapter()
        adapter.hotkey(key)

    def _resolve_id(self, command: str) -> str:
        normalized = command.strip().casefold()
        for element_id, element in self._profile.semantic_elements.items():
            candidates = [element.label, *element.aliases, element_id]
            if any(normalized == c.casefold() for c in candidates):
                return element_id
        available = self.list_commands()
        raise KeyError(
            f"no element matches command: '{command}'. "
            f"Available: {', '.join(sorted(set(available)))}"
        )
