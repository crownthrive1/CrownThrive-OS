from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from typing import Any

KERNEL_REQUEST_CONTRACT_ID = "ct.contract.chlom.kernel.request.v1"
KERNEL_DECISION_CONTRACT_ID = "ct.contract.chlom.kernel.decision.v1"
KERNEL_CONTRACT_VERSION = "1.0.0"
KERNEL_PROTOTYPE_STATE = "phase_2_99_semantic_oracle"
_ALLOWED_RISK_CLASSES = {"D0", "D1", "D2", "D3"}
_GOVERNED_EVIDENCE_REF = re.compile(r"^ct\.(?:evidence|proof)\.ref\.[A-Za-z0-9._:-]+$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class KernelContractError(ValueError):
    pass


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise KernelContractError(f"{field} must be an object")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KernelContractError(f"{field} is required")
    return value


def _require_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise KernelContractError(f"{field} must be a non-negative integer")
    return value


def _require_string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise KernelContractError(f"{field} must be an array")
    return tuple(_require_string(item, f"{field}[]") for item in value)


def sanitize_evidence_references(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Persist governed references or opaque digests, never caller-provided free text."""

    sanitized: list[str] = []
    for item in values:
        value = _require_string(item, "authority_evidence[]")
        if _GOVERNED_EVIDENCE_REF.fullmatch(value):
            sanitized.append(value)
        else:
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            sanitized.append(f"ct.evidence.digest.sha256.{digest}")
    return tuple(sanitized)


@dataclass(frozen=True)
class VerifiedAuthorityContext:
    """Out-of-band authority resolved by a trusted authority/relationship adapter.

    Caller request fields are claims/evidence only. The semantic oracle consumes
    this context separately so untrusted payloads cannot self-create roles,
    relationships, delegations or approvals.
    """

    actor_id: str
    organization_id: str
    roles: tuple[str, ...]
    relationships: tuple[str, ...]
    delegations: tuple[str, ...]
    approvals: tuple[str, ...]
    evidence_refs: tuple[str, ...] = tuple()

    def sanitized_evidence_refs(self) -> tuple[str, ...]:
        return sanitize_evidence_references(self.evidence_refs)


@dataclass(frozen=True)
class KernelRequestMetadata:
    contract_id: str
    contract_version: str
    request_id: str
    correlation_id: str
    idempotency_key: str
    actor_id: str
    organization_id: str
    resource_id: str
    resource_type: str
    resource_organization_id: str
    risk_class: str
    environment: str
    purpose: str
    execution_mode: str
    observed_resource_version: int
    expected_resource_version: int
    authority_evidence: tuple[str, ...]
    approval_evidence: tuple[str, ...]


def parse_kernel_request(request: dict[str, Any]) -> KernelRequestMetadata:
    request = _require_mapping(request, "request")
    contract_id = _require_string(request.get("contract_id"), "contract_id")
    if contract_id != KERNEL_REQUEST_CONTRACT_ID:
        raise KernelContractError(f"unsupported contract_id: {contract_id}")
    contract_version = _require_string(request.get("contract_version"), "contract_version")
    if contract_version != KERNEL_CONTRACT_VERSION:
        raise KernelContractError(f"unsupported contract_version: {contract_version}")
    actor = _require_mapping(request.get("actor"), "actor")
    resource = _require_mapping(request.get("resource"), "resource")
    context = _require_mapping(request.get("context"), "context")
    _require_mapping(request.get("docs_impact"), "docs_impact")
    if "authenticated" not in actor or not isinstance(actor["authenticated"], bool):
        raise KernelContractError("actor.authenticated must be a boolean")
    risk_class = _require_string(context.get("risk_class"), "context.risk_class")
    if risk_class not in _ALLOWED_RISK_CLASSES:
        raise KernelContractError(f"unsupported context.risk_class: {risk_class}")
    return KernelRequestMetadata(
        contract_id=contract_id,
        contract_version=contract_version,
        request_id=_require_string(request.get("request_id"), "request_id"),
        correlation_id=_require_string(request.get("correlation_id"), "correlation_id"),
        idempotency_key=_require_string(request.get("idempotency_key"), "idempotency_key"),
        actor_id=_require_string(actor.get("actor_id"), "actor.actor_id"),
        organization_id=_require_string(actor.get("organization_id"), "actor.organization_id"),
        resource_id=_require_string(resource.get("resource_id"), "resource.resource_id"),
        resource_type=_require_string(resource.get("resource_type"), "resource.resource_type"),
        resource_organization_id=_require_string(resource.get("organization_id"), "resource.organization_id"),
        risk_class=risk_class,
        environment=_require_string(context.get("environment"), "context.environment"),
        purpose=_require_string(context.get("purpose"), "context.purpose"),
        execution_mode=_require_string(context.get("execution_mode"), "context.execution_mode"),
        observed_resource_version=_require_nonnegative_int(resource.get("version"), "resource.version"),
        expected_resource_version=_require_nonnegative_int(
            context.get("expected_resource_version"), "context.expected_resource_version"
        ),
        authority_evidence=_require_string_list(request.get("authority_evidence"), "authority_evidence"),
        approval_evidence=_require_string_list(request.get("approval_evidence"), "approval_evidence"),
    )


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
    contract_id: str
    contract_version: str
    request_contract_id: str
    request_id: str
    correlation_id: str
    idempotency_key: str
    actor_id: str
    organization_id: str
    resource_type: str
    observed_resource_version: int | None
    expected_resource_version: int | None
    authority_evidence: tuple[str, ...]
    authority_context_verified: bool
    relationship_refs: tuple[str, ...]
    delegation_refs: tuple[str, ...]
    verified_approvals: tuple[str, ...]
    prototype_state: str = KERNEL_PROTOTYPE_STATE

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["matched_rule_ids"] = list(self.matched_rule_ids)
        value["reasons"] = list(self.reasons)
        value["required_approvals"] = list(self.required_approvals)
        value["authority_evidence"] = list(self.authority_evidence)
        value["relationship_refs"] = list(self.relationship_refs)
        value["delegation_refs"] = list(self.delegation_refs)
        value["verified_approvals"] = list(self.verified_approvals)
        return value
