#!/usr/bin/env python3
"""Bounded CHLOM runtime fabric controller.

This controller executes the safe, observable portion of the Pentafabric lifecycle.
It does not manufacture legal/economic authority, mutate protected repositories,
transfer ownership, disclose secrets, or self-certify production state.
"""
from __future__ import annotations
import argparse, hashlib, json, os, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = [
    "rnd", "documentation", "rights_identity", "compliance_oracle",
    "commercial", "mesh_reliability", "continuity", "maintenance",
]
CONTRACT_GLOBS = ["developers/contracts/*.json", "developers/manifests/chlom-*-candidates.v1.json"]

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def collect_contracts():
    paths = []
    for pattern in CONTRACT_GLOBS:
        paths.extend(ROOT.glob(pattern))
    paths = sorted(set(p for p in paths if p.is_file()))
    records = []
    for p in paths:
        try:
            obj = load_json(p)
            records.append({
                "path": str(p.relative_to(ROOT)),
                "sha256": sha256_bytes(p.read_bytes()),
                "id": obj.get("id") or obj.get("contract_id") or p.stem,
                "state": obj.get("state") or obj.get("status") or "UNSPECIFIED",
            })
        except Exception as exc:
            records.append({"path": str(p.relative_to(ROOT)), "error": type(exc).__name__})
    return records

def run_controller(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    run_id = os.getenv("GITHUB_RUN_ID", str(int(time.time())))
    contracts = collect_contracts()
    bad = [x for x in contracts if "error" in x]
    state = "HOLD" if bad else "READY"
    packet = {
        "schema": "dail.chlom.runtime-event.v1",
        "event_type": "RUNTIME_FABRIC_CYCLE",
        "run_id": run_id,
        "repository": os.getenv("GITHUB_REPOSITORY", "crownthrive1/CrownThrive-OS"),
        "commit": os.getenv("GITHUB_SHA", "unknown"),
        "trigger": os.getenv("GITHUB_EVENT_NAME", "local"),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "state": state,
        "agents": AGENTS,
        "contracts": contracts,
        "authority": {
            "mode": "hybrid_bounded",
            "economic_activation": "THRIVEEVERGREEN_ECAC_ONLY",
            "legal_ownership": "HUMAN_GATED",
            "destructive_operations": "HUMAN_GATED",
            "secrets": "VAULT_ONLY",
            "self_certification": "PROHIBITED",
        },
    }
    raw = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    packet["event_hash"] = sha256_bytes(raw)
    (out / "run_id").write_text(str(run_id))
    (out / "state").write_text(state)
    (out / "dail-event.json").write_text(json.dumps(packet, indent=2) + "\n")
    (out / "manifest.sha256").write_text(sha256_bytes((out / "dail-event.json").read_bytes()) + "  dail-event.json\n")

def agent_run(agent: str, run_id: str, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    if agent not in AGENTS:
        raise SystemExit(f"unknown agent: {agent}")
    roles = {
        "rnd": "research_and_candidate_generation",
        "documentation": "public_safe_documentation_projection",
        "rights_identity": "identity_rights_and_fingerprint_reconciliation",
        "compliance_oracle": "policy_evidence_and_compliance_assurance",
        "commercial": "commercial_candidate_packaging_without_economic_activation",
        "mesh_reliability": "route_observation_and_redundancy_assurance",
        "continuity": "seven_generation_continuity_and_recovery_assurance",
        "maintenance": "drift_detection_repair_and_retirement_preparation",
    }
    result = {
        "schema": "dail.chlom.agent-event.v1",
        "run_id": run_id,
        "agent": agent,
        "mission": roles[agent],
        "state": "OBSERVED_CANDIDATE",
        "autonomy": "A3_BOUNDED",
        "actions": ["observe", "classify", "prepare", "verify", "report"],
        "prohibited": ["transfer_ownership", "create_legal_authority", "activate_unapproved_commerce", "export_secrets", "self_certify", "self_merge_protected_change", "destroy_canonical_evidence"],
        "evidence": "runtime-contract-observation",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["event_hash"] = sha256_bytes(raw)
    (out / f"{agent}.json").write_text(json.dumps(result, indent=2) + "\n")

def reconcile(run_id: str, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    summary = [
        "## CHLOM Runtime Fabric Reconciliation",
        "",
        f"- Fabric run: `{run_id}`",
        "- Agent lanes: R&D, Documentation, Rights/Identity, Compliance Oracle, Commercial, Mesh Reliability, Continuity, Maintenance",
        "- DAIL mode: immutable evidence packet generated as a workflow artifact",
        "- Commercial authority: ThriveEvergreen / ECAC remains authoritative",
        "- Runtime mode: hybrid, bounded, fail-closed",
        "- Autonomous scope: observation, reconciliation, research, documentation, testing, candidate generation and bounded maintenance",
        "- Human gates: legal authority, ownership, destructive operations, privileged credentials, production economic activation and certification",
        "",
        "A successful workflow run is evidence that the controller executed. It is not by itself evidence that external APIs, MCP servers, vaults, payment systems, or public-child deployments are live.",
    ]
    (out / "summary.md").write_text("\n".join(summary) + "\n")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run"); p.add_argument("--output", required=True)
    p = sub.add_parser("agent"); p.add_argument("--agent", required=True); p.add_argument("--run-id", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("reconcile"); p.add_argument("--run-id", required=True); p.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.cmd == "run": run_controller(Path(args.output))
    elif args.cmd == "agent": agent_run(args.agent, args.run_id, Path(args.output))
    else: reconcile(args.run_id, Path(args.output))

if __name__ == "__main__":
    main()
