#!/usr/bin/env python3
"""Deterministic mock conformance for the Phase 2.99 CHLOM adapter envelope.

This module performs no network request, provider mutation, credential access,
or production action. It validates the machine contract and executes mock
fixtures to prove fail-closed adapter semantics before any provider is adopted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "contracts/chlom/api/adapter-envelope.v1.json"
FIXTURE_PATH = ROOT / "contracts/chlom/api/adapter-conformance-fixture.v1.json"

SECRET_KEY_FRAGMENTS = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "private_key",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object at {path}")
    return value


def contains_forbidden_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS):
                return True
            if contains_forbidden_secret_key(child):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_secret_key(item) for item in value)
    return False


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("contract_id") != "ct.contract.chlom.adapter-envelope.v1":
        raise ValueError("Adapter contract ID drifted")
    if contract.get("contract_version") != "1.0.0":
        raise ValueError("Adapter contract version drifted")
    if contract.get("phase") != "2.99":
        raise ValueError("Adapter contract must remain Phase 2.99 prototype")

    authority = contract.get("authority", {})
    if authority.get("roadmap") != "CT-ADR-ROADMAP-010/ten_phase_v1":
        raise ValueError("Canonical roadmap drifted")
    if authority.get("governance") != "CT-ADR-GOV-011":
        raise ValueError("Governance decision drifted")
    if authority.get("provider_is_sovereign_authority") is not False:
        raise ValueError("Provider cannot become CrownThrive sovereign authority")
    if authority.get("provider_capability_implies_deployment") is not False:
        raise ValueError("Provider capability cannot imply CrownThrive deployment")
    if authority.get("provider_capability_implies_entitlement") is not False:
        raise ValueError("Provider capability cannot imply CrownThrive entitlement")
    if authority.get("production_provider_mutation_enabled") is not False:
        raise ValueError("Phase 2.99 provider mutation must remain disabled")

    classification = contract.get("classification", {})
    if classification.get("phase_2_99_allowed_side_effects") != ["none", "read"]:
        raise ValueError("Phase 2.99 side-effect boundary drifted")
    if classification.get("phase_2_99_write_behavior") != "fail_closed":
        raise ValueError("Phase 2.99 write behavior must fail closed")

    future_write = contract.get("future_write_contract", {})
    if future_write.get("active") is not False:
        raise ValueError("Future write contract must remain inactive")
    required_write_sequence = [
        "sovereign_authorization",
        "read_before",
        "bounded_allowlisted_write",
        "immediate_readback",
        "exact_field_comparison",
        "dail_evidence",
        "rollback_or_compensating_action",
    ]
    if future_write.get("required_sequence") != required_write_sequence:
        raise ValueError("Future write sequence drifted")
    if future_write.get("wildcard_field_write") is not False:
        raise ValueError("Wildcard field writes are prohibited")

    mcp = contract.get("mcp_contract", {})
    if mcp.get("protocol") != "2026-07-28":
        raise ValueError("MCP protocol drifted")
    if mcp.get("private_cache_required") is not True:
        raise ValueError("MCP cache scope must remain private")
    if mcp.get("input_schema_validation_required") is not True:
        raise ValueError("MCP input schema validation is required")
    if mcp.get("mutating_tools_phase_2_99") != "disabled":
        raise ValueError("MCP mutating tools must remain disabled")

    error_codes = {item.get("code") for item in contract.get("standard_errors", []) if isinstance(item, dict)}
    required_errors = {
        "AUTH_REQUIRED",
        "AUTHZ_DENIED",
        "SCHEMA_INVALID",
        "GOVERNANCE_APPROVAL_REQUIRED",
        "HUMAN_AUTHORITY_REQUIRED",
        "PROVIDER_STATE_UNVERIFIED",
        "PROVIDER_UNAVAILABLE",
        "RATE_LIMITED",
        "RESPONSE_SCHEMA_INVALID",
        "WRITE_GATE_CLOSED",
        "WEBHOOK_SIGNATURE_INVALID",
        "WEBHOOK_REPLAY",
    }
    missing = sorted(required_errors - error_codes)
    if missing:
        raise ValueError(f"Missing standard adapter errors: {missing}")


def request_shape_error(request: Any, contract: dict[str, Any]) -> str | None:
    if not isinstance(request, dict):
        return "SCHEMA_INVALID"
    required = contract.get("request_envelope", {}).get("required", [])
    for field in required:
        if field not in request:
            return "SCHEMA_INVALID"
    actor = request.get("actor")
    if not isinstance(actor, dict):
        return "SCHEMA_INVALID"
    for field in contract.get("request_envelope", {}).get("actor_required", []):
        if field not in actor:
            return "SCHEMA_INVALID"
    if not isinstance(request.get("input"), dict):
        return "SCHEMA_INVALID"
    if contains_forbidden_secret_key(request.get("input")):
        return "SCHEMA_INVALID"
    if request.get("side_effect_class") not in contract.get("classification", {}).get("side_effect_classes", []):
        return "SCHEMA_INVALID"
    if request.get("data_class") not in contract.get("classification", {}).get("data_classes", []):
        return "SCHEMA_INVALID"
    if request.get("risk_class") not in contract.get("classification", {}).get("autonomy_classes", []):
        return "SCHEMA_INVALID"
    for field in ("request_id", "correlation_id", "idempotency_key", "adapter_id", "operation_id"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            return "SCHEMA_INVALID"
    return None


def result(outcome: str, error_code: str | None) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "error_code": error_code,
        "side_effect_performed": False,
    }


def evaluate_case(case: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    request = case.get("request")
    provider = case.get("provider")
    shape_error = request_shape_error(request, contract)
    if shape_error:
        return result("deny", shape_error)
    if not isinstance(provider, dict):
        return result("deny", "SCHEMA_INVALID")

    actor = request["actor"]
    if actor.get("authenticated") is not True:
        return result("deny", "AUTH_REQUIRED")

    resource_org = request["input"].get("resource_org_id")
    actor_org = actor.get("org_id")
    if resource_org is not None and resource_org != actor_org:
        return result("deny", "AUTHZ_DENIED")

    if request.get("side_effect_class") not in {"none", "read"}:
        return result("deny", "WRITE_GATE_CLOSED")

    risk_class = request.get("risk_class")
    if risk_class == "D3":
        return result("hold", "HUMAN_AUTHORITY_REQUIRED")
    if risk_class == "D2" and request["input"].get("governance_approved") is not True:
        return result("hold", "GOVERNANCE_APPROVAL_REQUIRED")

    if provider.get("deployment_state") != "verified":
        return result("hold", "PROVIDER_STATE_UNVERIFIED")
    if provider.get("rate_allowed") is not True:
        return result("error", "RATE_LIMITED")
    if provider.get("available") is not True:
        return result("error", "PROVIDER_UNAVAILABLE")

    if provider.get("transport") == "webhook":
        if provider.get("signature_valid") is not True:
            return result("deny", "WEBHOOK_SIGNATURE_INVALID")
        if provider.get("replay_detected") is True:
            return result("deny", "WEBHOOK_REPLAY")

    if provider.get("response_schema_valid") is not True:
        return result("error", "RESPONSE_SCHEMA_INVALID")

    return result("allow", None)


def run_fixture(contract: dict[str, Any], fixture: dict[str, Any]) -> list[str]:
    if fixture.get("fixture_id") != "ct.fixture.chlom.adapter-conformance.v1":
        raise ValueError("Adapter fixture ID drifted")
    if fixture.get("contract_id") != contract.get("contract_id"):
        raise ValueError("Fixture contract ID does not match adapter contract")
    if fixture.get("phase") != "2.99":
        raise ValueError("Fixture must remain Phase 2.99")

    failures: list[str] = []
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Adapter fixture must include cases")
    for case in cases:
        if not isinstance(case, dict):
            failures.append("<non-object-case>: invalid case object")
            continue
        case_id = str(case.get("case_id", "<missing>"))
        expected = case.get("expected")
        if not isinstance(expected, dict):
            failures.append(f"{case_id}: missing expected result")
            continue
        observed = evaluate_case(case, contract)
        for key in ("outcome", "error_code", "side_effect_performed"):
            if observed.get(key) != expected.get(key):
                failures.append(
                    f"{case_id}: {key} observed={observed.get(key)!r} expected={expected.get(key)!r}"
                )
    return failures


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    fixture = load_json(FIXTURE_PATH)
    validate_contract(contract)
    failures = run_fixture(contract, fixture)
    if failures:
        for item in failures:
            print(f"FAIL: {item}")
        return 1
    print("CHLOM adapter conformance v1 passed.")
    print(f"Cases: {len(fixture['cases'])}; provider mutation: disabled; network calls: 0.")
    print("MCP protocol: 2026-07-28; provider authority: false; writes: fail closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
