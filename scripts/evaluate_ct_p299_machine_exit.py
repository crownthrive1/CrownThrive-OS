#!/usr/bin/env python3
"""Fail-closed CT-P299 hard-exit evaluator. PASSing this program is not Phase-3 GO."""

from __future__ import annotations
import argparse, hashlib, json, os, subprocess, urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
P = lambda x: ROOT / x
CONTRACT = P("developers/manifests/ct-p299-machine-hard-exit.v1.json")
LEDGER = P("developers/manifests/phase-2-99-hard-exit-ledger.v1.json")
NAMESPACE = P("developers/manifests/institutional-phase-namespace.v2.json")
AUTHORITY = P("governance/phase3-entry-authority-receipt.v1.json")
RECOVERY = P("governance/phase3-entry-recovery-receipt.v1.json")
TEXT = {".md", ".mdx", ".json", ".yaml", ".yml", ".txt"}
SKIP = {".git", "node_modules", "artifacts", "phase3-inputs", ".venv", "venv", "__pycache__"}

def cbytes(v: Any) -> bytes:
    return (json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()

def hbytes(v: bytes) -> str: return hashlib.sha256(v).hexdigest()
def hjson(v: Any) -> str: return hbytes(cbytes(v))
def load(path: Path) -> dict[str, Any]: return json.loads(path.read_text())
def head() -> str: return subprocess.check_output(["git","rev-parse","HEAD"], cwd=ROOT, text=True).strip().lower()

def source_snapshot(contract: dict[str, Any]) -> dict[str, Any]:
    files, missing = {}, []
    for rel in contract["canonical_sources"]:
        path = P(rel)
        if path.is_file(): files[rel] = hbytes(path.read_bytes())
        else: missing.append(rel)
    out = {"algorithm":"sha256-per-file-plus-canonical-json-v1","files":files,"missing":missing}
    out["snapshot_sha256"] = hjson(out)
    return out

def docs_baseline() -> dict[str, Any]:
    entries = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT: continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP for part in rel.parts): continue
        entries[str(rel)] = hbytes(path.read_bytes())
    basis = {"algorithm":"sha256-text-estate-canonical-map-v1","files":entries}
    return {"algorithm":basis["algorithm"],"file_count":len(entries),"baseline_sha256":hjson(basis)}

def github_main(repo: str, token: str | None) -> dict[str, Any]:
    headers={"Accept":"application/vnd.github+json","User-Agent":"CrownThrive-Phase3-Hard-Exit/1","X-GitHub-Api-Version":"2022-11-28"}
    if token: headers["Authorization"]=f"Bearer {token}"
    req=urllib.request.Request(f"https://api.github.com/repos/{repo}/branches/main",headers=headers)
    with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read())

def authority_ok(d: dict[str,Any], git_head: str, source_sha: str) -> tuple[bool,list[str]]:
    why=[]
    if d.get("state")!="VERIFIED": why.append("authority_receipt_not_verified")
    if d.get("exact_head_sha")!=git_head: why.append("authority_receipt_head_mismatch")
    if d.get("source_snapshot_sha256")!=source_sha: why.append("authority_receipt_source_snapshot_mismatch")
    for k in ("agent_a","independent_audit","security","agent_d"):
        if d.get(k)!="PASS": why.append(f"{k}_not_pass")
    g=d.get("sovereign_governance",{}); approvals=set(g.get("approvals") or [])
    if len(approvals)<int(g.get("minimum_approvals",4)): why.append("sovereign_quorum_not_met")
    if "D" not in approvals or g.get("agent_d_approved") is not True: why.append("agent_d_mandatory_approval_missing")
    if g.get("denials"): why.append("sovereign_denial_present")
    if g.get("blocks"): why.append("sovereign_block_present")
    if d.get("originator_self_approval") is not False: why.append("originator_self_approval_prohibited")
    return not why,why

def recovery_ok(d: dict[str,Any], git_head: str) -> tuple[bool,list[str]]:
    why=[]
    if d.get("state")!="VERIFIED": why.append("recovery_receipt_not_verified")
    if d.get("exact_head_sha")!=git_head: why.append("recovery_receipt_head_mismatch")
    for k in ("backup_verified","restore_tested","rollback_tested","off_provider_copy_verified","exact_readback_verified"):
        if d.get(k) is not True: why.append(f"{k}_not_verified")
    return not why,why

def thivebase(path: Path | None) -> tuple[bool,dict[str,Any],list[str]]:
    if not path or not path.exists(): return False,{},["thivebase_snapshot_missing"]
    try: d=load(path)
    except Exception: return False,{},["thivebase_snapshot_invalid_json"]
    why=[]
    if d.get("ok") is not True: why.append("thivebase_snapshot_not_ok")
    digest=str(d.get("snapshot_sha256") or "").lower()
    if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest): why.append("thivebase_snapshot_digest_invalid")
    snap=d.get("snapshot",{})
    thive=snap.get("thivebase",{})
    if thive.get("required_reads_complete") is not True:
        why.append("thivebase_required_reads_incomplete")
    for rail in ("chlom_gen6","commercial_release_factory"):
        if thive.get(rail,{}).get("ok") is not True:
            why.append(f"thivebase_{rail}_read_not_ok")
    side=snap.get("side_effects",{})
    for k in ("database_mutation","commerce_activation","money_movement","phase_transition","sovereign_vote_effect"):
        if side.get(k) is not False: why.append(f"thivebase_snapshot_{k}_must_be_false")
    return not why,d,why

def evaluate(branch: dict[str,Any], snapshot_path: Path | None) -> dict[str,Any]:
    contract, ledger, ns, auth, rec = map(load,(CONTRACT,LEDGER,NAMESPACE,AUTHORITY,RECOVERY))
    git_head=head(); sources=source_snapshot(contract); docs=docs_baseline()
    no_go=[]; holds=[]
    for k,v in {"decision_id":"CT-ADR-ROADMAP-010","top_level_phase_count":10,"current_phase":2,"current_subphase":"2.99"}.items():
        if ns.get(k)!=v: no_go.append(f"namespace_{k}_mismatch")
    required=set(contract["hard_exit_gate_policy"]["required_gate_ids"])
    rows={r.get("gate_id"):r for r in ledger.get("open_hard_gates",[])}
    evaluated=set(rows)==required and all(r.get("state") is not None for r in rows.values())
    if set(rows)!=required: no_go.append("hard_exit_gate_registry_incomplete")
    for gate_id in sorted(required):
        row=rows.get(gate_id)
        if not row: continue
        allowed={"pass"} | ({"deferred_accepted"} if row.get("deferral_permitted") is True else set())
        if row.get("state") not in allowed: no_go.append(f"{gate_id}:{row.get('state')}")
    protected=branch.get("protected") is True
    enabled=branch.get("protection",{}).get("enabled") is True
    enforcement=branch.get("protection",{}).get("required_status_checks",{}).get("enforcement_level")
    governance_pass=protected and enabled and enforcement in {"non_admins","everyone"}
    if not governance_pass: no_go.append("CT-P299-GATE-004:live_main_merge_governance_not_fail_closed")
    main_sha=str(branch.get("commit",{}).get("sha") or "").lower()
    if len(main_sha)!=40: no_go.append("github_main_sha_unavailable")
    if ledger.get("observed_main_sha")!=main_sha: holds.append("static_hard_exit_ledger_stale_to_current_main")
    tb_ok,tb,tb_why=thivebase(snapshot_path); holds+=tb_why
    a_ok,a_why=authority_ok(auth,git_head,sources["snapshot_sha256"]); holds+=a_why
    r_ok,r_why=recovery_ok(rec,git_head); holds+=r_why
    if sources["missing"]: no_go.append("canonical_source_snapshot_incomplete")
    freezes={
      "all_blockers_evaluated":evaluated,
      "absolute_no_go_zero":not no_go,
      "exact_source_snapshot_frozen":not sources["missing"],
      "exact_git_sha_frozen":len(git_head)==40,
      "exact_thivebase_snapshot_frozen":tb_ok,
      "docs_baseline_frozen":docs["file_count"]>0,
      "authority_quorum_verified":a_ok,
      "backup_rollback_receipt_verified":r_ok,
    }
    verdict="NO_GO" if no_go else ("HOLD" if not all(freezes.values()) else "GO")
    out={
      "schema_version":"1.0.0","evaluation_id":"ct.evaluation.p299-hard-exit.v1",
      "contract_id":contract["contract_id"],"verdict":verdict,
      "phase3_activation_state":"NOT_ACTIVE" if verdict!="GO" else "GO_ELIGIBLE_BOOTSTRAP_NOT_COMMITTED",
      "exact_git_sha":git_head,"current_main_sha":main_sha,"source_snapshot":sources,
      "docs_baseline":docs,"thivebase_snapshot_sha256":tb.get("snapshot_sha256"),
      "freezes":freezes,"absolute_no_go_conditions":sorted(set(no_go)),"holds":sorted(set(holds)),
      "live_main_governance":{"protected":protected,"protection_enabled":enabled,"required_status_enforcement":enforcement,"pass":governance_pass},
      "bootstrap_permitted":verdict=="GO","phase3_active":False,
    }
    out["evaluation_sha256"]=hjson(out); return out

def bootstrap(e: dict[str,Any]) -> dict[str,Any]:
    if e.get("verdict")!="GO": raise ValueError("phase3_bootstrap_requires_GO")
    p={
      "schema_version":"1.0.0","bootstrap_id":"CT-PHASE3-BOOTSTRAP-v1",
      "state":"GO_ELIGIBLE_BOOTSTRAP_NOT_COMMITTED","exact_git_sha":e["exact_git_sha"],
      "evaluation_sha256":e["evaluation_sha256"],"source_snapshot_sha256":e["source_snapshot"]["snapshot_sha256"],
      "docs_baseline_sha256":e["docs_baseline"]["baseline_sha256"],"thivebase_snapshot_sha256":e["thivebase_snapshot_sha256"],
      "dail_event":{"event_type":"phase_transition_candidate","from":"2.99","to":"3.0","state":"CANDIDATE_NOT_PERSISTED"},
      "required_commit_effects":{
        "dail_event_persisted_and_read_back":False,"thivebase_baseline_persisted_and_read_back":False,
        "git_tag_release_created_and_read_back":False,"mintlify_changelog_published_and_read_back":False,
        "rollback_snapshot_bound_and_read_back":False},
      "phase3_active":False,
      "rule":"Phase 3 becomes active only after every required commit effect reads back true under the same exact evaluation."
    }
    p["bootstrap_sha256"]=hjson(p); return p

def self_test() -> None:
    assert hjson({"b":2,"a":1})==hjson({"a":1,"b":2})
    try: bootstrap({"verdict":"HOLD"})
    except ValueError: pass
    else: raise AssertionError("bootstrap must reject non-GO")
    print("PASS_CT_P299_MACHINE_HARD_EXIT_SELF_TEST")

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--thivebase-snapshot",type=Path); ap.add_argument("--output",type=Path,default=Path("artifacts/ct-p299-hard-exit-evaluation.json"))
    ap.add_argument("--emit-bootstrap",type=Path); ap.add_argument("--require-go",action="store_true"); a=ap.parse_args()
    if a.self_test: self_test(); return 0
    try: branch=github_main(os.getenv("CT_REPOSITORY","crownthrive1/CrownThrive-Support"),os.getenv("GITHUB_TOKEN"))
    except Exception as exc: branch={"protected":False,"protection":{"enabled":False,"required_status_checks":{"enforcement_level":"unknown"}},"commit":{"sha":""},"observation_error":type(exc).__name__}
    out=evaluate(branch,a.thivebase_snapshot); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_bytes(cbytes(out)); print(json.dumps(out,indent=2,sort_keys=True))
    if a.emit_bootstrap: p=bootstrap(out); a.emit_bootstrap.parent.mkdir(parents=True,exist_ok=True); a.emit_bootstrap.write_bytes(cbytes(p))
    return 42 if a.require_go and out["verdict"]!="GO" else 0

if __name__=="__main__": raise SystemExit(main())
