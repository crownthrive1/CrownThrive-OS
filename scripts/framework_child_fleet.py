#!/usr/bin/env python3
"""Validate and render CrownThrive framework child repository scaffolds.

This is a provisioning/scaffold controller. It cannot create GitHub repositories,
certify children, activate sovereign voters, or bypass predecessor gates.
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

TERMINAL_LINKED = {"LINKED_GOVERNED", "CONTROLLED_TEST", "MAINTAINED"}
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
    rows = children(data)
    for row in rows:
        if row.get("current_state") not in TERMINAL_LINKED:
            return row
    return rows[-1]


def validate_manifest(data: dict[str, Any]) -> None:
    if data.get("manifest_id") != "ct.manifest.framework-child-fleet.v1":
        fail("child fleet manifest identity drift")
    if data.get("program_authority_issue") != 148 or data.get("stacked_on_parent_pr") != 145:
        fail("factory authority/stack dependency drift")
    if data.get("canonical_parent_repository") != "crownthrive1/CrownThrive-Support":
        fail("canonical parent repository drift")
    if data.get("current_constitution") != "CT-ADR-GOV-011":
        fail("current constitution must remain CT-ADR-GOV-011")
    if data.get("provisioning_mode") != "one_at_a_time":
        fail("framework child provisioning must remain one_at_a_time")

    inv = data.get("fleet_invariants", {})
    required_true = (
        "repository_name_is_not_existence_evidence",
        "physical_repository_id_required_before_bootstrap",
        "github_actions_oidc_required",
        "parent_certification_required",
        "agent_d_is_only_parent_certifier",
        "sovereign_vote_requires_separate_constitutional_acceptance",
        "sync_agents_only_non_voting_d0_d2_transport",
        "d3_human_reserved",
        "protected_calibration_public_copy_prohibited",
        "future_framework_activation_must_follow_sequence",
    )
    for key in required_true:
        if inv.get(key) is not True:
            fail(f"required fleet invariant missing: {key}")
    required_false = (
        "child_operational_before_oidc_and_parent_certification",
        "child_self_certification",
        "child_self_activation",
        "repository_or_workflow_creates_sovereign_vote",
        "framework_acceptance_creates_sovereign_vote",
        "child_certification_creates_sovereign_vote",
    )
    for key in required_false:
        if inv.get(key) is not False:
            fail(f"fail-closed fleet invariant drift: {key}")

    rows = children(data)
    if len(rows) != 8:
        fail("initial framework child fleet must contain exactly eight repositories")
    ids = [str(row.get("framework_id", "")) for row in rows]
    if ids != EXPECTED_SEQUENCE:
        fail(f"framework sequence drift: {ids}")

    repo_ids: set[str] = set()
    repo_names: set[str] = set()
    minutes: set[int] = set()
    bootstrap_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        if row.get("order") != index:
            fail(f"framework order drift at {index}")
        if row.get("activation_allowed") is not False:
            fail(f"activation must remain false in provisioning manifest: {row.get('framework_id')}")
        repo_id = str(row.get("repo_id", ""))
        repo_name = str(row.get("repo_full_name", ""))
        if not repo_id.startswith("ct.repo.") or repo_id in repo_ids:
            fail(f"invalid or duplicate repo_id: {repo_id}")
        if not repo_name.startswith("crownthrive1/CrownThrive-") or repo_name in repo_names:
            fail(f"invalid or duplicate repo_full_name: {repo_name}")
        repo_ids.add(repo_id)
        repo_names.add(repo_name)
        minute = row.get("schedule_minute")
        if not isinstance(minute, int) or not (0 <= minute <= 59) or minute in minutes:
            fail(f"invalid/duplicate schedule minute for {repo_id}")
        minutes.add(minute)

        predecessor = row.get("predecessor_framework_id")
        expected_predecessor = None if index == 1 else rows[index - 2]["framework_id"]
        if predecessor != expected_predecessor:
            fail(f"predecessor drift for {row.get('framework_id')}")
        if row.get("bootstrap_allowed") is True:
            bootstrap_rows.append(row)

        physical_id = row.get("physical_repository_id")
        if physical_id is not None and (not isinstance(physical_id, int) or physical_id <= 0):
            fail(f"physical_repository_id must be null or positive integer: {repo_id}")
        if row.get("current_state") == "PLANNED" and physical_id is not None:
            fail(f"planned repository cannot already carry a physical repository id: {repo_id}")

    if len(bootstrap_rows) > 1:
        fail("only one child repository may have bootstrap_allowed=true")
    expected_next = next_child(data)
    if bootstrap_rows and bootstrap_rows[0]["framework_id"] != expected_next["framework_id"]:
        fail("bootstrap eligibility must point at the first non-linked framework child")

    bundle = data.get("bootstrap_bundle", [])
    if bundle != list(TEMPLATE_MAP.values()):
        fail("bootstrap bundle/template output mapping drift")

    sustain = data.get("self_sustain_contract", {})
    if sustain.get("github_hosted_runner") != "ubuntu-latest":
        fail("child workflows must use approved literal ubuntu-latest runner")
    if sustain.get("bootstrap_auth") != "github_actions_oidc":
        fail("child bootstrap authentication must remain GitHub Actions OIDC")
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
            fail(f"missing child repository template: {path.relative_to(ROOT)}")
        output.append(path)
    return output


def validate_templates() -> None:
    for path in template_files():
        text = path.read_text(encoding="utf-8")
        if path.name == "validate_child_repository.py.tmpl":
            continue
        for fragment in FORBIDDEN_TEMPLATE_FRAGMENTS:
            if fragment in text:
                fail(f"{path.relative_to(ROOT)} contains forbidden child authority/secret fragment: {fragment}")
    workflow_text = "\n".join(
        (TEMPLATE_ROOT / rel).read_text(encoding="utf-8")
        for rel in (
            ".github/workflows/framework-child-bootstrap.yml.tmpl",
            ".github/workflows/framework-child-governance.yml.tmpl",
        )
    )
    for pinned in PINNED_ACTIONS:
        if pinned not in workflow_text:
            fail(f"child workflows missing pinned action reference: {pinned}")
    if "contents: write" in workflow_text or "pull-requests: write" in workflow_text:
        fail("child governance templates may not direct-write contents or PRs")
    if "id-token: write" not in workflow_text:
        fail("child OIDC workflows must request id-token: write")


def replacements(row: dict[str, Any], data: dict[str, Any]) -> dict[str, str]:
    parent_pr = row.get("parent_packet_pr")
    return {
        "{{FRAMEWORK_ID}}": str(row["framework_id"]),
        "{{CANONICAL_NAME}}": str(row["canonical_name"]),
        "{{FRAMEWORK_AGENT_ID}}": str(row["framework_agent_id"]),
        "{{REPO_ID}}": str(row["repo_id"]),
        "{{REPO_FULL_NAME}}": str(row["repo_full_name"]),
        "{{PARENT_REPOSITORY}}": str(data["canonical_parent_repository"]),
        "{{PARENT_PR}}": "null" if parent_pr is None else str(parent_pr),
        "{{SCHEDULE_MINUTE}}": str(row["schedule_minute"]),
        "{{BOOTSTRAP_ALLOWED}}": "true" if row.get("bootstrap_allowed") is True else "false",
        "{{PREDECESSOR_FRAMEWORK_ID}}": "" if row.get("predecessor_framework_id") is None else str(row["predecessor_framework_id"]),
    }


def render_framework(data: dict[str, Any], framework_id: str, output_dir: Path) -> None:
    row = next((item for item in children(data) if item.get("framework_id") == framework_id), None)
    if row is None:
        fail(f"framework not in authorized child fleet: {framework_id}")
    repl = replacements(row, data)
    for template_rel, output_rel in TEMPLATE_MAP.items():
        src = TEMPLATE_ROOT / template_rel
        text = src.read_text(encoding="utf-8")
        for key, value in repl.items():
            text = text.replace(key, value)
        unresolved = sorted(set(part for part in text.split() if part.startswith("{{") and part.endswith("}}")))
        if unresolved:
            fail(f"unresolved child template placeholders in {template_rel}: {unresolved}")
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
        fail(f"rendered child validation failed:\n{proc.stdout}")


def self_test(data: dict[str, Any]) -> None:
    validate_manifest(data)
    validate_templates()
    nxt = next_child(data)
    assert nxt["framework_id"] == "ct.framework.cultural-imprint-engine"
    assert nxt["bootstrap_allowed"] is True
    assert children(data)[1]["bootstrap_allowed"] is False
    assert children(data)[1]["predecessor_framework_id"] == "ct.framework.cultural-imprint-engine"
    with tempfile.TemporaryDirectory(prefix="ct-framework-child-fleet-") as td:
        root = Path(td)
        for fid in (EXPECTED_SEQUENCE[0], EXPECTED_SEQUENCE[1]):
            target = root / fid.rsplit(".", 1)[-1]
            render_framework(data, fid, target)
            run_rendered_validator(target)
    print(
        "Framework child fleet self-test PASS: one-at-a-time bootstrap, CIE current, "
        "Convergent scaffold-only, non-voting/OIDC/Agent-D/D3 boundaries preserved."
    )


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
            "repo_full_name": row["repo_full_name"],
            "current_state": row["current_state"],
            "bootstrap_allowed": row["bootstrap_allowed"],
            "activation_allowed": False,
            "physical_repository_id": row["physical_repository_id"],
            "provider_visibility": row["provider_visibility"],
            "next_safe_action": "discover_physical_repository_then_stage_oidc_bootstrap" if row["bootstrap_allowed"] else "hold",
        }, indent=2, sort_keys=True))
    if args.render:
        if not args.output_dir:
            parser.error("--output-dir is required with --render")
        render_framework(data, args.render, args.output_dir)
        print(f"Rendered {args.render} -> {args.output_dir}")
    if args.validate and not (args.self_test or args.next or args.render):
        print("Framework child fleet validation PASS")
    if not any((args.validate, args.self_test, args.next, args.render)):
        print("Framework child fleet validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
