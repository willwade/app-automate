from __future__ import annotations

from dataclasses import dataclass

from app_automate.accessibility.models import UIElement
from app_automate.accessibility.synonyms import (
    expand_synonyms,
    role_matches,
)


@dataclass(slots=True)
class SearchResult:
    element: UIElement
    score: float
    match_type: str
    matched_text: str

    def as_dict(self) -> dict:
        return {
            "label": self.element.label,
            "role": self.element.role or self.element.class_name,
            "score": round(self.score, 3),
            "match_type": self.match_type,
            "matched_text": self.matched_text,
            "x": self.element.x,
            "y": self.element.y,
            "width": self.element.width,
            "height": self.element.height,
            "actionable": self.element.actionable,
            "path": self.element.path,
        }


def search_elements(
    elements: list[UIElement],
    query: str,
    *,
    role_filter: str | None = None,
    actionable_only: bool = False,
    enabled_only: bool = True,
    max_results: int = 20,
) -> list[SearchResult]:
    if role_filter:
        elements = [
            e for e in elements if role_matches(e.role, role_filter)
        ]
    if actionable_only:
        elements = [e for e in elements if e.actionable]
    if enabled_only:
        elements = [e for e in elements if e.enabled is None or e.enabled]

    expanded = expand_synonyms(query)
    query_lower = query.lower()
    query_tokens = query_lower.split()

    results: list[SearchResult] = []
    for el in elements:
        best = _score_element(el, query_lower, query_tokens, expanded)
        if best is not None:
            results.append(best)

    results.sort(
        key=lambda r: (
            -r.score,
            r.element.depth,
            r.element.x or 0,
            r.element.y or 0,
        )
    )
    return results[:max_results]


def _score_element(
    el: UIElement,
    query_lower: str,
    query_tokens: list[str],
    expanded: list[str],
) -> SearchResult | None:
    label = (el.label or "").lower()
    role = (el.role or "").lower()
    description = (el.description or "").lower()
    class_name = (el.class_name or "").lower()

    best_score = 0.0
    best_type = ""
    best_text = ""

    if label == query_lower:
        return SearchResult(el, 100.0, "exact-label", label)

    if query_lower in label:
        s = 80.0 + (len(query_lower) / max(len(label), 1)) * 15.0
        if s > best_score:
            best_score = s
            best_type = "substring-label"
            best_text = label

    for token in query_tokens:
        if token in label:
            s = 60.0 + (len(token) / max(len(label), 1)) * 10.0
            if s > best_score:
                best_score = s
                best_type = "token-label"
                best_text = label

    if query_lower in role:
        s = 55.0
        if s > best_score:
            best_score = s
            best_type = "substring-role"
            best_text = role

    if query_lower in description:
        s = 50.0 + (len(query_lower) / max(len(description), 1)) * 10.0
        if s > best_score:
            best_score = s
            best_type = "substring-description"
            best_text = description

    if query_lower in class_name:
        s = 40.0
        if s > best_score:
            best_score = s
            best_type = "substring-class"
            best_text = class_name

    for syn in expanded:
        if syn == query_lower:
            continue
        syn_lower = syn.lower()
        if syn_lower in label:
            s = 30.0 + (len(syn_lower) / max(len(label), 1)) * 10.0
            if s > best_score:
                best_score = s
                best_type = "synonym-label"
                best_text = f"{label} (syn: {syn})"
        elif syn_lower in role:
            s = 25.0
            if s > best_score:
                best_score = s
                best_type = "synonym-role"
                best_text = f"{role} (syn: {syn})"
        elif syn_lower in description:
            s = 20.0
            if s > best_score:
                best_score = s
                best_type = "synonym-description"
                best_text = f"{description} (syn: {syn})"

    if el.actionable and best_score > 0:
        best_score += 5.0

    if best_score == 0.0:
        return None

    return SearchResult(el, best_score, best_type, best_text)
