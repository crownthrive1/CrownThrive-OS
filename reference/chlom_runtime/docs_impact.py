from __future__ import annotations

from typing import Any

_ALLOWED = {"docs_updated", "docs_no_change", "docs_delta_opened"}


def normalize_docs_impact(value: dict[str, Any] | None) -> dict[str, Any]:
    value = dict(value or {})
    outcome = value.get("outcome", "docs_delta_opened")
    if outcome not in _ALLOWED:
        raise ValueError(f"Unsupported documentation-impact outcome: {outcome}")
    reason = str(value.get("reason", "reference_runtime_requires_explicit_docs_reconciliation"))
    return {
        "outcome": outcome,
        "reason": reason,
        "affected_article_ids": list(value.get("affected_article_ids", [])),
        "affected_changelog_ids": list(value.get("affected_changelog_ids", [])),
    }
