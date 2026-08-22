#!/usr/bin/env python3
"""Validate the public-safe CrownThrive Interoperability Adapter SDK templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "plugins/crownthrive-interoperability/sdk"
ADAPTER = SDK / "adapter-package.template.json"
ROUTE = SDK / "route.template.json"
README = SDK / "README.md"


def load(path: Path) -> dict[str, Any]:
    assert path.is_file(), f"Missing SDK artifact: {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    adapter = load(ADAPTER)
    route = load(ROUTE)
    assert README.is_file()

    assert adapter["template_version"] == "1.0.0"
    assert adapter["lifecycle_state"] == "candidate"
    assert adapter["authority_ceiling"] == "D2"
    assert adapter["owner_agent_id"] != adapter["verifier_agent_id"]
    assert adapter["auth"]["raw_credential_in_package"] is False
    assert adapter["auth"]["credential_ref_public"] is False
    assert adapter["auth"]["least_privilege_required"] is True
    assert adapter["provider_limits"]["local_budget_semantics"] == (
        "-1=unlimited_local_ceiling;0=disabled;positive=local_monthly_ceiling;null=unresolved_fail_closed"
    )
    assert adapter["provider_limits"]["provider_limits_authoritative"] is True
    required_tests = set(adapter["testing"]["required_classes"])
    assert {"schema", "compatibility", "negative", "security", "privacy", "idempotency"} <= required_tests
    assert adapter["testing"]["originator_can_self_verify"] is False
    governance = adapter["governance"]
    assert governance["D3_auto"] is False
    assert governance["sovereign_vote_effect"] is False
    assert governance["direct_main_merge"] is False
    assert governance["provider_write_enabled"] is False
    assert governance["checkout_enabled"] is False
    assert governance["history_policy"] == "append_or_supersede_never_silent_delete"

    for capability in adapter["capabilities"]:
        assert capability["risk_class"] in {"D0", "D1", "D2"}
        assert capability["input_schema"]["type"] == "object"
        assert capability["input_schema"].get("additionalProperties") is False
        if capability["operation_mode"] == "write":
            assert adapter["canaries"]["write"]["required"] is True
            assert adapter["canaries"]["rollback"]["required_for_write"] is True
            assert adapter["canaries"]["read_after_write"]["required_for_write"] is True

    for binding in adapter["contracts"]:
        assert binding["exact_version_required"] is True
        assert binding["field_mapping_public"] is False
        assert binding["loss_analysis_required"] is True

    assert route["template_version"] == "1.0.0"
    assert route["route_state"] == "candidate"
    assert route["authority_class"] in {"D0", "D1", "D2"}
    assert route["owner_agent_id"] != route["verifier_agent_id"]
    assert route["rollback_policy"]["silent_delete"] is False
    assert route["rollback_policy"]["provider_rollback_required_for_write"] is True
    assert route["rollback_policy"]["read_after_write_required"] is True
    assert route["observability"]["evidence_receipt_required"] is True
    assert route["observability"]["route_score_required"] is True
    assert route["observability"]["secret_exposed"] is False
    assert route["execution"]["performed_by_template"] is False
    assert route["execution"]["provider_write_enabled"] is False
    assert route["execution"]["D3_auto"] is False
    assert route["execution"]["sovereign_vote_effect"] is False

    denied = set(route["data_minimization_policy"]["deny"])
    assert {"credential", "private_key", "payment_credential", "private_identity_mapping"} <= denied
    assert route["data_minimization_policy"]["unknown_fields"] == "deny_and_quarantine"
    assert route["idempotency_strategy"]
    assert route["retry_policy"]["max_attempts"] >= 1
    assert "exact_contract_and_version" in route["activation_gates"]
    assert "independent_verification" in route["activation_gates"]

    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in (ADAPTER, ROUTE, README)
    ).lower()
    for fragment in (
        "controlled test",
        "provider writes",
        "d3",
        "never silently delete",
        "provider throttles",
        "raw credentials",
    ):
        assert fragment in corpus, fragment

    print("CrownThrive Interoperability Adapter SDK invariants: PASS")


if __name__ == "__main__":
    main()
