#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "developers/manifests/whole-estate-project-diagnostics.v1.json").read_text())

assert manifest["generation"] == 7
assert manifest["state"] == "CONTROLLED_TEST_GOVERNED_HOLD"
assert manifest["phase"] == "2.99"
assert manifest["phase_3_advanced"] is False
assert manifest["sovereign_voters"] == [
    "ct.relay.agent-a",
    "ct.relay.agent-b",
    "ct.relay.agent-c",
    "ct.relay.agent-d",
    "ct.relay.agent-s",
]
assert manifest["d3_human_reserved"] is True
assert manifest["no_silent_delete"] is True
assert manifest["external_scheduler_slots_added"] == 0

initial = manifest["initial_diagnostic_run"]
assert initial["projects_scanned"] == sum(manifest["project_types"].values())
assert initial["handoffs_created"] == initial["issues_created"] - 1

deltas = manifest["post_scan_deltas"]
assert len(deltas) == 1
factory = deltas[0]
assert factory["scope"] == "concurrent_proprietary_factory_expansion"
assert factory["new_agent_created"] is False
assert factory["new_external_scheduler_slot"] is False
assert factory["owner_agent_id"] != factory["verifier_agent_id"]
observed = factory["observed"]
assert observed["factory_algorithms"] == observed["distinct_algorithm_ids"]
assert observed["duplicate_public_contract_digests"] == 0
assert observed["algorithms_runtime_enabled"] == 0
assert observed["public_implementation_reachable"] == 0
assert observed["explicit_algorithm_custody_rows"] <= observed["factory_algorithms"]

current = manifest["current_totals"]
assert current["issues"] == current["resolved"] + current["running"] + current["assigned"]
assert current["issues"] == initial["issues_created"] + sum(d["issues_created"] for d in deltas)
assert current["handoffs"] == initial["handoffs_created"] + sum(d["handoffs_created"] for d in deltas)

agents = manifest["project_agents"]
assert [a["agent_id"] for a in agents] == [
    "ct.project.agent.portfolio-auditor",
    "ct.project.agent.pr-convergence",
    "ct.project.agent.execution-enablement",
    "ct.agent.ecosystem-rollout-certifier",
]
for agent in agents:
    assert agent["authority_ceiling"] == "D2"
    assert agent["vote_eligible"] is False
    assert agent["scheduler_slot"] is False
    assert agent["did_uri"].startswith("did:chlom:agent:")
    assert agent["private_mapping"] is True
assert agents[1]["merge_authority"] is False
assert agents[2]["live_schedule_mutation"] is False
assert agents[3]["self_approval"] is False

algorithm = manifest["routing_algorithm"]
assert algorithm["algorithm_id"] == "ct.alg.gen7.pirs"
assert algorithm["classification"] == "PUBLIC_CONTRACT_RESTRICTED_IMPLEMENTATION"
assert len(algorithm["public_contract_digest"]) == 64
assert algorithm["implementation"] == "SUPABASE_VAULT_ONLY"
assert algorithm["person_scoring"] is False
assert algorithm["d3_auto"] is False
assert algorithm["weights_exposed"] is False
assert algorithm["thresholds_exposed"] is False

invariants = manifest["execution_invariants"]
assert all(invariants.values())
assert manifest["authority_corrections"]["unauthorized_vote_eligible_remaining"] == 0
assert manifest["authority_corrections"]["internal_d3_remaining"] == 0
assert manifest["authority_corrections"]["history_preserved"] is True

budget = manifest["budget_semantics"]
assert budget["minus_one"] == "unlimited_local_ceiling"
assert budget["zero"] == "disabled"
assert budget["null"] == "unresolved_fail_closed"
assert budget["provider_throttles_and_billing_separate"] is True
assert budget["resolved_issue_count"] == 20

api = manifest["api_mcp"]
assert api["verify_jwt"] is True
assert len(api["edge_function_sha256"]) == 64
assert len(api["tools"]) == 7
assert manifest["schedule"]["new_external_task"] is False
assert manifest["schedule"]["target_wip"] == 4
assert manifest["schedule"]["hard_max_wip"] == 6

print("Whole-estate project diagnostics invariants: PASS")
