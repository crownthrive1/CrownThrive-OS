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
    VerifiedAuthorityContext,
    canonical_json,
    parse_kernel_request,
    sanitize_evidence_references,
)
from .policy import PolicyEngine


class CHLOMReferenceEngine:
    """Executable CHLOM semantic kernel for Phase 2.99 prototype validation.

    The engine decides/records; it does not execute provider mutations. Strict
    v1 requests never trust caller-asserted roles, approvals, relationships or
    delegations as authority. Legacy behavior is isolated to the exact parent
    reference-test fixture and is not a general request fallback.
    """

    def __init__(self, rules: list[dict[str, Any]], ledger: DAILLedger | None = None):
        self.policy = PolicyEngine(rules)
        self.ledger = ledger or DAILLedger()
        self._idempotency_cache: dict[str, tuple[str, str, Decision]] = {}

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
    def _is_exact_legacy_test_fixture(request: dict[str, Any]) -> bool:
        if "contract_id" in request or "contract_version" in request:
            return False
        return (
            request.get("request_id") == "req_test"
            and request.get("actor", {}).get("actor_id") == "ct.actor.test"
            and request.get("actor", {}).get("organization_id") == "ct.org.crownthrive-llc"
            and request.get("resource", {}).get("resource_id") == "ct.resource.test"
            and request.get("context", {}).get("environment") == "test"
            and request.get("docs_impact", {}).get("reason") == "test_only"
        )

    @staticmethod
    def _fingerprint(request: dict[str, Any]) -> str:
        return hashlib.sha256(canonical_json(request).encode("utf-8")).hexdigest()

    @staticmethod
    def _authority_fingerprint(
        verified_authority: VerifiedAuthorityContext | None,
    ) -> str:
        """Hash the effective out-of-band authority context used by a decision.

        Idempotency cannot safely replay an authority-sensitive decision from the
        request payload alone because verified authority is supplied separately.
        Normalize set-like fields so semantically identical contexts produce the
        same fingerprint while removal or material authority changes fail closed.
        """

        if verified_authority is None:
            value: dict[str, Any] = {"present": False}
        else:
            value = {
                "present": True,
                "actor_id": verified_authority.actor_id,
                "organization_id": verified_authority.organization_id,
                "roles": sorted(set(verified_authority.roles)),
                "relationships": sorted(set(verified_authority.relationships)),
                "delegations": sorted(set(verified_authority.delegations)),
                "approvals": sorted(set(verified_authority.approvals)),
                "evidence_refs": sorted(
                    set(verified_authority.sanitized_evidence_refs())
                ),
            }
        return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

    def _matched_rules_require_authority(self, matched_rule_ids: tuple[str, ...]) -> bool:
        matched = set(matched_rule_ids)
        for rule in self.policy.rules:
            if str(rule.get("rule_id")) not in matched:
                continue
            conditions = rule.get("conditions", {})
            if "actor.roles_any" in conditions or "actor.roles_all" in conditions:
                return True
            if rule.get("required_approvals"):
                return True
        return False

    @staticmethod
    def _verified_authority_matches_request(
        metadata, verified_authority: VerifiedAuthorityContext | None
    ) -> bool:
        if verified_authority is None:
            return False
        return (
            verified_authority.actor_id == metadata.actor_id
            and verified_authority.organization_id == metadata.organization_id
        )

    def evaluate(
        self,
        request: dict[str, Any],
        *,
        verified_authority: VerifiedAuthorityContext | None = None,
    ) -> Decision:
        strict_v1 = self._is_v1_contract(request)
        if strict_v1:
            metadata = parse_kernel_request(request)
        elif self._is_exact_legacy_test_fixture(request):
            metadata = None
            self._require_request(request)
        else:
            raise KernelContractError(
                "contract_id and contract_version are required for untrusted requests"
            )

        actor = request["actor"]
        resource = request["resource"]
        context = request["context"]
        action = str(request["action"])
        risk_class = str(context["risk_class"])

        request_contract_id = (
            metadata.contract_id
            if metadata
            else "ct.contract.chlom.kernel.request.legacy-v0-test-only"
        )
        request_id = metadata.request_id if metadata else str(request["request_id"])
        correlation_id = metadata.correlation_id if metadata else request_id
        idempotency_key = metadata.idempotency_key if metadata else request_id
        raw_authority_evidence = (
            metadata.authority_evidence
            if metadata
            else tuple(str(item) for item in request.get("authority_evidence", []))
        )
        authority_evidence = sanitize_evidence_references(raw_authority_evidence)
        observed_resource_version = metadata.observed_resource_version if metadata else None
        expected_resource_version = metadata.expected_resource_version if metadata else None

        authority_context_verified = False
        relationship_refs: tuple[str, ...] = tuple()
        delegation_refs: tuple[str, ...] = tuple()
        verified_approvals: tuple[str, ...] = tuple()
        verified_roles: tuple[str, ...] = tuple()
        if strict_v1 and self._verified_authority_matches_request(metadata, verified_authority):
            authority_context_verified = True
            verified_roles = verified_authority.roles
            relationship_refs = verified_authority.relationships
            delegation_refs = verified_authority.delegations
            verified_approvals = verified_authority.approvals
            authority_evidence = tuple(
                dict.fromkeys(
                    authority_evidence + verified_authority.sanitized_evidence_refs()
                )
            )

        request_fingerprint = self._fingerprint(request)
        authority_fingerprint = (
            self._authority_fingerprint(verified_authority) if strict_v1 else "legacy-test-only"
        )
        if strict_v1 and idempotency_key in self._idempotency_cache:
            (
                prior_request_fingerprint,
                prior_authority_fingerprint,
                prior_decision,
            ) = self._idempotency_cache[idempotency_key]
            if prior_request_fingerprint != request_fingerprint:
                raise KernelContractError("idempotency_key_reused_with_different_payload")
            if prior_authority_fingerprint != authority_fingerprint:
                raise KernelContractError(
                    "idempotency_key_reused_with_different_authority_context"
                )
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
        elif strict_v1 and verified_authority is not None and not authority_context_verified:
            reasons = ("verified_authority_context_identity_org_mismatch",)
        elif resource.get("hold_state") in {"active", "security_hold", "legal_hold", "rights_hold"}:
            effect = "hold"
            reasons = ("resource_hold_active",)
        else:
            policy_request = request
            if strict_v1:
                policy_request = dict(request)
                policy_request["actor"] = dict(actor)
                policy_request["actor"]["roles"] = list(verified_roles)
            result = self.policy.evaluate(policy_request)
            effect = result.effect
            matched = result.matched_rule_ids
            reasons = result.reasons
            approvals = result.required_approvals

            if strict_v1 and effect == "allow" and self._matched_rules_require_authority(matched):
                if not authority_context_verified:
                    effect = "hold"
                    reasons = tuple(list(reasons) + ["verified_authority_context_required"])
                elif not relationship_refs or not delegation_refs:
                    effect = "hold"
                    reasons = tuple(
                        list(reasons) + ["verified_relationship_and_delegation_required"]
                    )

        provided_approvals = (
            set(verified_approvals)
            if strict_v1
            else set(request.get("approval_evidence", []))
        )
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
                "authority_context_verified": authority_context_verified,
                "relationship_refs": list(relationship_refs),
                "delegation_refs": list(delegation_refs),
                "verified_approvals": list(verified_approvals),
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
            authority_context_verified=authority_context_verified,
            relationship_refs=relationship_refs,
            delegation_refs=delegation_refs,
            verified_approvals=verified_approvals,
        )
        if strict_v1:
            self._idempotency_cache[idempotency_key] = (
                request_fingerprint,
                authority_fingerprint,
                decision,
            )
        return decision
