from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class Decision:
    decision_id: str
    effect: str
    action: str
    resource_id: str
    matched_rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    required_approvals: tuple[str, ...]
    risk_class: str
    docs_impact: dict[str, Any]
    event_id: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["matched_rule_ids"] = list(self.matched_rule_ids)
        value["reasons"] = list(self.reasons)
        value["required_approvals"] = list(self.required_approvals)
        return value
