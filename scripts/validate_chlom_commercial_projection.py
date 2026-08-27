#!/usr/bin/env python3
"""Validate and materialize the CHLOM public commercial overlay.

The canonical public-safe parent is authoritative for the managed overlay. The
builder is intentionally non-destructive: it writes only manifest-managed files,
never deletes unmanaged child paths, and produces deterministic output for an
unchanged parent commit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/chlom-protocol-commercial-projection.v1.json"
CONTRACT_PATH = ROOT / "developers/contracts/chlom-commercial-projection.contract.v1.json"
PENTAFABRIC_PATH = ROOT / "developers/manifests/chlom-pentafabric.v1.json"
AGENT_CANDIDATES_PATH = ROOT / "developers/manifests/chlom-agent-factory-candidates.v1.json"
API_MCP_CANDIDATES_PATH = ROOT / "developers/manifests/chlom-api-mcp-surface-candidates.v1.json"
ASSET_CLASSES_PATH = ROOT / "developers/manifests/chlom-pentafabric-asset-classes.v1.json"
COMMERCIAL_PACKAGES_PATH = ROOT / "developers/manifests/chlom-commercial-package-candidates.v1.json"
MESH_PATH = ROOT / "developers/manifests/chlom-mesh-failover.v1.json"
MAINTENANCE_PATH = ROOT / "developers/manifests/chlom-maintenance-projection-gate.v1.json"
MACHINE_ACCESS_PATH = ROOT / "developers/contracts/chlom-machine-access.contract.v1.json"
VAULT_BOUNDARY_PATH = ROOT / "developers/contracts/chlom-vault-boundary.contract.v1.json"
CONTINUOUS_BUILD_PATH = ROOT / "developers/contracts/chlom-continuous-build.contract.v1.json"

SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sb_secret_[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]

FORBIDDEN_CURRENT_CANON = (
    "DAL = Decentralized Attestation Ledger",
    "DAL = Decentralized Adjudication Layer",
    "DLA = Decentralized Licensing Authority",
)

GENERATED_PATHS = {".crownthrive/upstream.json"}
VERIFIED_SUPPORT_URL = "https://donate.stripe.com/28E7sKfU02tkbmi3SLbAs0h"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def exact_parent_sha() -> str:
    env_sha = os.environ.get("GITHUB_SHA", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", env_sha):
        return env_sha
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def exact_parent_timestamp(sha: str) -> str:
    """Use the immutable commit timestamp so same input produces same dist."""
    return subprocess.check_output(
        ["git", "show", "-s", "--format=%cI", sha], cwd=ROOT, text=True
    ).strip()


def validate_pentafabric(pentafabric: dict) -> None:
    assert pentafabric["canonical_name"] == "CrownThrive Pentafabric"
    assert pentafabric["layer_count"] == 5
    assert [layer["layer"] for layer in pentafabric["layers"]] == [1, 2, 3, 4, 5]
    assert pentafabric["canonical_terms"]["DAIL"] == "Decentralized Autonomous Information Ledger"
    assert pentafabric["canonical_terms"]["DLA"] == "Dynamic Licensing Asset"
    assert pentafabric["repository_family"]["canonical_public_safe_parent"] == "crownthrive1/CrownThrive-OS"
    assert pentafabric["repository_family"]["public_commercial_child"] == "crownthrive/chlom-protocol"
    assert pentafabric["repository_family"]["both_public"] is True
    assert pentafabric["repository_family"]["restricted_state_in_public_git"] is False
    assert pentafabric["operating_rules"]["execution_may_not_manufacture_authority"] is True
    assert pentafabric["operating_rules"]["provider_success_is_not_institutional_truth"] is True
    assert pentafabric["economic_authority"] == "ThriveEvergreen / ECAC"


def validate_agent_pack(agent_pack: dict) -> None:
    required_ids = {
        "ct.agent.chlom-rd-researcher",
        "ct.agent.chlom-rights-identity-steward",
        "ct.agent.chlom-compliance-oracle",
        "ct.agent.chlom-docs-projection-steward",
        "ct.agent.chlom-commercial-packager",
        "ct.agent.chlom-mesh-reliability",
    }
    ids = {agent["agent_id"] for agent in agent_pack["agents"]}
    assert required_ids <= ids
    assert agent_pack["factory_binding"]["direct_main_write"] is False
    assert agent_pack["factory_binding"]["self_merge"] is False
    assert agent_pack["factory_binding"]["self_certification"] is False
    assert agent_pack["monetization_boundary"]["commercial_activation_authority"] == "ThriveEvergreen / ECAC"


def validate_extended_fabric(
    api_mcp: dict,
    asset_classes: dict,
    commercial_packages: dict,
    mesh: dict,
    maintenance: dict,
    machine: dict,
    vault: dict,
) -> None:
    assert api_mcp["state"] == "CONTRACTED_CANDIDATES_NOT_PUBLICLY_ACTIVATED"
    assert api_mcp["public_endpoint_claim"] is False
    assert api_mcp["public_mcp_claim"] is False
    assert api_mcp["shared_rules"]["raw_secret_export"] is False
    assert api_mcp["economic_activation_authority"] == "ThriveEvergreen / ECAC"

    required_asset_classes = {
        "pallet", "module", "container", "component", "framework", "plugin", "skill",
        "agent", "oracle", "contract", "schema", "api", "mcp_server", "mcp_tool",
        "wireframe", "scaffold", "portal", "dashboard", "widget", "dynamic_licensing_asset",
        "did_profile", "fingerprint_profile", "dail_record_type", "commercial_package",
    }
    assert required_asset_classes <= set(asset_classes["classes"])
    assert asset_classes["articleization_required_for_material_assets"] is True
    assert asset_classes["documentation_rules"]["combination_article_may_replace_material_asset_article"] is False
    assert asset_classes["factory_rules"]["build_receipt_is_certification"] is False
    assert asset_classes["commercial_rules"]["sku_issuance_authority"] == "ThriveEvergreen"

    assert commercial_packages["state"] == "CANDIDATE_ONLY_PENDING_RIGHTS_EVIDENCE_AND_ECAC"
    assert commercial_packages["thriveevergreen_is_exclusive_sku_issuer"] is True
    assert commercial_packages["sku_values_issued_here"] is False
    assert commercial_packages["pricing_values_issued_here"] is False
    assert commercial_packages["checkout_activated_here"] is False
    assert all(pkg["economic_state"] == "PENDING_ECAC" for pkg in commercial_packages["packages"])

    assert mesh["state"] == "DOCUMENTED_AND_MONITORED_NOT_INFRASTRUCTURE_FAILOVER_CERTIFIED"
    assert mesh["observer_agent"] == "ct.agent.chlom-mesh-reliability"
    assert len(mesh["public_routes"]) >= 5
    assert mesh["high_consequence_runtime_rules"]["api_or_mcp_unreachable"] == "FAIL_CLOSED"
    assert mesh["high_consequence_runtime_rules"]["rights_state_inferred_from_cached_provider"] is False

    assert maintenance["state"] == "PAUSED_FOR_TARGETED_MAINTENANCE"
    assert maintenance["autonomous_external_mutation_allowed"] is False
    assert maintenance["scheduled_child_projection_allowed"] is False
    assert maintenance["automatic_child_projection_on_parent_push_allowed"] is False
    assert maintenance["commercial_external_activation_allowed"] is False
    assert maintenance["release_is_time_based"] is False
    assert maintenance["release_requires_machine_evidence"] is True

    assert machine["default_state"] == "DENY_UNLESS_EXPLICITLY_AUTHORIZED"
    assert machine["authority_rules"]["provider_success_is_institutional_truth"] is False
    assert machine["commercialization"]["economic_activation_authority"] == "ThriveEvergreen / ECAC"

    assert vault["runtime_binding_state"] == "PENDING_VERIFIED_RUNTIME_BINDING"
    assert vault["opaque_references_only"] is True
    assert vault["raw_secret_return"] is False
    assert vault["public_vault_locator"] is False
    assert vault["agent_rules"]["agents_may_export_raw_secret"] is False
    assert vault["factory_rules"]["candidate_artifacts_may_copy_protected_inputs"] is False
    assert vault["economic_rules"]["economic_activation_authority"] == "ThriveEvergreen / ECAC"


def validate_manifest(
    manifest: dict,
    contract: dict,
    machine: dict,
    vault: dict,
    continuous: dict,
    maintenance: dict,
) -> None:
    assert manifest["canonical_parent_repository"] == "crownthrive1/CrownThrive-OS"
    assert manifest["public_commercial_repository"] == "crownthrive/chlom-protocol"
    assert manifest["public_repository_role"] == "commercial_public_projection"
    assert manifest["architecture_id"] == "ct.architecture.pentafabric.v1"
    assert manifest["repository_visibility"] == {
        "parent": "public",
        "child": "public",
        "restricted_state_in_public_git": False,
    }
    assert manifest["os_identity"] == "CrownThrive OS"
    assert manifest["canonical_ledger"] == {
        "name": "DAIL",
        "expanded_name": "Decentralized Autonomous Information Ledger",
        "legacy_dal_is_canonical": False,
    }
    assert manifest["licensing_identity"]["DLA"] == "Dynamic Licensing Asset"
    assert manifest["commercialization"]["economic_activation_authority"] == "ThriveEvergreen / ECAC"
    assert manifest["authority"]["direct_main_write"] is False
    assert manifest["authority"]["force_push"] is False
    assert manifest["authority"]["self_merge"] is False
    assert manifest["authority"]["security_bypass"] is False
    assert manifest["security"]["allowlist_only"] is True
    assert manifest["security"]["raw_secret_export"] is False
    assert manifest["security"]["private_prompt_or_scoring_export"] is False
    assert manifest["projection"]["delete_unmanaged_child_paths"] is False
    assert manifest["projection"]["child_changes_require_pull_request"] is True
    assert manifest["projection"]["scheduled_continuity_enabled"] is True

    assert contract["parent_repository"] == manifest["canonical_parent_repository"]
    assert contract["child_repository"] == manifest["public_commercial_repository"]
    assert contract["relationship"] == "public_safe_canonical_governance_parent_to_public_commercial_child"
    assert contract["repository_visibility"] == {"parent": "public", "child": "public"}
    assert contract["restricted_state_location"] == "outside_public_git_vault_bounded"
    assert contract["source_authority"] == "parent"
    assert contract["rules"]["child_direct_main_write"] is False
    assert contract["rules"]["child_force_push"] is False
    assert contract["rules"]["secret_scan_required"] is True
    assert contract["rules"]["provider_success_is_institutional_truth"] is False
    assert contract["rights_model"]["commercial_use_requires_separate_license"] is True
    assert contract["economic_activation_authority"] == "ThriveEvergreen / ECAC"

    assert continuous["projection"]["parent"] == manifest["canonical_parent_repository"]
    assert continuous["projection"]["child"] == manifest["public_commercial_repository"]
    assert continuous["projection"]["child_pull_request_required"] is True
    assert continuous["economic_boundary"]["activation_authority"] == "ThriveEvergreen / ECAC"
    assert continuous["maintenance"]["current_state"] == maintenance["state"]
    assert continuous["maintenance"]["routine_autonomous_external_mutation_allowed"] == maintenance["autonomous_external_mutation_allowed"]
    assert continuous["vault"]["runtime_binding_state"] == vault["runtime_binding_state"]
    assert continuous["machine_interfaces"]["public_runtime_activation_inferred"] is False
    assert continuous["mesh"]["infrastructure_failover_certified"] is False


def source_files(manifest: dict) -> list[tuple[str, Path]]:
    source_root = ROOT / manifest["projection"]["source_root"]
    managed = manifest["projection"]["managed_paths"]
    assert managed == list(dict.fromkeys(managed)), "managed paths must be unique"
    files: list[tuple[str, Path]] = []
    for rel in managed:
        if rel in GENERATED_PATHS:
            continue
        candidate = (source_root / rel).resolve()
        assert source_root.resolve() in candidate.parents, f"managed path escapes source root: {rel}"
        assert candidate.is_file(), f"missing public-safe source: {rel}"
        files.append((rel, candidate))
    return files


def validate_public_text(files: list[tuple[str, Path]]) -> None:
    joined = []
    for rel, path in files:
        text = path.read_text(encoding="utf-8")
        joined.append(text)
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), f"credential-shaped material in {rel}"
        for phrase in FORBIDDEN_CURRENT_CANON:
            assert phrase not in text, f"legacy term asserted as current canon in {rel}: {phrase}"
        assert "CONFIDENTIAL_INTERNAL" not in text, f"internal marker in {rel}"
        assert "TRADE_SECRET_BODY" not in text, f"trade-secret marker in {rel}"

    all_text = "\n".join(joined)
    assert "private canonical parent" not in all_text.lower(), "stale private-parent claim in public projection"
    assert VERIFIED_SUPPORT_URL in all_text, "verified support route missing from managed projection"
    assert "CrownThrive Pentafabric" in all_text, "Pentafabric architecture missing from managed projection"
    assert "Decentralized Autonomous Information Ledger" in all_text
    assert "Dynamic Licensing Asset" in all_text


def write_dist(manifest: dict, files: list[tuple[str, Path]]) -> Path:
    dist_root = ROOT / manifest["projection"]["dist_root"]
    if dist_root.exists():
        shutil.rmtree(dist_root)
    dist_root.mkdir(parents=True, exist_ok=True)
    for rel, src in files:
        dst = dist_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    parent_sha = exact_parent_sha()
    provenance = {
        "schema_version": manifest["schema_version"],
        "product_id": manifest["product_id"],
        "architecture_id": manifest["architecture_id"],
        "canonical_parent_repository": manifest["canonical_parent_repository"],
        "upstream_parent_sha": parent_sha,
        "upstream_parent_commit_time": exact_parent_timestamp(parent_sha),
        "public_commercial_repository": manifest["public_commercial_repository"],
        "repository_role": manifest["public_repository_role"],
        "repository_visibility": manifest["repository_visibility"],
        "os_identity": manifest["os_identity"],
        "canonical_ledger": manifest["canonical_ledger"],
        "DLA": manifest["licensing_identity"]["DLA"],
        "economic_activation_authority": manifest["commercialization"]["economic_activation_authority"],
        "authority_mode": manifest["authority"]["recorded_mode"],
        "founder": manifest["authority"]["founder"],
        "receipt_is_certification": False,
        "receipt_creates_license": False,
        "receipt_creates_economic_authority": False,
    }
    receipt = dist_root / ".crownthrive/upstream.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return dist_root


def check_dist(manifest: dict, dist_root: Path) -> None:
    expected = set(manifest["projection"]["managed_paths"])
    actual = {
        path.relative_to(dist_root).as_posix()
        for path in dist_root.rglob("*")
        if path.is_file()
    }
    assert actual == expected, f"dist path mismatch: expected={sorted(expected)} actual={sorted(actual)}"
    receipt = load_json(dist_root / ".crownthrive/upstream.json")
    assert re.fullmatch(r"[0-9a-f]{40}", receipt["upstream_parent_sha"])
    assert receipt["architecture_id"] == "ct.architecture.pentafabric.v1"
    assert receipt["repository_visibility"]["parent"] == "public"
    assert receipt["repository_visibility"]["child"] == "public"
    assert receipt["repository_visibility"]["restricted_state_in_public_git"] is False
    assert receipt["canonical_ledger"]["name"] == "DAIL"
    assert receipt["DLA"] == "Dynamic Licensing Asset"
    assert receipt["economic_activation_authority"] == "ThriveEvergreen / ECAC"
    assert receipt["receipt_is_certification"] is False
    assert receipt["receipt_creates_license"] is False
    assert receipt["receipt_creates_economic_authority"] is False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="materialize dist/chlom-protocol")
    parser.add_argument("--check-dist", action="store_true", help="validate materialized output")
    args = parser.parse_args()

    manifest = load_json(MANIFEST_PATH)
    contract = load_json(CONTRACT_PATH)
    pentafabric = load_json(PENTAFABRIC_PATH)
    agent_pack = load_json(AGENT_CANDIDATES_PATH)
    api_mcp = load_json(API_MCP_CANDIDATES_PATH)
    asset_classes = load_json(ASSET_CLASSES_PATH)
    commercial_packages = load_json(COMMERCIAL_PACKAGES_PATH)
    mesh = load_json(MESH_PATH)
    maintenance = load_json(MAINTENANCE_PATH)
    machine = load_json(MACHINE_ACCESS_PATH)
    vault = load_json(VAULT_BOUNDARY_PATH)
    continuous = load_json(CONTINUOUS_BUILD_PATH)

    validate_pentafabric(pentafabric)
    validate_agent_pack(agent_pack)
    validate_extended_fabric(api_mcp, asset_classes, commercial_packages, mesh, maintenance, machine, vault)
    validate_manifest(manifest, contract, machine, vault, continuous, maintenance)
    files = source_files(manifest)
    validate_public_text(files)

    dist_root = ROOT / manifest["projection"]["dist_root"]
    if args.write:
        dist_root = write_dist(manifest, files)
    if args.check_dist:
        assert dist_root.is_dir(), "dist root not materialized"
        check_dist(manifest, dist_root)

    print("PASS_CHLOM_COMMERCIAL_PROJECTION")


if __name__ == "__main__":
    main()
