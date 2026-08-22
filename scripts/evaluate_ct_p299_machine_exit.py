#!/usr/bin/env python3
"""Evaluate the CrownThrive CT-P299 machine hard exit.

Validation success means the evaluator ran deterministically and failed closed.
It does NOT mean Phase 2.99 passed. Use --require-go only for an explicit
bootstrap attempt after all required evidence exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "developers/manifests/ct-p299-machine-hard-exit.v1.json"
LEDGER = ROOT / "developers/manifests/phase-2-99-hard-exit-ledger.v1.json"
PHASE_NAMESPACE = ROOT / "developers/manifests/institutional-phase-namespace.v2.json"
AUTHORITY = ROOT / "governance/phase3-entry-authority-receipt.v1.json"
RECOVERY = ROOT / "governance/phase3-entry-recovery-receipt.v1.json"

TEXT_SUFFIXES = {".md", ".mdx", ".json", ".yaml", ".yml", ".txt"}
EXCLUDED_PARTS = {".git", "node_modules", "artifacts", "phase3-inputs", ".venv", "venv", "__pycache__"}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def current_head() -> str:
    value = git("rev-parse", "HEAD").lower()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("invalid_git_head")
    return value


def source_snapshot(contract: dict[str, Any]) -> dict[str, Any]:
    files = {}
    missing = []
    for rel in contract["canonical_sources"]:
        path = ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        files[rel] = sha256_bytes(path.read_bytes())
    snapshot = {
        "algorithm": "sha256-per-file-plus-canonical-json-v1",
        "files": files,
        "missing": missing,
    }
    snapshot["snapshot_sha256"] = sha256_json(snapshot)
    return snapshot


def docs_baseline() -> dict[str, Any]:
    entries = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        entries[str(rel)] = sha256_bytes(path.read_bytes())
    value = {
        "algorithm": "sha256-text-estate-canonical-map-v1",
        "file_count": len(entries),
        "files": entries,
    }
    return {
        "algorithm": value["algorithm"],
        "file_count": value["file_count"],
        "baseline_sha256": sha256_json(value),
    }


def github_main(repository: str, token: str | None, fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    if fixture is not None:
        return fixture
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/branches/main",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "CrownThrive-Phase3-Hard-Exit/1",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def validate_namespace(data: dict[str, Any]) -> list[str]:
    errors = []
    expected = {
        "decision_id": "CT-ADR-ROADMAP-010",
        "top_level_phase_count": 10,
        "current_phase": 2,
        "current_subphase": "2.99",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            errors.append(f"namespace_{key}_mismatch")
    if data.get("phase_3_entry") not in {"blocked_pending_phase_2_99_hard_exit", "go_eligible", "phase3_active"}:
        errors.append("namespace_phase3_state_invalid")
    return errors


def validate_authority(data: dict[str, Any], head: str, source_sha: str) -> tuple[bool, list[str]]:
    reasons = []
    if data.get("state") != "VERIFIED":
        reasons.append("authority_receipt_not_verified")
    if data.get("exact_head_sha") != head:
        reasons.append("authority_receipt_head_mismatch")
    if data.get("source_snapshot_sha256") != source_sha:
        reasons.append("authority_receipt_source_snapshot_mismatch")
    for key in ("agent_a", "independent_audit", "security", "agent_d"):
        if data.get(key) != "PASS":
            reasons.append(f"{key}_not_pass")
    gov = data.get("sovereign_governance", {})
    approvals = set(gov.get("approvals") or [])
    denials = set(gov.get("denials") or [])
    blocks = set(gov.get("blocks") or [])
    if len(approvals) < int(gov.get("minimum_approvals", 4)):
        reasons.append("sovereign_quorum_not_met")
    if "D" not in approvals or gov.get("agent_d_approved") is not True:
        reasons.append("agent_d_mandatory_approval_missing")
    if denials:
        reasons.append("sovereign_denial_present")
    if blocks:
        reasons.append("sovereign_block_present")
    if data.get("originator_self_approval") is not False:
        reasons.append("originator_self_approval_prohibited")
    return not reasons, reasons


def validate_recovery(data: dict[str, Any], head: str) -> tuple[bool, list[str]]:
    reasons = []
    if data.get("state") != "VERIFIED":
        reasons.append("recovery_receipt_not_verified")
    if data.get("exact_head_sha") != head:
        reasons.append("recovery_receipt_head_mismatch")
    for key in ("backup_verified", "restore_tested", "rollback_tested", "off_provider_copy_verified", "exact_readback_verified"):
        if data.get(key) is not True:
            reasons.append(f"{key}_not_verified")
    return not reasons, reasons


def parse_thivebase(path: Path | None) -> tuple[bool, dict[str, Any], list[str]]:
    if path is None or not path.exists():
        return False, {}, ["thivebase_snapshot_missing"]
    try:
        data = load_json(path)
    except Exception:
        return False, {}, ["thivebase_snapshot_invalid_json"]
    reasons = []
    if data.get("ok") is not True:
        reasons.append("thivebase_snapshot_not_ok")
    digest = str(data.get("snapshot_sha256") or "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        reasons.append("thivebase_snapshot_digest_invalid")
    side = data.get("snapshot", {}).get("side_effects", {})
    for key in ("database_mutation", "commerce_activation", "money_movement", "phase_transition", "sovereign_vote_effect"):
        if side.get(key) is not False:
            reasons.append(f"thivebase_snapshot_{key}_must_be_false")
    return not reasons, data, reasons


def evaluate(github_branch: dict[str, Any], thivebase_path: Path | None) -> dict[str, Any]:
    contract = load_json(CONTRACT)
    ledger = load_json(LEDGER)
    namespace = load_json(PHASE_NAMESPACE)
    authority = load_json(AUTHORITY)
    recovery = load_json(RECOVERY)

    head = current_head()
    sources = source_snapshot(contract)
    docs = docs_baseline()
    namespace_errors = validate_namespace(namespace)

    gate_rows = ledger.get("open_hard_gates", [])
    required_ids = set(contract["hard_exit_gate_policy"]["required_gate_ids"])
    by_id = {row.get("gate_id"): row for row in gate_rows}
    gate_registry_complete = set(by_id) == required_ids
    blockers_evaluated = gate_registry_complete and all(row.get("state") is not None for row in gate_rows)

    no_go: list[str] = []
    holds: list[str] = []

    if not gate_registry_complete:
        no_go.append("hard_exit_gate_registry_incomplete")
    for gate_id in sorted(required_ids):
        row = by_id.get(gate_id)
        if not row:
            continue
        state = row.get("state")
        allowed = {"pass"}
        if row.get("deferral_permitted") is True:
            allowed.add("deferred_accepted")
        if state not in allowed:
            no_go.append(f"{gate_id}:{state}")

    branch_protected = github_branch.get("protected") is True
    protection_enabled = github_branch.get("protection", {}).get("enabled") is True
    enforcement = github_branch.get("protection", {}).get("required_status_checks", {}).get("enforcement_level")
    required_enforced = enforcement in {"non_admins", "everyone"}
    if not (branch_protected and protection_enabled and required_enforced):
        no_go.append("CT-P299-GATE-004:live_main_merge_governance_not_fail_closed")

    actual_main_sha = str(github_branch.get("commit", {}).get("sha") or "").lower()
    if len(actual_main_sha) != 40:
        no_go.append("github_main_sha_unavailable")
    if ledger.get("observed_main_sha") != actual_main_sha:
        holds.append("static_hard_exit_ledger_stale_to_current_main")

    thivebase_ok, thivebase, thivebase_reasons = parse_thivebase(thivebase_path)
    if not thivebase_ok:
        holds.extend(thivebase_reasons)

    authority_ok, authority_reasons = validate_authority(authority, head, sources["snapshot_sha256"])
    if not authority_ok:
        holds.extend(authority_reasons)

    recovery_ok, recovery_reasons = validate_recovery(recovery, head)
    if not recovery_ok:
        holds.extend(recovery_reasons)

    if sources["missing"]:
        no_go.append("canonical_source_snapshot_incomplete")
    if namespace_errors:
        no_go.extend(namespace_errors)

    freezes = {
        "all_blockers_evaluated": blockers_evaluated,
        "absolute_no_go_zero": len(no_go) == 0,
        "exact_source_snapshot_frozen": not sources["missing"],
        "exact_git_sha_frozen": len(head) == 40,
        "exact_thivebase_snapshot_frozen": thivebase_ok,
        "docs_baseline_frozen": docs["file_count"] > 0,
        "authority_quorum_verified": authority_ok,
        "backup_rollback_receipt_verified": recovery_ok,
    }

    if no_go:
        verdict = "NO_GO"
    elif not all(freezes.values()):
        verdict = "HOLD"
    else:
        verdict = "GO"

    result = {
        "schema_version": "1.0.0",
        "evaluation_id": "ct.evaluation.p299-hard-exit.v1",
        "contract_id": contract["contract_id"],
        "verdict": verdict,
        "phase3_activation_state": "NOT_ACTIVE" if verdict != "GO" else "GO_ELIGIBLE_BOOTSTRAP_NOT_COMMITTED",
        "exact_git_sha": head,
        "current_main_sha": actual_main_sha,
        "source_snapshot": sources,
        "docs_baseline": docs,
        "thivebase_snapshot_sha256": thivebase.get("snapshot_sha256"),
        "freezes": freezes,
        "absolute_no_go_conditions": sorted(set(no_go)),
        "holds": sorted(set(holds)),
        "live_main_governance": {
            "protected": branch_protected,
            "protection_enabled": protection_enabled,
            "required_status_enforcement": enforcement,
            "pass": branch_protected and protection_enabled and required_enforced,
        },
        "bootstrap_permitted": verdict == "GO",
        "phase3_active": False,
    }
    result["evaluation_sha256"] = sha256_json(result)
    return result


def bootstrap_packet(evaluation: dict[str, Any]) -> dict[str, Any]:
    if evaluation.get("verdict") != "GO":
        raise ValueError("phase3_bootstrap_requires_GO")
    packet = {
        "schema_version": "1.0.0",
        "bootstrap_id": "CT-PHASE3-BOOTSTRAP-v1",
        "state": "GO_ELIGIBLE_BOOTSTRAP_NOT_COMMITTED",
        "exact_git_sha": evaluation["exact_git_sha"],
        "evaluation_sha256": evaluation["evaluation_sha256"],
        "source_snapshot_sha256": evaluation["source_snapshot"]["snapshot_sha256"],
        "docs_baseline_sha256": evaluation["docs_baseline"]["baseline_sha256"],
        "thivebase_snapshot_sha256": evaluation["thivebase_snapshot_sha256"],
        "dail_event": {
            "event_type": "phase_transition_candidate",
            "from": "2.99",
            "to": "3.0",
            "state": "CANDIDATE_NOT_PERSISTED"
        },
        "required_commit_effects": {
            "dail_event_persisted_and_read_back": false,
            "thivebase_baseline_persisted_and_read_back": false,
            "git_tag_release_created_and_read_back": false,
            "mintlify_changelog_published_and_read_back": false,
            "rollback_snapshot_bound_and_read_back": false
        },
        "phase3_active": false,
        "rule": "Phase 3 becomes active only after every required commit effect reads back true under the same exact evaluation."
    }
    packet["bootstrap_sha256"] = sha256_json(packet)
    return packet


def self_test() -> None:
    assert sha256_json({"b": 2, "a": 1}) == sha256_json({"a": 1, "b": 2})
    head = "a" * 40
    good_authority = {
        "state": "VERIFIED",
        "exact_head_sha": head,
        "source_snapshot_sha256": "b" * 64,
        "agent_a": "PASS",
        "independent_audit": "PASS",
        "security": "PASS",
        "agent_d": "PASS",
        "sovereign_governance": {
            "minimum_approvals": 4,
            "approvals": ["A", "B", "D", "S"],
            "denials": [],
            "blocks": [],
            "agent_d_approved": true
        },
        "originator_self_approval": false
    }
    ok, reasons = validate_authority(good_authority, head, "b" * 64)
    assert ok and not reasons
    bad = json.loads(json.dumps(good_authority))
    bad["sovereign_governance"]["approvals"] = ["A", "B", "C", "S"]
    ok, reasons = validate_authority(bad, head, "b" * 64)
    assert not ok and "agent_d_mandatory_approval_missing" in reasons
    recovery = {
        "state": "VERIFIED",
        "exact_head_sha": head,
        "backup_verified": true,
        "restore_tested": true,
        "rollback_tested": true,
        "off_provider_copy_verified": true,
        "exact_readback_verified": true
    }
    ok, reasons = validate_recovery(recovery, head)
    assert ok and not reasons
    try:
        bootstrap_packet({"verdict": "HOLD"})
    except ValueError:
        pass
    else:
        raise AssertionError("bootstrap must reject non-GO")
    print("PASS_CT_P299_MACHINE_HARD_EXIT_SELF_TEST")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--thivebase-snapshot", type=Path)
    p.add_argument("--output", type=Path, default=Path("artifacts/ct-p299-hard-exit-evaluation.json"))
    p.add_argument("--emit-bootstrap", type=Path)
    p.add_argument("--require-go", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    repository = os.getenv("CT_REPOSITORY", "crownthrive1/CrownThrive-Support")
    token = os.getenv("GITHUB_TOKEN")
    try:
        branch = github_main(repository, token)
    except Exception as exc:
        branch = {
            "protected": False,
            "protection": {"enabled": False, "required_status_checks": {"enforcement_level": "unknown"}},
            "commit": {"sha": ""},
            "observation_error": type(exc).__name__
        }

    result = evaluate(branch, args.thivebase_snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(result))
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.emit_bootstrap:
        packet = bootstrap_packet(result)
        args.emit_bootstrap.parent.mkdir(parents=True, exist_ok=True)
        args.emit_bootstrap.write_bytes(canonical_bytes(packet))

    if args.require_go and result["verdict"] != "GO":
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
