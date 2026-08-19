from __future__ import annotations

from typing import Any

from .dail import DAILLedger
from .docs_impact import normalize_docs_impact
from .model import Decision
from .policy import PolicyEngine


class CHLOMReferenceEngine:
    """Executable CHLOM semantic kernel for Phase 2.99 prototype validation.

    The engine decides/records; it does not execute provider mutations.
    """

    def __init__(self, rules: list[dict[str, Any]], ledger: DAILLedger | None = None):
        self.policy = PolicyEngine(rules)
        self.ledger = ledger or DAILLedger()

    @staticmethod
    def _require_request(request: dict[str, Any]) -> None:
        required = [
            request.get("request_id"),
            request.get("action"),
            request.get("actor", {}).get("actor_id"),
            request.get("actor", {}).get("organization_id"),
            request.get("resource", {}).get("resource_id"),
            request.get("resource", {}).get("resource_type"),
            request.get("context", {}).get("risk_class"),
        ]
        if not all(required):
            raise ValueError("request_id, action, actor identity/org, resource identity/type and risk_class are required")

    def evaluate(self, request: dict[str, Any]) -> Decision:
        self._require_request(request)
        actor = request["actor"]
        resource = request["resource"]
        context = request["context"]
        action = str(request["action"])
        risk_class = str(context["risk_class"])

        effect = "deny"
        matched: tuple[str, ...] = tuple()
        reasons: tuple[str, ...] = tuple()
        approvals: tuple[str, ...] = tuple()

        if actor.get("authenticated") is not True:
            reasons = ("actor_not_authenticated",)
        elif resource.get("organization_id") and resource.get("organization_id") != actor.get("organization_id"):
            reasons = ("cross_organization_access_not_authorized",)
        elif resource.get("hold_state") in {"active", "security_hold", "legal_hold", "rights_hold"}:
            effect = "hold"
            reasons = ("resource_hold_active",)
        else:
            result = self.policy.evaluate(request)
            effect = result.effect
            matched = result.matched_rule_ids
            reasons = result.reasons
            approvals = result.required_approvals

        provided_approvals = set(request.get("approval_evidence", []))
        missing_approvals = [item for item in approvals if item not in provided_approvals]
        if effect == "allow" and (risk_class == "D3" or missing_approvals):
            effect = "hold"
            extra = []
            if risk_class == "D3":
                extra.append("d3_reserved_authority_required")
            if missing_approvals:
                extra.append("missing_required_approvals:" + ",".join(missing_approvals))
            reasons = tuple(list(reasons) + extra)

        docs_impact = normalize_docs_impact(request.get("docs_impact"))
        event = self.ledger.append(
            "ct.chlom.reference.decision.v1",
            {
                "request_id": request["request_id"],
                "action": action,
                "actor_id": actor["actor_id"],
                "organization_id": actor["organization_id"],
                "resource_id": resource["resource_id"],
                "resource_type": resource["resource_type"],
                "effect": effect,
                "matched_rule_ids": list(matched),
                "reasons": list(reasons),
                "required_approvals": list(approvals),
                "risk_class": risk_class,
                "docs_impact": docs_impact,
            },
        )
        decision_id = f"ct.decision.ref.{event['sequence']:08d}"
        return Decision(
            decision_id=decision_id,
            effect=effect,
            action=action,
            resource_id=str(resource["resource_id"]),
            matched_rule_ids=matched,
            reasons=reasons,
            required_approvals=approvals,
            risk_class=risk_class,
            docs_impact=docs_impact,
            event_id=str(event["event_id"]),
        )
