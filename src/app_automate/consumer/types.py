from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecuteResult:
    element_id: str
    label: str
    action: str
    x: float | None = None
    y: float | None = None
