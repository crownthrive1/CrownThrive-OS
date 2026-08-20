#!/usr/bin/env python3
"""CrownThrive governed collision preflight, queue throttle, and post-merge reconciler.

Standard-library only. The controller is intentionally read-only against GitHub. It
classifies, scores, serializes, and recommends review routing; it never merges,
casts votes, changes branch protection, or mutates provider state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

API_ROOT = "https://api.github.com"

COLLISION_NAMES = {
    0: "CT-COLL-0_clear",
    1: "CT-COLL-1_soft_shared_surface",
    2: "CT-COLL-2_direct_file_or_sequence_collision",
    3: "CT-COLL-3_semantic_or_identity_collision",
    4: "CT-COLL-4_runtime_or_provider_mutation_collision",
    5: "CT-COLL-5_constitutional_or_d3_collision",
}

CONSTITUTIONAL_MARKERS = (
    "agent-sovereign-governance",
    "governed_merge_decision",
    "governed_current_pr_preflight",
    "founder-reserved",
    "autonomy-operating-constitution",
)
RUNTIME_MARKERS = (
    "supabase/",
    "migrations/",
    "edge-functions/",
    "credential",
    "secret",
    "vault",
    "deployment",
    "provider-write",
)
IDENTITY_MARKERS = (
    "agent-registry",
    "repository-federation",
    "fingerprint-id",
    "stable-id",
    "identity-crosswalk",
)

SECURITY_PRIORITY_LABELS = {
    "security-critical",
    "security-high",
    "incident-critical",
}
HARD_EXIT_PRIORITY_LABELS = {
    "phase-hard-exit-blocker",
    "hard-exit-blocker",
}


def stable_fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _label_names(pr: Dict[str, Any]) -> Set[str]:
    return {
        str(item.get("name") or "").strip().lower()
        for item in (pr.get("labels") or [])
        if isinstance(item, dict) and item.get("name")
    }


def _path_surface(path: str) -> Optional[str]:
    p = path.lower()
    if p == "docs.json":
        return "mintlify_navigation"
    if p == "agents.md":
        return "root_agent_policy"
    if p.startswith(".github/workflows/"):
        return "github_workflow_control"
    if any(marker in p for marker in CONSTITUTIONAL_MARKERS):
        return "constitutional_governance"
    if any(marker in p for marker in RUNTIME_MARKERS):
        return "runtime_provider_control"
    if any(marker in p for marker in IDENTITY_MARKERS):
        return "institutional_identity"
    if p.startswith("developers/manifests/"):
        return "machine_manifest"
    if p.startswith("automation/"):
        return "agent_automation_docs"
    if p.startswith("standards/"):
        return "institutional_policy"
    if p.startswith("scripts/"):
        return "validator_or_control_script"
    if p.startswith("contracts/chlom/") or p.startswith("reference/chlom_runtime/"):
        return "chlom_contract_runtime"
    return None


def _severity_for_exact_path(path: str) -> int:
    p = path.lower()
    if any(marker in p for marker in CONSTITUTIONAL_MARKERS):
        return 5
    if any(marker in p for marker in RUNTIME_MARKERS):
        return 4
    if any(marker in p for marker in IDENTITY_MARKERS) or p.startswith("standards/"):
        return 3
    return 2


def classify_path_collision(paths_a: Iterable[str], paths_b: Iterable[str]) -> Dict[str, Any]:
    a = set(paths_a)
    b = set(paths_b)
    exact = sorted(a & b)

    surfaces_a: Dict[str, List[str]] = {}
    surfaces_b: Dict[str, List[str]] = {}
    for path in sorted(a):
        surface = _path_surface(path)
        if surface:
            surfaces_a.setdefault(surface, []).append(path)
    for path in sorted(b):
        surface = _path_surface(path)
        if surface:
            surfaces_b.setdefault(surface, []).append(path)
    shared_surfaces = sorted(set(surfaces_a) & set(surfaces_b))

    severity = 0
    reasons: List[str] = []
    domains: Set[str] = set()

    if exact:
        severity = max(_severity_for_exact_path(path) for path in exact)
        reasons.append("exact_changed_file_overlap")
        domains.update(_path_surface(path) or f"file:{path}" for path in exact)
    elif shared_surfaces:
        severity = 1
        reasons.append("shared_high_risk_surface")
        domains.update(shared_surfaces)

    # Parallel work in these broad families is riskier than ordinary shared folders.
    # Exact file overlap still determines the strongest file-level severity.
    if "constitutional_governance" in shared_surfaces:
        severity = max(severity, 3 if not exact else severity)
        reasons.append("constitutional_surface_parallel_change")
    if "runtime_provider_control" in shared_surfaces:
        severity = max(severity, 2 if not exact else severity)
        reasons.append("runtime_surface_parallel_change")
    if "institutional_identity" in shared_surfaces:
        severity = max(severity, 2 if not exact else severity)
        reasons.append("identity_surface_parallel_change")

    result = {
        "severity": severity,
        "class": COLLISION_NAMES[severity],
        "exact_files": exact,
        "shared_surfaces": shared_surfaces,
        "domains": sorted(domains),
        "reasons": sorted(set(reasons)),
    }
    result["fingerprint"] = stable_fingerprint(result)
    return result


def classify_pr_pair(
    pr_a: Dict[str, Any],
    pr_b: Dict[str, Any],
    files_a: Sequence[str],
    files_b: Sequence[str],
) -> Dict[str, Any]:
    result = classify_path_collision(files_a, files_b)
    result.update({"pr_a": pr_a.get("number"), "pr_b": pr_b.get("number")})

    base_a = (pr_a.get("base") or {}).get("ref")
    base_b = (pr_b.get("base") or {}).get("ref")
    head_a = (pr_a.get("head") or {}).get("ref")
    head_b = (pr_b.get("head") or {}).get("ref")
    if base_a == head_b or base_b == head_a:
        result["severity"] = max(int(result["severity"]), 2)
        result["class"] = COLLISION_NAMES[int(result["severity"])]
        result["reasons"] = sorted(set((result.get("reasons") or []) + ["stacked_dependency_detected"]))

    result["fingerprint"] = stable_fingerprint({k: v for k, v in result.items() if k != "fingerprint"})
    return result


def _request_json(url: str, token: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CrownThrive-Collision-Control/1.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} for {url}: {body[:500]}") from exc


def _paginate(url: str, token: str) -> List[Any]:
    out: List[Any] = []
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        data = _request_json(f"{url}{sep}per_page=100&page={page}", token)
        if not isinstance(data, list):
            raise RuntimeError(f"Expected list from paginated endpoint: {url}")
        out.extend(data)
        if len(data) < 100:
            return out
        page += 1


def list_open_prs(repo: str, token: str) -> List[Dict[str, Any]]:
    return _paginate(f"{API_ROOT}/repos/{repo}/pulls?state=open&sort=created&direction=asc", token)


def list_pr_files(repo: str, pr_number: int, token: str) -> List[str]:
    data = _paginate(f"{API_ROOT}/repos/{repo}/pulls/{pr_number}/files", token)
    return sorted(str(item["filename"]) for item in data if item.get("filename"))


def current_main_sha(repo: str, token: str, branch: str = "main") -> str:
    data = _request_json(f"{API_ROOT}/repos/{repo}/branches/{urllib.parse.quote(branch, safe='')}", token)
    return str(data["commit"]["sha"])


def pr_main_behind_by(repo: str, pr: Dict[str, Any], main_sha: str, token: str) -> Optional[int]:
    """Return commits the PR head is behind current main, or None for stacked non-main PRs.

    GitHub's PR base object can reflect a moving base branch, so comparing its base SHA
    to current main is not a sufficient staleness test. The compare API is the binding
    source for whether a main-based PR head has actually inherited current main.
    """

    base = pr.get("base") or {}
    if base.get("ref") != "main":
        return None
    head_sha = str((pr.get("head") or {}).get("sha") or "")
    if not head_sha:
        raise RuntimeError(f"PR #{pr.get('number')} has no resolvable head SHA")
    data = _request_json(f"{API_ROOT}/repos/{repo}/compare/{main_sha}...{head_sha}", token)
    return int(data.get("behind_by") or 0)


def age_points(created_at: Optional[str], now: Optional[datetime] = None) -> int:
    if not created_at:
        return 0
    now = now or datetime.now(timezone.utc)
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    days = max(0.0, (now - created).total_seconds() / 86400.0)
    return min(5, int(days // 2) + (1 if days >= 1 else 0))


def priority_score(pr: Dict[str, Any], max_collision_severity: int, stale_base: bool = False) -> Dict[str, Any]:
    """Produce a bounded queue score from explicit state, title, and governed labels.

    Emergency/D3/security/quorum state is intentionally label-bound rather than inferred
    from arbitrary body prose. A policy document that merely *describes* D3 or a security
    incident must not summon an emergency queue or Special Quorum by itself.
    """

    title = str(pr.get("title") or "").strip().lower()
    body = str(pr.get("body") or "").lower()
    labels = _label_names(pr)

    hard_exit = bool(HARD_EXIT_PRIORITY_LABELS & labels) or "hard-exit" in title or "hard exit" in title
    security_urgent = bool(SECURITY_PRIORITY_LABELS & labels)
    dependency_unblock = (
        "dependency-unblock" in labels
        or "blocker" in title
        or "reconcile" in title
        or "dependency" in title
        or "gate" in title
    )
    explicit_founder = "founder-priority" in labels
    title_stale = "stale" in title or "rebase" in title
    reversible = any(term in body for term in ("bounded", "rollback", "revert"))
    specialist_pending = "specialist-pending" in labels
    unclassified_material = "material-scope-unclassified" in labels
    d3_hold = "d3-human-hold" in labels

    dimensions = {
        "phase_hard_exit_impact": 25 if hard_exit else 0,
        "security_or_integrity_urgency": 20 if security_urgent else 0,
        "dependency_unblock_fanout": 20 if dependency_unblock else 0,
        "explicit_founder_priority": 15 if explicit_founder else 0,
        "evidence_staleness_or_rebase_pressure": 10 if stale_base or title_stale else 0,
        "age_and_queue_fairness": age_points(pr.get("created_at")),
        "reversibility_and_boundedness": 5 if reversible else 0,
    }
    penalties = {
        "unresolved_direct_collision": 25 if max_collision_severity >= 2 else 0,
        "stale_base": 15 if stale_base else 0,
        "missing_required_specialist": 10 if specialist_pending else 0,
        "unclassified_material_scope": 25 if unclassified_material else 0,
    }
    score = max(0, min(100, sum(dimensions.values()) - sum(penalties.values())))

    if d3_hold:
        band = "HOLD_D3"
    elif explicit_founder and security_urgent:
        band = "P0"
    elif score >= 65:
        band = "P1"
    elif score >= 40:
        band = "P2"
    elif score >= 20:
        band = "P3"
    else:
        band = "P4"

    return {
        "score": score,
        "band": band,
        "dimensions": dimensions,
        "penalties": penalties,
        "hard_block": max_collision_severity >= 5 or d3_hold or unclassified_material,
    }


def _collision_matrix(prs: Sequence[Dict[str, Any]], file_map: Dict[int, List[str]]) -> List[Dict[str, Any]]:
    collisions: List[Dict[str, Any]] = []
    for idx, pr_a in enumerate(prs):
        for pr_b in prs[idx + 1 :]:
            pair = classify_pr_pair(pr_a, pr_b, file_map[int(pr_a["number"])], file_map[int(pr_b["number"])])
            if int(pair["severity"]) > 0:
                collisions.append(pair)
    return collisions


def _max_collision_by_pr(prs: Sequence[Dict[str, Any]], collisions: Sequence[Dict[str, Any]]) -> Dict[int, int]:
    result = {int(pr["number"]): 0 for pr in prs}
    for item in collisions:
        severity = int(item["severity"])
        result[int(item["pr_a"])] = max(result[int(item["pr_a"])], severity)
        result[int(item["pr_b"])] = max(result[int(item["pr_b"])], severity)
    return result


def _domains_by_pr(prs: Sequence[Dict[str, Any]], collisions: Sequence[Dict[str, Any]]) -> Dict[int, Set[str]]:
    """Return only exclusive/material collision domains.

    CT-COLL-1 is awareness: two packets may both contain manifests or independent
    workflows without being serialized. CT-COLL-2+ owns an exclusive collision domain
    until the conflict is resolved/adjudicated.
    """

    result = {int(pr["number"]): set() for pr in prs}
    for item in collisions:
        if int(item.get("severity") or 0) < 2:
            continue
        domains = set(item.get("domains") or [])
        result[int(item["pr_a"])].update(domains)
        result[int(item["pr_b"])].update(domains)
    return result


def throttle_queue(
    repo: str,
    token: str,
    prs: Sequence[Dict[str, Any]],
    collisions: Sequence[Dict[str, Any]],
    main_sha: str,
) -> Dict[str, Any]:
    max_coll = _max_collision_by_pr(prs, collisions)
    exclusive_domains = _domains_by_pr(prs, collisions)
    ranked: List[Dict[str, Any]] = []

    for pr in prs:
        pr_number = int(pr["number"])
        base = pr.get("base") or {}
        behind_by = pr_main_behind_by(repo, pr, main_sha, token)
        stale = bool(behind_by is not None and behind_by > 0)
        priority = priority_score(pr, max_coll[pr_number], stale_base=stale)
        ranked.append(
            {
                "number": pr_number,
                "title": pr.get("title"),
                "draft": bool(pr.get("draft")),
                "base": base.get("ref"),
                "base_sha": base.get("sha"),
                "head_sha": (pr.get("head") or {}).get("sha"),
                "behind_current_main_by": behind_by,
                "stale_base": stale,
                "collision_severity": max_coll[pr_number],
                "exclusive_collision_domains": sorted(exclusive_domains[pr_number]),
                "priority": priority,
            }
        )

    ranked.sort(key=lambda item: (item["priority"]["hard_block"], -item["priority"]["score"], item["number"]))

    selected: List[int] = []
    throttled: List[Dict[str, Any]] = []
    occupied_domains: Set[str] = set()
    for item in ranked:
        if item["priority"]["hard_block"] or item["draft"]:
            throttled.append({"number": item["number"], "reason": "hard_block_or_draft"})
            continue
        if item["stale_base"]:
            throttled.append({"number": item["number"], "reason": "behind_current_main"})
            continue
        item_domains = set(item["exclusive_collision_domains"])
        if len(selected) >= 2:
            throttled.append({"number": item["number"], "reason": "d2_final_quorum_wip_limit"})
            continue
        if occupied_domains & item_domains:
            throttled.append({"number": item["number"], "reason": "exclusive_collision_domain_already_occupied"})
            continue
        selected.append(item["number"])
        occupied_domains.update(item_domains)

    return {
        "main_sha": main_sha,
        "ranked": ranked,
        "selected_final_quorum_slots": selected,
        "throttled": throttled,
        "policy": {
            "max_concurrent_final_quorum_d2": 2,
            "max_concurrent_same_collision_domain": 1,
            "max_concurrent_d3": 1,
            "soft_collision_serializes_queue": False,
        },
    }


def special_quorum_reasons(
    pr: Dict[str, Any],
    collision_severity: int,
    invalidated_ready_count: int = 0,
) -> List[str]:
    labels = _label_names(pr)
    reasons: List[str] = []

    if collision_severity >= 3:
        reasons.append("material_collision_deadlock_or_semantic_conflict")
    if SECURITY_PRIORITY_LABELS & labels:
        reasons.append("critical_or_high_security_sequence_decision")
    if HARD_EXIT_PRIORITY_LABELS & labels:
        reasons.append("phase_hard_exit_blocker_or_fanout")
    if invalidated_ready_count >= 3:
        reasons.append("main_move_invalidated_three_or_more_promotion_ready_packets")
    if "founder-priority" in labels:
        reasons.append("explicit_recorded_founder_priority")
    if "special-quorum" in labels:
        reasons.append("explicit_governed_special_quorum_request")

    return sorted(set(reasons))


def preflight(repo: str, token: str, pr_number: int) -> Dict[str, Any]:
    prs = list_open_prs(repo, token)
    target = next((pr for pr in prs if int(pr["number"]) == pr_number), None)
    if target is None:
        raise RuntimeError(f"PR #{pr_number} is not open or not visible")

    main_sha = current_main_sha(repo, token)
    files_target = list_pr_files(repo, pr_number, token)
    collisions: List[Dict[str, Any]] = []
    for other in prs:
        if int(other["number"]) == pr_number:
            continue
        files_other = list_pr_files(repo, int(other["number"]), token)
        pair = classify_pr_pair(target, other, files_target, files_other)
        if int(pair["severity"]) > 0:
            collisions.append(pair)

    max_severity = max((int(item["severity"]) for item in collisions), default=0)
    base = target.get("base") or {}
    behind_by = pr_main_behind_by(repo, target, main_sha, token)
    stale = bool(behind_by is not None and behind_by > 0)
    if stale:
        max_severity = max(max_severity, 2)

    priority = priority_score(target, max_severity, stale_base=stale)
    result = {
        "mode": "preflight",
        "repo": repo,
        "pr": pr_number,
        "current_main_sha": main_sha,
        "target_base_ref": base.get("ref"),
        "target_base_sha": base.get("sha"),
        "target_head_sha": (target.get("head") or {}).get("sha"),
        "target_changed_files": files_target,
        "behind_current_main_by": behind_by,
        "stale_main_base": stale,
        "max_collision_severity": max_severity,
        "collisions": collisions,
        "priority": priority,
        "special_quorum_reasons": special_quorum_reasons(target, max_severity),
        "recommended_disposition": (
            "founder_or_authorized_human_adjudication"
            if max_severity >= 5
            else "hold_for_adjudication"
            if max_severity >= 3
            else "serialize_stack_split_or_rebase"
            if max_severity >= 2 or stale
            else "coordinate_or_rebase"
            if max_severity == 1
            else "continue"
        ),
    }
    result["fingerprint"] = stable_fingerprint(result)
    return result


def queue_snapshot(repo: str, token: str) -> Dict[str, Any]:
    prs = list_open_prs(repo, token)
    file_map = {int(pr["number"]): list_pr_files(repo, int(pr["number"]), token) for pr in prs}
    collisions = _collision_matrix(prs, file_map)
    main_sha = current_main_sha(repo, token)
    result = {
        "mode": "queue",
        "repo": repo,
        "open_pr_count": len(prs),
        "collision_count": len(collisions),
        "collisions": collisions,
        "throttle": throttle_queue(repo, token, prs, collisions, main_sha),
    }
    result["fingerprint"] = stable_fingerprint(result)
    return result


def postmerge_snapshot(repo: str, token: str, merged_sha: Optional[str] = None) -> Dict[str, Any]:
    prs = list_open_prs(repo, token)
    main_sha = current_main_sha(repo, token)
    stale_prs: List[Dict[str, Any]] = []

    for pr in prs:
        behind_by = pr_main_behind_by(repo, pr, main_sha, token)
        if behind_by is not None and behind_by > 0:
            stale_prs.append(
                {
                    "number": int(pr["number"]),
                    "base_sha": (pr.get("base") or {}).get("sha"),
                    "head_sha": (pr.get("head") or {}).get("sha"),
                    "behind_current_main_by": behind_by,
                    "required_action": "fresh_current_main_collision_reconciliation_and_review_rebinding",
                }
            )

    queue = queue_snapshot(repo, token)
    result = {
        "mode": "postmerge",
        "repo": repo,
        "merged_sha": merged_sha,
        "current_main_sha": main_sha,
        "stale_open_pr_count": len(stale_prs),
        "stale_open_prs": stale_prs,
        "queue": queue,
    }
    result["fingerprint"] = stable_fingerprint(result)
    return result


def self_test() -> Dict[str, Any]:
    clear = classify_path_collision(["alpha/new.md"], ["beta/new.md"])
    assert clear["severity"] == 0

    direct = classify_path_collision(["docs.json"], ["docs.json"])
    assert direct["severity"] == 2

    constitutional = classify_path_collision(
        ["developers/manifests/agent-sovereign-governance.v1.json"],
        ["developers/manifests/agent-sovereign-governance.v1.json"],
    )
    assert constitutional["severity"] == 5

    runtime = classify_path_collision(
        ["supabase/migrations/20260820_a.sql"],
        ["supabase/migrations/20260820_a.sql"],
    )
    assert runtime["severity"] == 4

    shared = classify_path_collision(
        [".github/workflows/a.yml"],
        [".github/workflows/b.yml"],
    )
    assert shared["severity"] == 1

    fake_hard_exit = {
        "number": 1,
        "title": "Phase 2.99 hard-exit blocker reconciliation",
        "body": "Bounded rollback.",
        "labels": [{"name": "security-high"}],
        "created_at": "2026-08-19T00:00:00Z",
    }
    priority = priority_score(fake_hard_exit, 0, stale_base=False)
    assert priority["score"] >= 65
    assert priority["band"] == "P1"
    assert "critical_or_high_security_sequence_decision" in special_quorum_reasons(fake_hard_exit, 0)

    descriptive_policy = {
        "number": 2,
        "title": "Document collision governance",
        "body": "This page describes D3 human-reserved authority, critical security incidents, hard-exit blockers, pending specialists, and Special Quorum behavior.",
        "labels": [],
        "created_at": "2026-08-20T00:00:00Z",
    }
    descriptive_priority = priority_score(descriptive_policy, 1, stale_base=False)
    assert descriptive_priority["band"] != "HOLD_D3"
    assert descriptive_priority["hard_block"] is False
    assert special_quorum_reasons(descriptive_policy, 1) == []

    soft_domains = _domains_by_pr(
        [{"number": 1}, {"number": 2}],
        [{"pr_a": 1, "pr_b": 2, "severity": 1, "domains": ["machine_manifest"]}],
    )
    assert soft_domains[1] == set() and soft_domains[2] == set()

    return {
        "status": "PASS",
        "tests": 8,
        "constitutional_collision": constitutional["class"],
        "runtime_collision": runtime["class"],
        "hard_exit_priority": priority,
        "descriptive_policy_priority": descriptive_priority,
        "soft_domains_serialize": False,
    }


def _write_step_summary(result: Dict[str, Any]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("## CrownThrive Collision Control\n\n")
        handle.write(f"- Mode: `{result.get('mode', 'self-test')}`\n")
        if "pr" in result:
            handle.write(f"- PR: `#{result['pr']}`\n")
            handle.write(f"- Max collision severity: `{result.get('max_collision_severity')}`\n")
            handle.write(f"- Disposition: `{result.get('recommended_disposition')}`\n")
            handle.write(f"- Behind current main by: `{result.get('behind_current_main_by')}`\n")
            handle.write(f"- Special quorum reasons: `{', '.join(result.get('special_quorum_reasons') or []) or 'none'}`\n")
        if "open_pr_count" in result:
            handle.write(f"- Open PRs: `{result['open_pr_count']}`\n")
            handle.write(f"- Detected collisions: `{result['collision_count']}`\n")
        if "stale_open_pr_count" in result:
            handle.write(f"- Stale open PRs after main move: `{result['stale_open_pr_count']}`\n")
        handle.write(f"- Fingerprint: `{result.get('fingerprint', 'n/a')}`\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "queue", "postmerge", "self-test"), required=True)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--merged-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--fail-on-severity", type=int, default=2)
    args = parser.parse_args()

    if args.mode == "self-test":
        result = self_test()
    else:
        if not args.repo or not args.token:
            parser.error("--repo and --token/GITHUB_TOKEN are required for live modes")
        if args.mode == "preflight":
            if not args.pr:
                parser.error("--pr is required for preflight")
            result = preflight(args.repo, args.token, args.pr)
        elif args.mode == "queue":
            result = queue_snapshot(args.repo, args.token)
        else:
            result = postmerge_snapshot(args.repo, args.token, args.merged_sha)

    print(json.dumps(result, indent=2, sort_keys=True))
    _write_step_summary(result)

    if args.mode == "preflight" and int(result.get("max_collision_severity", 0)) >= args.fail_on_severity:
        print(
            "Collision preflight HOLD: material collision requires serialization/adjudication before promotion.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
