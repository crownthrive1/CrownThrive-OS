#!/usr/bin/env python3
"""CT-P299 Phase 3 hard-exit evaluator v2.

The evaluator is fail-closed, exact-head bound, and forward-oriented. The legacy
A/B/C/D/S external-scheduler quorum and the August 19 static hard-exit ledger are
preserved as historical governance evidence, but current Phase 3 eligibility is
computed from the live ThriveBase production software fabric.

A GO is eligibility to bootstrap Phase 3. It is not Phase 3 activation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
P = lambda x: ROOT / x
CONTRACT = P("developers/manifests/ct-p299-machine-hard-exit.v1.json")
NAMESPACE = P("developers/manifests/institutional-phase-namespace.v2.json")
TEXT = {".md", ".mdx", ".json", ".yaml", ".yml", ".txt"}
SKIP = {".git", "node_modules", "artifacts", "phase3-inputs", ".venv", "venv", "__pycache__"}


def cbytes(v: Any) -> bytes:
    return (json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def hbytes(v: bytes) -> str:
    return hashlib.sha256(v).hexdigest()


def hjson(v: Any) -> str:
    return hbytes(cbytes(v))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip().lower()


def source_snapshot(contract: dict[str, Any]) -> dict[str, Any]:
    files: dict[str, str] = {}
    missing: list[str] = []
    for rel in contract["canonical_sources"]:
        path = P(rel)
        if path.is_file():
            files[rel] = hbytes(path.read_bytes())
        else:
            missing.append(rel)
    out: dict[str, Any] = {
        "algorithm": "sha256-per-file-plus-canonical-json-v2",
        "files": files,
        "missing": missing,
    }
    out["snapshot_sha256"] = hjson(out)
    return out


def docs_baseline() -> dict[str, Any]:
    entries: dict[str, str] = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT:
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP for part in rel.parts):
            continue
        entries[str(rel)] = hbytes(path.read_bytes())
    basis = {"algorithm": "sha256-text-estate-canonical-map-v2", "files": entries}
    return {
        "algorithm": basis["algorithm"],
        "file_count": len(entries),
        "baseline_sha256": hjson(basis),
    }


def github_main(repo: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "CrownThrive-Phase3-Hard-Exit/2",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/branches/main", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def thivebase(path: Path | None, git_head: str) -> tuple[bool, dict[str, Any], list[str]]:
    if not path or not path.exists():
        return False, {}, ["thivebase_snapshot_missing"]
    try:
        d = load(path)
    except Exception:
        return False, {}, ["thivebase_snapshot_invalid_json"]

    why: list[str] = []
    if d.get("ok") is not True:
        why.append("thivebase_snapshot_not_ok")
    digest = str(d.get("snapshot_sha256") or "").lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        why.append("thivebase_snapshot_digest_invalid")

    snap = d.get("snapshot", {})
    if str(snap.get("source_head_sha") or "").lower() != git_head:
        why.append("thivebase_snapshot_exact_head_mismatch")

    thive = snap.get("thivebase", {})
    if thive.get("required_reads_complete") is not True:
        why.append("thivebase_required_reads_incomplete")
    for rail in ("chlom_gen6", "commercial_release_factory"):
        if thive.get(rail, {}).get("ok") is not True:
            why.append(f"thivebase_{rail}_read_not_ok")

    live_wrapper = thive.get("phase3_live_gate", {})
    if live_wrapper.get("ok") is not True:
        why.append("phase3_live_gate_read_not_ok")
        live = {}
    else:
        live = live_wrapper.get("data") or {}
    if thive.get("phase3_live_gate_exact_head_bound") is not True:
        why.append("phase3_live_gate_not_exact_head_bound")
    if str(live.get("source_head_sha") or "").lower() != git_head:
        why.append("phase3_live_gate_source_head_mismatch")
    if live.get("gate_count") != 8:
        why.append("phase3_live_gate_registry_incomplete")
    if live.get("blocker_count") != 0:
        why.append("phase3_live_gate_blockers_present")
    if live.get("verdict") != "GO":
        why.append("phase3_live_gate_not_go")
    if live.get("phase3_activation_state") != "GO_ELIGIBLE_BOOTSTRAP_NOT_COMMITTED":
        why.append("phase3_live_gate_activation_state_invalid")

    gates_value = live.get("gates") if isinstance(live, dict) else None
    gates = gates_value if isinstance(gates_value, dict) else {}
    if not isinstance(gates_value, dict):
        why.append("phase3_live_gate_gates_invalid")
    required = {f"CT-P299-GATE-{i:03d}" for i in range(1, 9)}
    if set(gates) != required:
        why.append("phase3_live_gate_ids_incomplete")
    allowed = {"pass", "deferred_accepted"}
    for gate_id in sorted(required):
        if gates.get(gate_id, {}).get("state") not in allowed:
            why.append(f"{gate_id}:not_accepted")

    if live.get("legacy_ABCDS_scheduler_quorum") != "SUPERSEDED_BY_THRIVEBASE_PRODUCTION_SOFTWARE_FABRIC":
        why.append("legacy_agent_scheduler_topology_not_superseded")

    side = snap.get("side_effects", {})
    for k in (
        "database_mutation",
        "commerce_activation",
        "money_movement",
        "phase_transition",
        "sovereign_vote_effect",
    ):
        if side.get(k) is not False:
            why.append(f"thivebase_snapshot_{k}_must_be_false")

    return not why, d, why


def evaluate(branch: dict[str, Any], snapshot_path: Path | None) -> dict[str, Any]:
    contract = load(CONTRACT)
    ns = load(NAMESPACE)
    git_head = head()
    sources = source_snapshot(contract)
    docs = docs_baseline()
    no_go: list[str] = []
    holds: list[str] = []

    for k, v in {
        "decision_id": "CT-ADR-ROADMAP-010",
        "top_level_phase_count": 10,
        "current_phase": 2,
        "current_subphase": "2.99",
    }.items():
        if ns.get(k) != v:
            no_go.append(f"namespace_{k}_mismatch")

    if sources["missing"]:
        no_go.append("canonical_source_snapshot_incomplete")

    tb_ok, tb, tb_why = thivebase(snapshot_path, git_head)
    if tb_why:
        no_go.extend(tb_why)

    snap = tb.get("snapshot", {}) if tb else {}
    live = snap.get("thivebase", {}).get("phase3_live_gate", {}).get("data", {}) if snap else {}
    gates_value = live.get("gates") if isinstance(live, dict) else None
    gates = gates_value if isinstance(gates_value, dict) else {}

    remote_main_sha = str(branch.get("commit", {}).get("sha") or "").lower()
    snapshot_main_sha = str(snap.get("github_main", {}).get("sha") or "").lower()
    main_sha = remote_main_sha if len(remote_main_sha) == 40 else snapshot_main_sha
    if len(main_sha) != 40:
        holds.append("github_main_sha_unavailable")
    exact_head_is_current_main = main_sha == git_head
    if not exact_head_is_current_main:
        holds.append("exact_head_not_current_main_bootstrap_not_permitted")

    protected = branch.get("protected") is True
    enabled = branch.get("protection", {}).get("enabled") is True
    enforcement = branch.get("protection", {}).get("required_status_checks", {}).get("enforcement_level")
    founder_override = gates.get("CT-P299-GATE-004", {}).get("state") == "deferred_accepted"
    governance_accepted = (protected and enabled and enforcement in {"non_admins", "everyone"}) or founder_override
    if not governance_accepted:
        no_go.append("CT-P299-GATE-004:repository_governance_not_accepted")

    production_fabric_attestation = gates.get("CT-P299-GATE-008", {}).get("state") == "pass"
    recovery_continuity = gates.get("CT-P299-GATE-007", {}).get("state") in {"pass", "deferred_accepted"}
    all_blockers_evaluated = len(gates) == 8 and all(
        g.get("state") in {"pass", "deferred_accepted"} for g in gates.values()
    )

    freezes = {
        "all_blockers_evaluated": all_blockers_evaluated,
        "absolute_no_go_zero": not no_go,
        "exact_source_snapshot_frozen": not sources["missing"],
        "exact_git_sha_frozen": len(git_head) == 40,
        "exact_head_is_current_main": exact_head_is_current_main,
        "exact_thivebase_snapshot_frozen": tb_ok,
        "docs_baseline_frozen": docs["file_count"] > 0,
        "production_fabric_attestation_verified": production_fabric_attestation,
        "recovery_continuity_accepted": recovery_continuity,
    }

    verdict = "NO_GO" if no_go else ("HOLD" if not all(freezes.values()) else "GO")
    out: dict[str, Any] = {
        "schema_version": "2.0.0",
        "evaluation_id": "ct.evaluation.p299-hard-exit.v2",
        "contract_id": contract["contract_id"],
        "verdict": verdict,
        "phase3_activation_state": "GO_ELIGIBLE_BOOTSTRAP_NOT_COMMITTED" if verdict == "GO" else "NOT_ACTIVE",
        "exact_git_sha": git_head,
        "current_main_sha": main_sha,
        "source_snapshot": sources,
        "docs_baseline": docs,
        "thivebase_snapshot_sha256": tb.get("snapshot_sha256") if tb else None,
        "thivebase_live_gate_evaluation_id": live.get("evaluation_id") if isinstance(live, dict) else None,
        "thivebase_live_gate": live,
        "freezes": freezes,
        "absolute_no_go_conditions": sorted(set(no_go)),
        "holds": sorted(set(holds)),
        "live_main_governance": {
            "protected": protected,
            "protection_enabled": enabled,
            "required_status_enforcement": enforcement,
            "founder_override_accepted": founder_override,
            "accepted": governance_accepted,
            "truth_rule": "Founder override never rewrites GitHub's observed protection state.",
        },
        "topology": {
            "legacy_ABCDS_scheduler_quorum": "SUPERSEDED_BY_THRIVEBASE_PRODUCTION_SOFTWARE_FABRIC",
            "current_authority": "ThriveBase production software fabric plus exact-head receipts",
        },
        "bootstrap_permitted": verdict == "GO",
        "phase3_active": False,
    }
    out["evaluation_sha256"] = hjson(out)
    return out


def bootstrap(e: dict[str, Any]) -> dict[str, Any]:
    if e.get("verdict") != "GO":
        raise ValueError("phase3_bootstrap_requires_GO")
    if e.get("exact_git_sha") != e.get("current_main_sha"):
        raise ValueError("phase3_bootstrap_requires_exact_current_main")
    p: dict[str, Any] = {
        "schema_version": "2.0.0",
        "bootstrap_id": "CT-PHASE3-BOOTSTRAP-v2",
        "state": "GO_ELIGIBLE_BOOTSTRAP_NOT_COMMITTED",
        "exact_git_sha": e["exact_git_sha"],
        "evaluation_sha256": e["evaluation_sha256"],
        "source_snapshot_sha256": e["source_snapshot"]["snapshot_sha256"],
        "docs_baseline_sha256": e["docs_baseline"]["baseline_sha256"],
        "thivebase_snapshot_sha256": e["thivebase_snapshot_sha256"],
        "thivebase_live_gate_evaluation_id": e.get("thivebase_live_gate_evaluation_id"),
        "dail_event": {
            "event_type": "phase_transition_candidate",
            "from": "2.99",
            "to": "3.0",
            "state": "CANDIDATE_NOT_PERSISTED",
        },
        "required_commit_effects": {
            "dail_event_persisted_and_read_back": False,
            "thivebase_baseline_persisted_and_read_back": False,
            "git_tag_release_created_and_read_back": False,
            "mintlify_changelog_published_and_read_back": False,
            "rollback_snapshot_bound_and_read_back": False,
        },
        "phase3_active": False,
        "rule": "Phase 3 becomes active only after every required bootstrap effect reads back true under this exact-head evaluation.",
    }
    p["bootstrap_sha256"] = hjson(p)
    return p


def self_test() -> None:
    assert hjson({"b": 2, "a": 1}) == hjson({"a": 1, "b": 2})
    try:
        bootstrap({"verdict": "HOLD"})
    except ValueError:
        pass
    else:
        raise AssertionError("bootstrap must reject non-GO")
    try:
        bootstrap({"verdict": "GO", "exact_git_sha": "a" * 40, "current_main_sha": "b" * 40})
    except ValueError:
        pass
    else:
        raise AssertionError("bootstrap must reject non-current-main GO")
    with TemporaryDirectory() as temporary_directory:
        snapshot_path = Path(temporary_directory) / "snapshot.json"
        snapshot_path.write_text(json.dumps({
            "ok": True,
            "snapshot_sha256": "a" * 64,
            "snapshot": {
                "source_head_sha": "b" * 40,
                "thivebase": {
                    "required_reads_complete": True,
                    "chlom_gen6": {"ok": True},
                    "commercial_release_factory": {"ok": True},
                    "phase3_live_gate": {"ok": True, "data": {"gates": None}},
                    "phase3_live_gate_exact_head_bound": True,
                },
                "side_effects": {
                    "database_mutation": False,
                    "commerce_activation": False,
                    "money_movement": False,
                    "phase_transition": False,
                    "sovereign_vote_effect": False,
                },
            },
        }))
        ok, _, why = thivebase(snapshot_path, "b" * 40)
        assert ok is False
        assert "phase3_live_gate_gates_invalid" in why
    print("PASS_CT_P299_MACHINE_HARD_EXIT_V2_SELF_TEST")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--thivebase-snapshot", type=Path)
    ap.add_argument("--output", type=Path, default=Path("artifacts/ct-p299-hard-exit-evaluation.json"))
    ap.add_argument("--emit-bootstrap", type=Path)
    ap.add_argument("--require-go", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return 0

    try:
        branch = github_main(os.getenv("CT_REPOSITORY", "crownthrive1/CrownThrive-OS"), os.getenv("GITHUB_TOKEN"))
    except Exception as exc:
        branch = {
            "protected": False,
            "protection": {"enabled": False, "required_status_checks": {"enforcement_level": "unknown"}},
            "commit": {"sha": ""},
            "observation_error": type(exc).__name__,
        }

    out = evaluate(branch, a.thivebase_snapshot)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(cbytes(out))
    print(json.dumps(out, indent=2, sort_keys=True))
    if a.emit_bootstrap:
        p = bootstrap(out)
        a.emit_bootstrap.parent.mkdir(parents=True, exist_ok=True)
        a.emit_bootstrap.write_bytes(cbytes(p))
        print(json.dumps(p, indent=2, sort_keys=True))
    return 42 if a.require_go and out["verdict"] != "GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
