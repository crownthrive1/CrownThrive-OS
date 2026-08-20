#!/usr/bin/env python3
"""CrownThrive governed collision preflight, queue throttle, and post-merge reconciler.

Standard-library only. The script is intentionally read-only against GitHub. It may
classify, score, serialize, and recommend review routing; it never merges, votes,
changes branch protection, or mutates provider state.
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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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


def stable_fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


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


def classify_pr_pair(pr_a: Dict[str, Any], pr_b: Dict[str, Any], files_a: Sequence[str], files_b: Sequence[str]) -> Dict[str, Any]:
    result = classify_path_collision(files_a, files_b)
    result.update({"pr_a": pr_a.get("number"), "pr_b": pr_b.get("number")})
    base_a = (pr_a.get("base") or {}).get("ref")
    base_b = (pr_b.get("base") or {}).get("ref")
    head_a = (pr_a.get("head") or {}).get("ref")
    head_b = (pr_b.get("head") or {}).get("ref")
    if base_a == head_b or base_b == head_a:
        result["severity"] = max(result["severity"], 2)
        result["class"] = COLLISION_NAMES[result["severity"]]
        result["reasons"] = sorted(set(result["reasons"] + ["stacked_dependency_detected"]))
    result["fingerprint"] = stable_fingerprint({k: v for k, v in result.items() if k != "fingerprint"})
    return result


def _request_json(url: str, token: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CrownThrive-Collision-Control/1.0",
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


def age_points(created_at: Optional[str], now: Optional[datetime] = None) -> int:
    if not created_at:
        return 0
    now = now or datetime.now(timezone.utc)
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    days = max(0.0, (now - created).total_seconds() / 86400.0)
    return min(5, int(days // 2) + (1 if days >= 1 else 0))


def priority_score(pr: Dict[str, Any], max_collision_severity: int, stale_base: bool = False) -> Dict[str, Any]:
    title = str(pr.get("title") or "").lower()
    body = str(pr.get("body") or "").lower()
    text = f"{title}\n{body}"
    labels = {str(item.get("name") or "").lower() for item in (pr.get("labels") or []) if isinstance(item, dict)}

    dimensions = {
        "phase_hard_exit_impact": 25 if ("hard-exit" in text or "hard exit" in text or "phase 2.99" in text) else 0,
        "security_or_integrity_urgency": 20 if any(term in text for term in ("critical security", "security", "integrity", "codeql")) else 0,
        "dependency_unblock_fanout": 20 if any(term in text for term in ("blocker", "blocked", "gate", "reconcile", "dependency")) else 0,
        "explicit_founder_priority": 15 if "founder-priority" in labels else 0,
        "evidence_staleness_or_rebase_pressure": 10 if stale_base or "stale" in text else 0,
        "age_and_queue_fairness": age_points(pr.get("created_at")),
        "reversibility_and_boundedness": 5 if any(term in text for term in ("bounded", "rollback", "revert")) else 0,
    }
    penalties = {
        "unresolved_direct_collision": 25 if max_collision_severity >= 2 else 0,
        "stale_base": 15 if stale_base else 0,
        "missing_required_specialist": 10 if "specialist" in text and "pending" in text else 0,
        "unclassified_material_scope": 0,
    }
    score = max(0, min(100, sum(dimensions.values()) - sum(penalties.values())))

    if any(term in text for term in ("d3", "human-reserved", "human reserved")) and any(term in text for term in ("pending", "hold", "requires")):
        band = "HOLD_D3"
    elif any(term in text for term in ("critical security incident", "emergency")) and "founder-priority" in labels:
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
        "hard_block": max_collision_severity >= 5 or band == "HOLD_D3",
    }


def _collision_matrix(prs: Sequence[Dict[str, Any]], file_map: Dict[int, List[str]]) -> List[Dict[str, Any]]:
    collisions: List[Dict[str, Any]] = []
    for idx, pr_a in enumerate(prs):
        for pr_b in prs[idx + 1 :]:
            pair = classify_pr_pair(pr_a, pr_b, file_map[pr_a["number"]], file_map[pr_b["number"]])
            if pair["severity"] > 0:
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
    result = {int(pr["number"]): set() for pr in prs}
    for item in collisions:
        domains = set(item.get("domains") or [])
        result[int(item["pr_a"])].update(domains)
        result[int(item["pr_b"])].update(domains)
    return result


def throttle_queue(prs: Sequence[Dict[str, Any]], collisions: Sequence[Dict[str, Any]], main_sha: str) -> Dict[str, Any]:
    max_coll = _max_collision_by_pr(prs, collisions)
    domains = _domains_by_pr(prs, collisions)
    ranked: List[Dict[str, Any]] = []
    for pr in prs:
        base = pr.get("base") or {}
        stale = base.get("ref") == "main" and base.get("sha") != main_sha
        priority = priority_score(pr, max_coll[int(pr["number"])], stale_base=stale)
        ranked.append(
            {
                "number": int(pr["number"]),
                "title": pr.get("title"),
                "draft": bool(pr.get("draft")),
                "base": base.get("ref"),
                "base_sha": base.get("sha"),
                "head_sha": (pr.get("head") or {}).get("sha"),
                "stale_base": stale,
                "collision_severity": max_coll[int(pr["number"])],
                "collision_domains": sorted(domains[int(pr["number"])]),
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
        item_domains = set(item["collision_domains"])
        if len(selected) >= 2:
            throttled.append({"number": item["number"], "reason": "d2_final_quorum_wip_limit"})
            continue
        if occupied_domains & item_domains:
            throttled.append({"number": item["number"], "reason": "collision_domain_already_occupied"})
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
        },
    }


def special_quorum_reasons(pr: Dict[str, Any], collision_severity: int, invalidated_ready_count: int = 0) -> List[str]:
    text = f"{pr.get('title') or ''}\n{pr.get('body') or ''}".lower()
    reasons: List[str] = []
    if collision_severity >= 3:
        reasons.append("material_collision_deadlock_or_semantic_conflict")
    if any(term in text for term in ("critical security", "high security", "codeql high")):
        reasons.append("critical_or_high_security_sequence_decision")
    if "hard-exit" in text or "hard exit" in text:
        reasons.append("phase_hard_exit_blocker_or_fanout")
    if invalidated_ready_count >= 3:
        reasons.append("main_move_invalidated_three_or_more_promotion_ready_packets")
    labels = {str(item.get("name") or "").lower() for item in (pr.get("labels") or []) if isinstance(item, dict)}
    if "founder-priority" in labels:
        reasons.append("explicit_recorded_founder_priority")
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
        if pair["severity"] > 0:
            collisions.append(pair)
    max_severity = max((int(item["severity"]) for item in collisions), default=0)
    base = target.get("base") or {}
    stale = base.get("ref") == "main" and base.get("sha") != main_sha
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
        "throttle": throttle_queue(prs, collisions, main_sha),
    }
    result["fingerprint"] = stable_fingerprint(result)
    return result


def postmerge_snapshot(repo: str, token: str, merged_sha: Optional[str] = None) -> Dict[str, Any]:
    prs = list_open_prs(repo, token)
    main_sha = current_main_sha(repo, token)
    stale_prs: List[Dict[str, Any]] = []
    for pr in prs:
        base = pr.get("base") or {}
        if base.get("ref") == "main" and base.get("sha") != main_sha:
            stale_prs.append(
                {
                    "number": int(pr["number"]),
                    "base_sha": base.get("sha"),
                    "head_sha": (pr.get("head") or {}).get("sha"),
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

    fake_pr = {
        "number": 1,
        "title": "Phase 2.99 hard-exit blocker reconciliation",
        "body": "Bounded rollback with security review.",
        "labels": [],
        "created_at": "2026-08-19T00:00:00Z",
    }
    priority = priority_score(fake_pr, 0, stale_base=False)
    assert priority["score"] >= 65
    assert priority["band"] == "P1"

    return {
        "status": "PASS",
        "tests": 6,
        "constitutional_collision": constitutional["class"],
        "runtime_collision": runtime["class"],
        "hard_exit_priority": priority,
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
