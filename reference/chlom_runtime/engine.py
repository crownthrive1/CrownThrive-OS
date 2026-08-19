from __future__ import annotations

import hashlib
from typing import Any

from .dail import DAILLedger
from .docs_impact import normalize_docs_impact
from .model import (
    Decision,
    KernelContractError,
    KERNEL_CONTRACT_VERSION,
    KERNEL_DECISION_CONTRACT_ID,
    KERNEL_PROTOTYPE_STATE,
    canonical_json,
    parse_kernel_request,
)
from .policy import PolicyEngine


class CHLOMReferenceEngine:
    """Executable CHLOM semantic kernel for Phase 2.99 prototype validation.

    The engine decides/records; it does not execute provider mutations.
    """

    def __init__(self, rules: list[dict[str, Any]], ledger: DAILLedger | None = None):
        self.policy = PolicyEngine(rules)
        self.ledger = ledger or DAILLedger()
        self._idempotency_cache: dict[str, tuple[str, Decision]] = {}

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
            raise ValueError(
                "request_id, action, actor identity/org, resource identity/type and risk_class are required"
            )

    @staticmethod
    def _is_v1_contract(request: dict[str, Any]) -> bool:
        return "contract_id" in request or "contract_version" in request

    @staticmethod
    def _fingerprint(request: dict[str, Any]) -> str:
        return hashlib.sha256(canonical_json(request).encode("utf-8")).hexdigest()

    def evaluate(self, request: dict[str, Any]) -> Decision:
        strict_v1 = self._is_v1_contract(request)
        metadata = parse_kernel_request(request) if strict_v1 else None
        if not strict_v1:
            self._require_request(request)

        actor = request["actor"]
        resource = request["resource"]
        context = request["context"]
        action = str(request["action"])
        risk_class = str(context["risk_class"])

        request_contract_id = (
            metadata.contract_id if metadata else "ct.contract.chlom.kernel.request.legacy-v0"
        )
        request_id = metadata.request_id if metadata else str(request["request_id"])
        correlation_id = metadata.correlation_id if metadata else request_id
        idempotency_key = metadata.idempotency_key if metadata else request_id
        authority_evidence = metadata.authority_evidence if metadata else tuple(
            str(item) for item in request.get("authority_evidence", [])
        )
        observed_resource_version = metadata.observed_resource_version if metadata else None
        expected_resource_version = metadata.expected_resource_version if metadata else None

        fingerprint = self._fingerprint(request)
        if strict_v1 and idempotency_key in self._idempotency_cache:
            prior_fingerprint, prior_decision = self._idempotency_cache[idempotency_key]
            if prior_fingerprint != fingerprint:
                raise KernelContractError("idempotency_key_reused_with_different_payload")
            return prior_decision

        effect = "deny"
        matched: tuple[str, ...] = tuple()
        reasons: tuple[str, ...] = tuple()
        approvals: tuple[str, ...] = tuple()

        if actor.get("authenticated") is not True:
            reasons = ("actor_not_authenticated",)
        elif resource.get("organization_id") and resource.get("organization_id") != actor.get("organization_id"):
            reasons = ("cross_organization_access_not_authorized",)
        elif strict_v1 and metadata.execution_mode != "decision_only":
            reasons = ("reference_kernel_provider_mutation_prohibited",)
        elif strict_v1 and observed_resource_version != expected_resource_version:
            effect = "hold"
            reasons = ("resource_version_conflict",)
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
                "prototype_state": KERNEL_PROTOTYPE_STATE,
                "decision_contract_id": KERNEL_DECISION_CONTRACT_ID,
                "decision_contract_version": KERNEL_CONTRACT_VERSION,
                "request_contract_id": request_contract_id,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "idempotency_key": idempotency_key,
                "action": action,
                "actor_id": actor["actor_id"],
                "organization_id": actor["organization_id"],
                "resource_id": resource["resource_id"],
                "resource_type": resource["resource_type"],
                "observed_resource_version": observed_resource_version,
                "expected_resource_version": expected_resource_version,
                "authority_evidence": list(authority_evidence),
                "effect": effect,
                "matched_rule_ids": list(matched),
                "reasons": list(reasons),
                "required_approvals": list(approvals),
                "risk_class": risk_class,
                "docs_impact": docs_impact,
            },
        )
        decision_id = f"ct.decision.ref.{event['sequence']:08d}"
        decision = Decision(
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
            contract_id=KERNEL_DECISION_CONTRACT_ID,
            contract_version=KERNEL_CONTRACT_VERSION,
            request_contract_id=request_contract_id,
            request_id=request_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            actor_id=str(actor["actor_id"]),
            organization_id=str(actor["organization_id"]),
            resource_type=str(resource["resource_type"]),
            observed_resource_version=observed_resource_version,
            expected_resource_version=expected_resource_version,
            authority_evidence=authority_evidence,
        )
        if strict_v1:
            self._idempotency_cache[idempotency_key] = (fingerprint, decision)
        return decision
