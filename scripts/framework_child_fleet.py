#!/usr/bin/env python3
"""Validate and render CrownThrive framework execution packages.

A framework child is an independently executable package (workflow, validator, engine,
skill, tools, API/MCP contracts, evals, federation and commercial manifest). A separate
physical GitHub repository is optional distribution packaging, not the child identity.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/framework-child-fleet.v1.json"
TEMPLATE_ROOT = ROOT / "developers/templates/framework-child-repository"

TEMPLATE_MAP = {
    "README.md.tmpl": "README.md",
    "AGENTS.md.tmpl": "AGENTS.md",
    "SECURITY.md.tmpl": "SECURITY.md",
    ".crownthrive/federation.json.tmpl": ".crownthrive/federation.json",
    "framework/manifest.json.tmpl": "framework/manifest.json",
    "engine/engine.py.tmpl": "engine/engine.py",
    "skills/framework/SKILL.md.tmpl": "skills/framework/SKILL.md",
    "tools/tools.v1.json.tmpl": "tools/tools.v1.json",
    "api/api-contract.v1.json.tmpl": "api/api-contract.v1.json",
    "mcp/mcp-tools.v1.json.tmpl": "mcp/mcp-tools.v1.json",
    "evals/evals.v1.json.tmpl": "evals/evals.v1.json",
    "commercial/offer-manifest.v1.json.tmpl": "commercial/offer-manifest.v1.json",
    ".github/CODEOWNERS.tmpl": ".github/CODEOWNERS",
    ".github/dependabot.yml.tmpl": ".github/dependabot.yml",
    ".github/pull_request_template.md.tmpl": ".github/pull_request_template.md",
    ".github/workflows/framework-child-bootstrap.yml.tmpl": ".github/workflows/framework-child-bootstrap.yml",
    ".github/workflows/framework-child-governance.yml.tmpl": ".github/workflows/framework-child-governance.yml",
    "scripts/federation_client.py.tmpl": "scripts/federation_client.py",
    "scripts/validate_child_repository.py.tmpl": "scripts/validate_child_repository.py",
}

EXPECTED_SEQUENCE = [
    "ct.framework.cultural-imprint-engine",
    "ct.framework.convergent-ecosystem",
    "ct.framework.thrive-flywheel",
    "ct.framework.chlom",
    "ct.framework.corridor-architecture",
    "ct.framework.hybrid-incubator",
    "ct.framework.mm-suites",
    "ct.framework.one-seat-multiple-industries",
]

IMPLEMENTED_STATES = {"CONTROLLED_TEST", "PARENT_CERTIFICATION_PENDING", "GOVERNED_FRAMEWORK_ACCEPTANCE", "PUBLIC_PACKAGE_CANDIDATE", "MAINTAINED"}
FORBIDDEN_TEMPLATE_FRAGMENTS = (
    "vote_eligible: true",
    '"vote_eligible": true',
    "SUPABASE_SERVICE_ROLE_KEY",
    "ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION",
    "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24",
)
PINNED_ACTIONS = (
    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
    "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path}: JSON object required")
    return value


def children(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("framework_children")
    if not isinstance(rows, list):
        fail("framework_children must be an array")
    return rows


def next_child(data: dict[str, Any]) -> dict[str, Any]:
    for row in children(data):
        if row.get("current_state") not in IMPLEMENTED_STATES:
            return row
    return children(data)[-1]


def validate_manifest(data: dict[str, Any]) -> None:
    if data.get("manifest_id") != "ct.manifest.framework-child-fleet.v1":
        fail("child fleet manifest identity drift")
    if data.get("manifest_version") != "2.0.0":
        fail("framework child fleet must use package-model v2")
    if data.get("program_authority_issue") != 148 or data.get("stacked_on_parent_pr") != 145:
        fail("factory authority/stack dependency drift")
    if data.get("canonical_parent_repository") != "crownthrive1/CrownThrive-Support":
        fail("canonical parent repository drift")
    if data.get("current_constitution") != "CT-ADR-GOV-011":
        fail("current constitution must remain CT-ADR-GOV-011")
    if data.get("child_definition") != "independently_executable_framework_package_not_physical_repository":
        fail("framework child definition drift")
    if data.get("provisioning_mode") != "one_at_a_time":
        fail("framework package implementation must remain one_at_a_time")

    host = data.get("host_model", {})
    if host.get("physical_child_repository_required") is not False:
        fail("physical child repository must not be required")
    if host.get("repository_identity_is_not_framework_identity") is not True:
        fail("repository identity must remain distinct from framework identity")

    inv = data.get("fleet_invariants", {})
    required_true = (
        "framework_package_is_primary_child_identity",
        "github_actions_oidc_required_for_federation_mutation",
        "pull_request_validation_must_not_receive_oidc_authority",
        "workflow_ref_environment_agent_capability_binding_required_before_mutation",
        "parent_certification_required_before_operational_or_public_activation",
        "agent_d_is_only_parent_certifier",
        "sovereign_vote_requires_separate_constitutional_acceptance",
        "sync_agents_only_non_voting_d0_d2_transport",
        "d3_human_reserved",
        "protected_calibration_public_copy_prohibited",
        "future_framework_activation_must_follow_sequence",
        "public_package_requires_ip_classification",
        "exact_price_checkout_entitlement_require_separate_authority",
        "package_controlled_test_is_not_child_certification",
        "sync_agents_cannot_satisfy_child_certification",
    )
    for key in required_true:
        if inv.get(key) is not True:
            fail(f"required fleet invariant missing: {key}")
    required_false = (
        "physical_repository_required_for_framework_existence",
        "physical_repository_required_for_controlled_test",
        "child_operational_before_oidc_and_parent_certification",
        "child_self_certification",
        "child_self_activation",
        "package_or_workflow_creates_sovereign_vote",
        "framework_acceptance_creates_sovereign_vote",
        "child_certification_creates_sovereign_vote",
    )
    for key in required_false:
        if inv.get(key) is not False:
            fail(f"fail-closed fleet invariant drift: {key}")

    required_true = (
        "physical_repository_required_for_linked_governed_certification",
        "physical_repository_required_for_parent_certification",
        "physical_repository_required_for_operational_activation",
        "physical_repository_required_for_sovereign_activation",
    )
    for key in required_true:
        if inv.get(key) is not True:
            fail(f"linked-governed certification invariant drift: {key}")

    rows = children(data)
    if len(rows) != 8:
        fail("initial framework package fleet must contain exactly eight frameworks")
    ids = [str(row.get("framework_id", "")) for row in rows]
    if ids != EXPECTED_SEQUENCE:
        fail(f"framework sequence drift: {ids}")

    package_ids: set[str] = set()
    minutes: set[int] = set()
    materialization_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        if row.get("order") != index:
            fail(f"framework order drift at {index}")
        package_id = str(row.get("package_id", ""))
        if not package_id.startswith("ct.framework-package.") or package_id in package_ids:
            fail(f"invalid or duplicate package_id: {package_id}")
        package_ids.add(package_id)
        if row.get("public_activation_allowed") is not False:
            fail(f"public activation must remain false in factory candidate manifest: {row.get('framework_id')}")
        minute = row.get("schedule_minute")
        if not isinstance(minute, int) or not (0 <= minute <= 59) or minute in minutes:
            fail(f"invalid/duplicate schedule minute for {package_id}")
        minutes.add(minute)
        expected_predecessor = None if index == 1 else rows[index - 2]["framework_id"]
        if row.get("predecessor_framework_id") != expected_predecessor:
            fail(f"predecessor drift for {row.get('framework_id')}")
        if row.get("package_materialization_allowed") is True:
            materialization_rows.append(row)
        if row.get("linked_governed_child_repository_required") is not True:
            fail(f"linked-governed child repository requirement missing: {package_id}")
        if row.get("framework_id") == EXPECTED_SEQUENCE[0]:
            if row.get("optional_repository_projection_state") != "physical_provisioned_pre_cert":
                fail("CIE physical repository projection must reflect observed pre-cert state")
            if row.get("linked_governed_child_repository_state") != "PROVISIONED_UNLINKED":
                fail("CIE child repository must remain provisioned_unlinked before certification")
            if row.get("linked_governed_child_repository_id") != "ct.repo.cie":
                fail("CIE stable child repository identity drift")
            if row.get("linked_governed_child_github_repository_id") != 1341314455:
                fail("CIE immutable GitHub repository ID drift")
            if row.get("linked_governed_child_repository_sha") != "073da74bb6eb1fde31b9a6d0321bb85baf5ac8fd":
                fail("CIE exact child repository SHA drift")
            if row.get("linked_governed_child_contract_sha256") != "2c88d166607f0f280a6024c31720b14767896ef8f7a67109eb9863943490630a":
                fail("CIE child contract digest drift")
            if row.get("parent_certification_state") != "PENDING_PRECERT_EVIDENCE_AND_GOVERNED_ACCEPTANCE":
                fail("CIE parent certification state drift")
        else:
            if row.get("optional_repository_projection_state") != "optional_not_required":
                fail(f"later framework repository projection state drift: {package_id}")
            if row.get("linked_governed_child_repository_state") != "UNPROVISIONED":
                fail(f"later uncertified package must remain UNPROVISIONED: {package_id}")
            if row.get("linked_governed_child_repository_id") is not None:
                fail(f"later child repository identity cannot be invented: {package_id}")
            if row.get("parent_certification_state") != "PENDING_PHYSICAL_CHILD":
                fail(f"later parent certification must remain pending physical child: {package_id}")

    if len(materialization_rows) != 1 or materialization_rows[0]["framework_id"] != EXPECTED_SEQUENCE[0]:
        fail("only CIE may be the current package-materialization implementation packet")
    if rows[1].get("scaffold_preview_allowed") is not True or rows[1].get("package_materialization_allowed") is not False:
        fail("Convergent must remain scaffold-preview-only")

    bundle = data.get("required_package_bundle", [])
    if bundle != list(TEMPLATE_MAP.values()):
        fail("required package bundle/template output mapping drift")

    sustain = data.get("self_sustain_contract", {})
    if sustain.get("github_hosted_runner") != "ubuntu-latest":
        fail("framework workflows must use approved literal ubuntu-latest runner")
    if sustain.get("federation_auth") != "github_actions_oidc":
        fail("framework federation authentication must remain GitHub Actions OIDC")
    if sustain.get("pr_validation_oidc") is not False:
        fail("pull request validation must not receive OIDC")
    for key in ("automatic_direct_to_main_repair", "automatic_merge", "automatic_sovereign_vote", "provider_or_customer_mutation", "secrets_in_git"):
        if sustain.get(key) is not False:
            fail(f"self-sustain fail-closed invariant drift: {key}")

    research = data.get("non_sequence_research_candidates", [])
    cii = next((item for item in research if item.get("framework_id") == "ct.framework.cii-thrivefund"), None)
    if not cii or cii.get("state") != "RESEARCH_CANDIDATE" or cii.get("evidence_maturity") != "implementation_backed":
        fail("CII/ThriveFund implementation-backed research-candidate boundary missing")


def template_files() -> list[Path]:
    output: list[Path] = []
    for rel in TEMPLATE_MAP:
        path = TEMPLATE_ROOT / rel
        if not path.is_file():
            fail(f"missing framework package template: {path.relative_to(ROOT)}")
        output.append(path)
    return output


def validate_templates() -> None:
    for path in template_files():
        text = path.read_text(encoding="utf-8")
        if path.name == "validate_child_repository.py.tmpl":
            continue
        for fragment in FORBIDDEN_TEMPLATE_FRAGMENTS:
            if fragment in text:
                fail(f"{path.relative_to(ROOT)} contains forbidden authority/secret fragment: {fragment}")
    governance = (TEMPLATE_ROOT / ".github/workflows/framework-child-governance.yml.tmpl").read_text(encoding="utf-8")
    bootstrap = (TEMPLATE_ROOT / ".github/workflows/framework-child-bootstrap.yml.tmpl").read_text(encoding="utf-8")
    workflow = governance + "\n" + bootstrap
    for pinned in PINNED_ACTIONS:
        if pinned not in workflow:
            fail(f"framework workflows missing pinned action reference: {pinned}")
    if "contents: write" in workflow or "pull-requests: write" in workflow:
        fail("framework templates may not direct-write contents or PRs")
    if "id-token: write" in governance.split("jobs:", 1)[0]:
        fail("governance workflow cannot grant OIDC at workflow scope")
    validate_segment = governance.split("  validate:", 1)[1].split("  federation-runtime:", 1)[0]
    if "id-token: write" in validate_segment:
        fail("pull-request validation job cannot receive OIDC")
    federation_segment = governance.split("  federation-runtime:", 1)[1]
    if "id-token: write" not in federation_segment or "github.event_name != 'pull_request'" not in federation_segment:
        fail("trusted federation runtime OIDC isolation missing")


def replacements(row: dict[str, Any], data: dict[str, Any]) -> dict[str, str]:
    parent_pr = row.get("parent_packet_pr")
    optional_repo = row.get("optional_repository_projection") or ""
    return {
        "{{FRAMEWORK_ID}}": str(row["framework_id"]),
        "{{CANONICAL_NAME}}": str(row["canonical_name"]),
        "{{FRAMEWORK_AGENT_ID}}": str(row["framework_agent_id"]),
        "{{PACKAGE_ID}}": str(row["package_id"]),
        "{{PACKAGE_STATE}}": str(row["current_state"]),
        "{{OPTIONAL_REPOSITORY_PROJECTION}}": str(optional_repo),
        "{{PARENT_REPOSITORY}}": str(data["canonical_parent_repository"]),
        "{{PARENT_PR}}": "null" if parent_pr is None else str(parent_pr),
        "{{SCHEDULE_MINUTE}}": str(row["schedule_minute"]),
        "{{RUNTIME_INTEGRATION_ALLOWED}}": "true" if row.get("runtime_integration_allowed") is True else "false",
        "{{PREDECESSOR_FRAMEWORK_ID}}": "" if row.get("predecessor_framework_id") is None else str(row["predecessor_framework_id"]),
        "{{REPO_ID}}": str(row["package_id"]),
        "{{REPO_FULL_NAME}}": str(optional_repo),
        "{{BOOTSTRAP_ALLOWED}}": "true" if row.get("runtime_integration_allowed") is True else "false",
    }


def render_framework(data: dict[str, Any], framework_id: str, output_dir: Path) -> None:
    row = next((item for item in children(data) if item.get("framework_id") == framework_id), None)
    if row is None:
        fail(f"framework not in authorized package fleet: {framework_id}")
    repl = replacements(row, data)
    for template_rel, output_rel in TEMPLATE_MAP.items():
        text = (TEMPLATE_ROOT / template_rel).read_text(encoding="utf-8")
        for key, value in repl.items():
            text = text.replace(key, value)
        unresolved = sorted(key for key in repl if key in text)
        if unresolved:
            fail(f"unresolved framework package placeholders in {template_rel}: {unresolved}")
        dst = output_dir / output_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")


def run_rendered_validator(root: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/validate_child_repository.py"), "--root", str(root)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        fail(f"rendered framework package validation failed:\n{proc.stdout}")


def self_test(data: dict[str, Any]) -> None:
    validate_manifest(data)
    validate_templates()
    cie = children(data)[0]
    convergent = children(data)[1]
    assert cie["framework_id"] == "ct.framework.cultural-imprint-engine"
    assert cie["package_materialization_allowed"] is True
    assert cie["current_state"] == "CONTROLLED_TEST"
    assert convergent["scaffold_preview_allowed"] is True
    assert convergent["package_materialization_allowed"] is False
    with tempfile.TemporaryDirectory(prefix="ct-framework-package-fleet-") as td:
        root = Path(td)
        for row in (cie, convergent):
            target = root / row["execution_slug"]
            render_framework(data, row["framework_id"], target)
            run_rendered_validator(target)
    print("Framework package fleet self-test PASS: CIE current controlled-test package, Convergent preview-only, package-only repo optional, linked-governed physical child required, PR OIDC isolated, non-voting/Agent-D/D3/IP/commercial locks preserved.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--render")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    data = load_json(MANIFEST)
    validate_manifest(data)
    validate_templates()

    if args.self_test:
        self_test(data)
    if args.next:
        row = next_child(data)
        print(json.dumps({
            "framework_id": row["framework_id"],
            "package_id": row["package_id"],
            "current_state": row["current_state"],
            "package_materialization_allowed": row.get("package_materialization_allowed", False),
            "scaffold_preview_allowed": row.get("scaffold_preview_allowed", False),
            "physical_repository_required_for_package_existence": False,
            "physical_repository_required_for_linked_governed_certification": True,
            "linked_governed_child_repository_state": row.get("linked_governed_child_repository_state"),
            "public_activation_allowed": False,
            "next_safe_action": "implement_next_governed_package_packet" if row.get("package_materialization_allowed") else "research_or_scaffold_preview_only",
        }, indent=2, sort_keys=True))
    if args.render:
        if not args.output_dir:
            parser.error("--output-dir is required with --render")
        render_framework(data, args.render, args.output_dir)
        print(f"Rendered {args.render} -> {args.output_dir}")
    if args.validate and not (args.self_test or args.next or args.render):
        print("Framework package fleet validation PASS")
    if not any((args.validate, args.self_test, args.next, args.render)):
        print("Framework package fleet validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
