from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PolicyConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyResult:
    effect: str
    matched_rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    required_approvals: tuple[str, ...]


_EFFECT_RANK = {"allow": 1, "hold": 2, "deny": 3}
_SUPPORTED_CONDITIONS = {
    "actor.roles_any",
    "actor.roles_all",
    "resource.classification_in",
    "resource.status_in",
    "context.environment_in",
    "context.purpose_in",
    "context.risk_class_in",
}


def _dig(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


class PolicyEngine:
    """Small fail-closed evaluator proving CHLOM policy semantics.

    This is intentionally not a replacement for OPA/Cedar. It is the CrownThrive
    semantic reference used to test external policy backends later.
    """

    def __init__(self, rules: list[dict[str, Any]]):
        self.rules = sorted(rules, key=lambda r: int(r.get("priority", 0)), reverse=True)
        self._validate()

    def _validate(self) -> None:
        seen: set[str] = set()
        for rule in self.rules:
            rule_id = str(rule.get("rule_id", ""))
            if not rule_id or rule_id in seen:
                raise PolicyConfigurationError("Policy rule IDs must be non-empty and unique")
            seen.add(rule_id)
            if rule.get("effect") not in _EFFECT_RANK:
                raise PolicyConfigurationError(f"Unsupported effect in {rule_id}")
            conditions = rule.get("conditions", {})
            if not isinstance(conditions, dict):
                raise PolicyConfigurationError(f"conditions must be an object in {rule_id}")
            unknown = set(conditions) - _SUPPORTED_CONDITIONS
            if unknown:
                raise PolicyConfigurationError(f"Unknown fail-closed condition(s) in {rule_id}: {sorted(unknown)}")

    @staticmethod
    def _condition_matches(key: str, expected: Any, request: dict[str, Any]) -> bool:
        if key == "actor.roles_any":
            actual = set(_dig(request, "actor.roles", []) or [])
            return bool(actual.intersection(set(expected)))
        if key == "actor.roles_all":
            actual = set(_dig(request, "actor.roles", []) or [])
            return set(expected).issubset(actual)
        mapping = {
            "resource.classification_in": "resource.classification",
            "resource.status_in": "resource.status",
            "context.environment_in": "context.environment",
            "context.purpose_in": "context.purpose",
            "context.risk_class_in": "context.risk_class",
        }
        actual = _dig(request, mapping[key])
        return actual in set(expected)

    def _matches(self, rule: dict[str, Any], request: dict[str, Any]) -> bool:
        action = request.get("action")
        resource_type = _dig(request, "resource.resource_type")
        actions = rule.get("actions", ["*"])
        resource_types = rule.get("resource_types", ["*"])
        if "*" not in actions and action not in actions:
            return False
        if "*" not in resource_types and resource_type not in resource_types:
            return False
        return all(self._condition_matches(key, value, request) for key, value in rule.get("conditions", {}).items())

    def evaluate(self, request: dict[str, Any]) -> PolicyResult:
        matches = [rule for rule in self.rules if self._matches(rule, request)]
        if not matches:
            return PolicyResult("deny", tuple(), ("default_deny_no_matching_rule",), tuple())
        winning_rank = max(_EFFECT_RANK[str(rule["effect"])] for rule in matches)
        winners = [rule for rule in matches if _EFFECT_RANK[str(rule["effect"])] == winning_rank]
        effect = str(winners[0]["effect"])
        matched = tuple(str(rule["rule_id"]) for rule in matches)
        reasons = tuple(str(rule.get("reason", rule["rule_id"])) for rule in winners)
        approvals: list[str] = []
        for rule in winners:
            for approval in rule.get("required_approvals", []):
                if approval not in approvals:
                    approvals.append(str(approval))
        return PolicyResult(effect, matched, reasons, tuple(approvals))
