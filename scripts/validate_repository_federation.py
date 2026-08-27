#!/usr/bin/env python3
"""Fail-closed validation for the CrownThrive repository convergence fabric."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from penta.repository_fabric.fabric import ConvergenceError, canonical_sha256, validate_control_plane


POLICY_PATH = ROOT / "developers/manifests/repository-federation-control-plane.v1.json"
FAILOVER_PATH = ROOT / "developers/manifests/repository-failover-policy.v1.json"
STATUS_PATH = ROOT / "developers/manifests/repository-convergence-status.v1.json"
NODE_PATH = ROOT / ".crownthrive/penta-node.v1.json"
MESH_PATH = ROOT / "federation/penta-mesh.v1.json"
MESH_STATUS_PATH = ROOT / "federation/penta-mesh.status.v1.json"
ORGANIC_CATALOG_PATH = ROOT / "data/penta/systems.extensions.organic-control-plane.json"
COMPONENT_PATH = ROOT / "penta/registry/penta-component-registry.v1.json"
TRUSTED_WORKFLOW = ROOT / ".github/workflows/penta-repository-convergence.yml"
CONTRACT_WORKFLOW = ROOT / ".github/workflows/penta-repository-convergence-contract.yml"
SECRET_RE = re.compile(r"\$\{\{\s*(?:secrets\.|github\.token)")
TRUST_GUARD = (
    "github.repository == 'crownthrive1/CrownThrive-Support' "
    "&& github.ref == 'refs/heads/main'"
)


class DuplicateKeyError(ValueError):
    pass


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
    except (OSError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise ConvergenceError(f"invalid governed JSON {path.relative_to(ROOT)}: {exc}") from None
    if not isinstance(value, dict):
        raise ConvergenceError(f"JSON root must be an object: {path.relative_to(ROOT)}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConvergenceError(message)


def validate_attestation(value: dict[str, Any], hub: dict[str, Any], version: str) -> None:
    required = {
        "schema",
        "version",
        "stable_id",
        "parent_id",
        "mesh_contract_version",
        "default_branch",
        "visibility_class",
        "roles",
        "build_profile",
        "authority",
        "information_flow",
    }
    require(set(value) == required, "hub node attestation fields drifted")
    require(value["schema"] == "ct.penta.repository-node-attestation.v1", "node schema drifted")
    require(value["version"] == "1.0.0", "node version drifted")
    require(value["stable_id"] == hub["stable_id"], "hub stable ID mismatch")
    require(value["parent_id"] == "ct.repo.crownthrive-support", "node parent mismatch")
    require(value["mesh_contract_version"] == version, "node mesh version mismatch")
    require(value["default_branch"] == "main", "node default branch mismatch")
    require(value["visibility_class"] == "public", "hub visibility class mismatch")
    require(sorted(value["roles"]) == sorted(hub["roles"]), "hub roles mismatch")
    require(set(value["information_flow"]) == {"afferent", "efferent", "lateral"}, "tri-directional node flow missing")
    require(
        value["authority"]
        == {
            "direct_main_write": False,
            "self_activation": False,
            "d3_human_reserved": True,
            "provider_writes_require_exact_certification": True,
        },
        "node authority boundary drifted",
    )


def validate_workflow_boundary() -> None:
    trusted = TRUSTED_WORKFLOW.read_text(encoding="utf-8")
    contract = CONTRACT_WORKFLOW.read_text(encoding="utf-8")
    require("  pull_request:" not in trusted, "trusted convergence workflow accepts pull requests")
    require("  pull_request:" in contract, "contract convergence workflow must accept pull requests")
    require("  push:" not in contract and "  schedule:" not in contract, "contract workflow must be pull-request only")
    require(not SECRET_RE.search(contract), "pull-request convergence contract references credentials")
    require("id-token: write" not in contract, "pull-request convergence contract can mint OIDC")
    require(not re.search(r"(?m)^\s+[a-z-]+:\s+write\s*$", contract), "pull-request convergence permissions are not read-only")
    require(TRUST_GUARD in trusted, "trusted convergence job lacks exact-main repository guard")
    require("environment: penta-repository-readonly" in trusted, "trusted convergence job lacks environment gate")
    require(SECRET_RE.search(trusted) is not None, "trusted convergence workflow has no credential binding")
    require(
        not re.search(r"(?m)^    env:\s*$", trusted),
        "trusted convergence credentials must not be bound at job scope",
    )
    readback_start = trusted.find("      - name: Read all authorized nodes and reconcile")
    readback_end = trusted.find("\n      - name:", readback_start + 1)
    require(readback_start >= 0 and readback_end > readback_start, "trusted readback step boundary missing")
    secret_positions = [match.start() for match in SECRET_RE.finditer(trusted)]
    require(
        secret_positions and all(readback_start <= position < readback_end for position in secret_positions),
        "trusted credentials must be bound only to the authenticated readback step",
    )
    require("ref: refs/heads/main" in trusted, "trusted convergence checkout is not exact main")
    require("persist-credentials: false" in trusted, "trusted convergence checkout persists credentials")
    require("continue-on-error" not in trusted, "trusted convergence workflow tolerates observation failure")
    require("if: always()" in trusted, "trusted convergence workflow must preserve HOLD evidence")
    require("python3 scripts/run_repository_convergence.py" in trusted, "trusted convergence runtime is not wired")
    for fragment in (
        "umask 077",
        "${{ runner.temp }}/repository-convergence/",
        "--output",
        "--emergency-journal",
        "--organic-journal",
    ):
        require(fragment in trusted, f"trusted convergence evidence boundary missing {fragment!r}")
    require("path: evidence/" not in trusted, "trusted workflow may upload unrelated repository evidence")
    require("python3 -m unittest" in contract, "contract workflow does not run adversarial tests")


def main() -> int:
    required_files = [
        POLICY_PATH,
        FAILOVER_PATH,
        STATUS_PATH,
        NODE_PATH,
        MESH_PATH,
        MESH_STATUS_PATH,
        ORGANIC_CATALOG_PATH,
        COMPONENT_PATH,
        TRUSTED_WORKFLOW,
        CONTRACT_WORKFLOW,
        ROOT / "penta/repository_fabric/fabric.py",
        ROOT / "penta/repository_fabric/github.py",
        ROOT / "penta/repository_fabric/cold.py",
        ROOT / "scripts/run_repository_convergence.py",
        ROOT / "tests/test_penta_repository_fabric.py",
    ]
    required_files.extend(
        ROOT / name
        for name in (
            "schemas/penta/repository-node-attestation.schema.json",
            "schemas/penta/repository-sync-event.schema.json",
            "schemas/penta/repository-failover-receipt.schema.json",
            "schemas/penta/repository-family.schema.json",
            "schemas/penta/repository-observation.schema.json",
            "schemas/penta/repository-cold-snapshot.schema.json",
        )
    )
    missing = [path.relative_to(ROOT).as_posix() for path in required_files if not path.is_file()]
    require(not missing, "repository convergence files missing: " + ", ".join(missing))

    policy = load(POLICY_PATH)
    rows = validate_control_plane(policy)
    require(len(rows) == 13, "repository control-plane census must remain exactly 13")
    require(sum(row["visibility_class"] == "public" for row in rows) == 3, "public node census drifted")
    require(sum(row["visibility_class"] == "restricted" for row in rows) == 10, "restricted node census drifted")
    corrected = next(
        (row for row in rows if row["stable_id"] == "ct.repo.cie-private-control"),
        None,
    )
    require(
        corrected is not None
        and corrected["visibility_class"] == "restricted"
        and corrected["expected_provider_visibility"] == "private"
        and corrected.get("locator") == "restricted_ref_only",
        "Private-CrownThrive-CIE visibility anomaly must remain restricted and HOLD",
    )
    hub = next(row for row in rows if row["stable_id"] == policy["canonical_hub_id"])
    validate_attestation(load(NODE_PATH), hub, policy["version"])
    require(policy["implementation"]["runtime"] == "penta/repository_fabric", "runtime reference drifted")
    require(policy["implementation"]["validator"] == "scripts/validate_repository_federation.py", "validator reference drifted")
    require(
        policy.get("release_governance")
        == {
            "stable_id": "ct.repo.crownthrive-support",
            "active_default_branch_ruleset_required": True,
            "required_check_contexts": ["CrownThrive governed merge gate"],
            "max_bypass_actor_count": 0,
            "exact_head_success_required": True,
        },
        "release governance must require a successful exact-head gate with zero bypass",
    )

    failover = load(FAILOVER_PATH)
    require(failover["schema"] == "ct.penta.repository-failover-policy.v1", "failover schema drifted")
    routes = {route.get("class"): route for route in failover.get("routes", [])}
    require(set(routes) == {"HOT_PRIMARY", "COLD_RECOVERY", "SILENT_EMERGENCY"}, "hot/cold/silent routes incomplete")
    require(routes["COLD_RECOVERY"].get("write_state") == "read_only", "cold recovery must remain read-only")
    require(routes["COLD_RECOVERY"].get("cutover_certified") is False, "unproven cold cutover cannot be certified")
    require(routes["SILENT_EMERGENCY"].get("external_broadcast") is False, "silent emergency cannot broadcast")
    require(routes["SILENT_EMERGENCY"].get("authority_effect") == "reduce_only", "silent emergency must reduce authority")
    require(routes["SILENT_EMERGENCY"].get("live_delivery_certified") is False, "unproven emergency delivery cannot be certified")

    status = load(STATUS_PATH)
    require(status.get("record_class") == "committed_non_live_baseline", "committed status must not claim live truth")
    require(status.get("provider_coordinates_included") is False, "committed status exposes provider coordinates")
    require(status.get("production_certified") is False, "repository fabric cannot claim production certification")
    require(status.get("census", {}).get("expected") == 13, "status census drifted")
    require(status.get("census", {}).get("public_detail_count") == 3, "status public census drifted")
    require(status.get("census", {}).get("restricted_aggregate_count") == 10, "status restricted census drifted")
    require(status.get("census", {}).get("held") == 13, "baseline must fail closed pending readback")
    anomalies = {
        item.get("stable_id"): item.get("state")
        for item in status.get("known_public_anomalies", [])
        if isinstance(item, dict)
    }
    require(
        anomalies.get("ct.repo.cie-private-control") == "HOLD_VISIBILITY_MISMATCH",
        "visibility mismatch HOLD is missing from status",
    )
    provider = status.get("authenticated_provider_evidence", {})
    require(provider.get("adapter") == "github_app_readback", "authenticated provider evidence is unbound")
    require(provider.get("support_prior_head_check_run_count") == 175, "Support check-run evidence drifted")
    require(provider.get("support_ruleset_id") == 21528790, "Support ruleset evidence drifted")
    require(
        provider.get("support_ruleset_state") == "ACTIVE_DEFAULT_BRANCH_WITH_BYPASS_ACTORS",
        "Support bypass evidence must remain explicit",
    )
    require(
        provider.get("required_context_prior_head_state") == "COMPLETED_CANCELLED",
        "cancelled exact-head gate evidence must remain HOLD",
    )
    require(provider.get("chlom_ruleset_state") == "HOLD_NO_RULESET", "CHLOM ruleset HOLD drifted")
    require(
        provider.get("chlom_prior_head_workflows") == {"success": 1, "ofac_failure": 1},
        "CHLOM authenticated workflow evidence drifted",
    )
    require(provider.get("zero_workflow_run_claim_retracted") is True, "invalid zero-run claim was restored")
    require(
        provider.get("pending_release_requirement")
        == "SUCCESSFUL_EXACT_HEAD_GATE_AND_ZERO_BYPASS_ACTORS",
        "pending release gate requirement drifted",
    )
    candidate_sync = status.get("candidate_sync_disposition", {})
    held_candidate_paths = {
        "penta/repository_fabric/candidate.py": "492618aaffe5a628805644f6f324c3b81cbd98c35ce90a30ecd8953bdfce915c",
        "penta/repository_fabric/templates.py": "455443045105a6fbb6b54e1e50d0a132647b5f5891e715df5bec38f6073d6058",
        "scripts/sync_repository_node_contracts.py": "fd0da0ba44c4e53782440fb931d8e57e02782805f7d0e81150fc6f074ecab232",
        ".github/workflows/penta-repository-node-contract-sync.yml": "afdd06ef90c0f86896162a9269e5cf5f9dc5a36c41fb5470a10fad1e307e8e20",
        "tests/test_penta_repository_candidate_sync.py": "c6ce150b687bd98d28032aaf02263847e7ecd912221fa9f325e5f5d6060f58df",
    }
    require(candidate_sync.get("state") == "HOLD_SUPERSEDED_NOT_INTEGRATED", "candidate-sync source pack must remain HOLD/SUPERSEDED")
    require(
        candidate_sync.get("source_observation")
        == "stable_pre_cutoff_untracked_worktree_candidate_not_authoritative_commit",
        "candidate-sync untracked source boundary drifted",
    )
    require(
        candidate_sync.get("observed_candidate_digests") == held_candidate_paths,
        "candidate-sync observed digest record drifted",
    )
    require(
        candidate_sync.get("source_code_copied_into_canonical") is False
        and candidate_sync.get("provider_effect_performed") is False,
        "held candidate-sync pack cannot claim source integration or provider effects",
    )
    require(
        len(candidate_sync.get("hold_reasons", [])) >= 11
        and len(candidate_sync.get("required_evidence_before_reconsideration", [])) >= 11,
        "candidate-sync HOLD evidence requirements are incomplete",
    )
    candidate_evidence = candidate_sync.get("captured_adversarial_evidence", {})
    require(
        candidate_evidence.get("duplicate_restricted_binding_accepted") is True
        and candidate_evidence.get("provider_sensitivity_flag_can_disable_redaction") is True
        and candidate_evidence.get("fully_aligned_state_reported") == "CANDIDATES_READY"
        and candidate_evidence.get("fully_aligned_provider_write_count") == 0
        and candidate_evidence.get("tests_cover_all_blocking_findings") is False,
        "candidate-sync captured adversarial evidence drifted",
    )
    prohibited = set(candidate_sync.get("effects_prohibited_while_held", []))
    require(
        {
            "candidate_branch_create",
            "pull_request_create_or_update",
            "direct_main_write",
            "merge",
            "visibility_change",
            "release_or_dispatch",
            "secret_or_coordinate_return",
            "production_certification",
            "d3_effect",
        }
        == prohibited,
        "candidate-sync prohibited effect boundary drifted",
    )
    require(
        all(not (ROOT / path).exists() for path in held_candidate_paths),
        "held candidate-sync source pack was copied into canonical without its evidence gate",
    )

    mesh = load(MESH_PATH)
    mesh_status = load(MESH_STATUS_PATH)
    require(mesh.get("version") == "1.1.0", "repository mesh version drifted")
    require(mesh.get("repository_control_plane") == POLICY_PATH.relative_to(ROOT).as_posix(), "mesh control-plane link drifted")
    require(mesh.get("inventory", {}).get("expected_physical_repository_count") == 13, "mesh census drifted")
    require(mesh.get("inventory", {}).get("public_contract_detail_count") == 3, "mesh public census drifted")
    require(mesh.get("inventory", {}).get("restricted_repository_count") == 10, "mesh restricted census drifted")
    require(mesh.get("inventory", {}).get("restricted_coordinates") == "restricted_ref_only", "mesh private boundary drifted")
    require(mesh.get("interoperability", {}).get("information_flow") == ["afferent", "efferent", "lateral"], "mesh tri-directional flow drifted")
    require(mesh_status.get("record_class") == "committed_non_live_baseline", "mesh status must remain non-live")
    require(mesh_status.get("census", {}).get("public_contract_nodes") == 3, "mesh status public census drifted")
    require(mesh_status.get("census", {}).get("restricted_nodes") == 10, "mesh status restricted census drifted")
    require(mesh_status.get("private_redaction") is True, "mesh status private redaction disabled")
    require(mesh_status.get("restricted_provider_coordinates_included") is False, "mesh status contains restricted coordinates")
    require(mesh_status.get("provider_message_or_delivery_identifiers_included") is False, "mesh status contains unrelated provider delivery identifiers")
    require(mesh_status.get("production_certified") is False, "mesh status cannot claim production certification")
    mesh_text = MESH_PATH.read_text(encoding="utf-8") + MESH_STATUS_PATH.read_text(encoding="utf-8")
    require("CrownThrive-CIE" not in mesh_text, "privacy-safe mesh exposes restricted CIE coordinates")
    require("provider_message_id" not in mesh_text, "privacy-safe mesh exposes provider delivery identifiers")

    organic_catalog = load(ORGANIC_CATALOG_PATH)
    component = load(COMPONENT_PATH)
    organic_keys = {item.get("machine_key") for item in organic_catalog.get("systems", [])}
    require(organic_keys == {"penta.brain", "penta.spine", "penta.nerves", "penta.body", "penta.load", "penta.balancer"}, "organic system catalog drifted or duplicates canonical health/cost")
    component_keys = [item.get("key") for item in component.get("components", [])]
    require(len(component_keys) == len(set(component_keys)), "component registry contains duplicate machine keys")
    federation_component = next(
        (item for item in component["components"] if item.get("key") == "penta.federation"),
        None,
    )
    require(
        isinstance(federation_component, dict)
        and federation_component.get("runtime_ref") == "penta/repository_fabric",
        "repository fabric is not implanted into PentaFederation",
    )

    schema_paths = required_files[-6:]
    for schema_path in schema_paths:
        schema = load(schema_path)
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"schema draft drifted: {schema_path.name}")
    strict_schema_names = {
        "repository-node-attestation.schema.json",
        "repository-sync-event.schema.json",
        "repository-failover-receipt.schema.json",
        "repository-family.schema.json",
        "repository-observation.schema.json",
        "repository-cold-snapshot.schema.json",
    }
    for schema_path in schema_paths:
        if schema_path.name in strict_schema_names:
            require(
                load(schema_path).get("additionalProperties") is False,
                f"schema root is not fail-closed: {schema_path.name}",
            )
    require(
        "release_governance" in load(ROOT / "schemas/penta/repository-observation.schema.json").get("properties", {}),
        "canonical release-governance observation schema is missing",
    )

    validate_workflow_boundary()
    print("Repository federation control-plane validation passed.")
    print("Census: 13 nodes (3 public contract nodes, 10 restricted runtime bindings).")
    print("Routes: authenticated hot; independently verified read-only cold; sealed authority-reducing silent emergency.")
    print("Candidate-sync provider-write source pack: HOLD_SUPERSEDED_NOT_INTEGRATED pending redesign and independent authority review.")
    print("Certification boundary: implementation/controlled tests only; provider binding, live cutover, deployment and D3 remain HOLD.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConvergenceError as exc:
        raise SystemExit(f"ERROR: {exc}") from None
