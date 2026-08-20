#!/usr/bin/env python3
"""Validate CrownThrive parent-child repository federation and IP boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEDERATION = ROOT / "developers/manifests/repository-federation.v1.json"
ALGORITHMS = ROOT / "developers/manifests/framework-algorithm-registry.v1.json"
CHILD_TEMPLATE = ROOT / "developers/templates/framework-child-federation-contract.v1.json"
FEDERATION_CLIENT = ROOT / "scripts/repository_federation_sync.py"
CIE_CLIENT = ROOT / "scripts/cie_scan.py"
FEDERATION_DOC = ROOT / "technology/repository-federation-control-plane.mdx"
FRAMEWORK_REPO_DOC = ROOT / "automation/framework-repository-governance-standard.mdx"
FEDERATION_WORKFLOW = ROOT / ".github/workflows/repository-federation-governance.yml"

REQUIRED_PARENT_LOCKS = {
    "constitutional_governance",
    "d3_human_authority",
    "security_privacy",
    "rights_legal",
    "money_movement",
    "repository_federation",
    "vault_secret_policy",
    "phase_hard_gates",
}
SEALED_PUBLIC_FORBIDDEN = {
    "severity_deductions",
    "confidence_multipliers",
    "recurrence_multipliers",
    "calibration_weights",
    "private_eval_corpora",
    "proprietary_detection_rules",
}
EXPECTED_CIE_CONTRACT_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: Path) -> Any:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(walk_keys(item))
    return keys


def public_contract_digest(contract: dict[str, Any]) -> str:
    rendered = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def main() -> int:
    fed = load(FEDERATION)
    alg = load(ALGORITHMS)
    load(CHILD_TEMPLATE)

    if fed.get("manifest_id") != "ct.manifest.repository-federation.v1":
        fail("federation manifest identity drift")
    authority = fed.get("authority", {})
    if authority.get("canonical_parent_repository") != "crownthrive1/CrownThrive-Support":
        fail("canonical parent repository drift")
    if authority.get("child_repository_self_activation") is not False or authority.get("parent_certification_required") is not True:
        fail("child self-activation must remain prohibited and parent certification mandatory")
    if authority.get("d3_human_reserved") is not True:
        fail("repository federation cannot create D3 authority")

    auth = fed.get("runtime", {}).get("auth", {})
    if auth.get("scheme") != "github_actions_oidc":
        fail("federation must use GitHub Actions OIDC")
    if auth.get("issuer") != "https://token.actions.githubusercontent.com":
        fail("GitHub OIDC issuer drift")
    if auth.get("audience") != "crownthrive-repository-federation":
        fail("GitHub OIDC audience drift")
    if auth.get("long_lived_shared_secret_required") is not False:
        fail("repository federation cannot require a long-lived shared repository secret")

    if set(fed.get("parent_lock_keys", [])) != REQUIRED_PARENT_LOCKS:
        fail("parent lock-key set drift")
    child_policy = fed.get("framework_child_policy", {})
    required_false = (
        "may_override_parent_lock_keys", "may_change_quorum", "may_self_add_vote",
        "may_self_certify", "may_create_d3_authority", "transport_messages_create_votes",
        "framework_subagents_create_votes",
    )
    for key in required_false:
        if child_policy.get(key) is not False:
            fail(f"framework-child non-negotiable drift: {key}")
    if child_policy.get("all_governed_agents_transport_access") is not True:
        fail("governed agents must retain federation transport access")
    if child_policy.get("bidirectional_reference_required") is not True:
        fail("bidirectional repository references required")
    if child_policy.get("child_backlink_file") != ".crownthrive/federation.json":
        fail("child backlink path drift")

    repos = {item.get("repo_id"): item for item in fed.get("repositories", [])}
    if set(repos) != {"ct.repo.crownthrive-support", "ct.repo.cie"}:
        fail("unexpected current federation repository set")
    parent = repos["ct.repo.crownthrive-support"]
    child = repos["ct.repo.cie"]
    if parent.get("role") != "canonical_parent" or parent.get("github_repository_id") != 1336348391 or parent.get("operationally_enabled") is not True:
        fail("canonical parent identity/state drift")
    if child.get("repo_full_name") != "crownthrive1/CrownThrive-CIE" or child.get("parent_repo_id") != parent.get("repo_id"):
        fail("CIE parent-child identity drift")
    if child.get("github_repository_id") is None:
        if child.get("governance_state") != "pending_provisioning" or child.get("operationally_enabled") is not False:
            fail("unprovisioned CIE child must remain pending and disabled")
        if child.get("backlink_state") != "blocked_repo_not_provisioned":
            fail("missing CIE repository must expose backlink block")
    elif child.get("governance_state") != "linked_governed":
        if child.get("operationally_enabled") is not False:
            fail("non-certified child cannot be operational")

    if fed.get("cross_chain", {}).get("per_repository_previous_hash_link") is not True:
        fail("cross-repository event hash chain required")
    if fed.get("cross_chain", {}).get("public_repository_stores_private_event_payloads") is not False:
        fail("private federation event payloads cannot be projected public")

    algorithm_rows = alg.get("algorithms", [])
    if len(algorithm_rows) != 1:
        fail("expected one current framework algorithm")
    cie = algorithm_rows[0]
    if cie.get("algorithm_id") != "ct.algorithm.cie.v1" or cie.get("framework_id") != "ct.framework.cultural-imprint-engine":
        fail("CIE algorithm identity drift")
    contract = cie.get("public_contract", {})
    if public_contract_digest(contract) != EXPECTED_CIE_CONTRACT_DIGEST:
        fail("CIE public contract digest drift")
    if cie.get("public_contract_digest") != EXPECTED_CIE_CONTRACT_DIGEST:
        fail("CIE registered public contract digest drift")
    if cie.get("classification") != "RESTRICTED_INSTITUTIONAL":
        fail("CIE algorithm implementation must remain restricted")
    if cie.get("vault_policy_ref") != "vault:ct.algorithm.cie.v1.policy_bundle":
        fail("CIE Vault runtime reference drift")
    if set(cie.get("sealed_fields_not_public", [])) != SEALED_PUBLIC_FORBIDDEN:
        fail("sealed CIE field list drift")
    if walk_keys(alg) & SEALED_PUBLIC_FORBIDDEN:
        # sealed_fields_not_public intentionally names them as values, never keys.
        fail("sealed CIE calibration appeared as public manifest keys")

    client_text = FEDERATION_CLIENT.read_text(encoding="utf-8")
    cie_text = CIE_CLIENT.read_text(encoding="utf-8")
    forbidden_static = "SUPABASE_" + "SERVICE_ROLE_KEY"
    if forbidden_static in client_text or forbidden_static in cie_text:
        fail("public federation/CIE client contains a service-role secret reference")
    for token in ("SEVERITY_DEDUCTIONS", "confidence_multipliers", "recurrence_multipliers"):
        if token in cie_text:
            fail(f"public CIE client exposes protected calibration: {token}")

    for path in (FEDERATION_DOC, FRAMEWORK_REPO_DOC, FEDERATION_WORKFLOW):
        if not path.is_file():
            fail(f"missing federation institutional surface: {path.relative_to(ROOT)}")

    readiness = 88
    verdict = "CONTROL_PLANE_PASS_CHILD_LINK_BLOCKED"
    if child.get("github_repository_id") is not None and child.get("governance_state") == "linked_governed" and child.get("backlink_state") == "verified":
        readiness = 100
        verdict = "FEDERATION_LINK_PASS"
    print(f"Repository federation validation PASS: readiness={readiness}/100; verdict={verdict}; parent authority fixed; OIDC-only transport; Vault algorithm boundary enforced; child self-activation prohibited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
