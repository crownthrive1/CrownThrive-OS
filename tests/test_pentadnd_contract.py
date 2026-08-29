"""Contract tests for the public PentaDND COS V1 specification.

These tests use only the Python standard library so the public contract can be
validated in minimal CI environments.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "specs/cos-v1/pentadnd/pentadnd.manifest.v1.json"
TOPOLOGY_PATH = REPO_ROOT / "specs/cos-v1/pentadnd/virtual-network-topology.v1.json"
RECEIPT_SCHEMA_PATH = REPO_ROOT / "schemas/cos-v1/pentadnd/run-receipt.v1.schema.json"


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_manifest_identity_and_authority_are_bounded() -> None:
    manifest = _load(MANIFEST_PATH)
    assert manifest["system_id"] == "ct.penta.dnd.v1"
    assert manifest["protocol_id"] == "ct.protocol.pentadnd.scoped-maintenance.v1"
    assert manifest["authority"] == {
        "autonomy_class": "A2",
        "decision_ceiling": "D2",
        "d3_human_reserved": True,
        "vote_eligible": False,
        "self_approval_allowed": False,
        "money_movement_allowed": False,
        "rights_grant_allowed": False,
        "credential_export_allowed": False,
        "destructive_delete_allowed": False,
    }


def test_manifest_requires_exact_next_phase_and_completion_email() -> None:
    manifest = _load(MANIFEST_PATH)
    hourly = manifest["hourly_job"]
    assert hourly["job_id"] == "ct.job.cos-convergence.hourly.v1"
    assert hourly["context_id"] == "ct.context.sol-ultra.pro-hourly.v1"
    assert hourly["write_next_phase"] is True
    assert hourly["send_completion_email"] is True
    assert hourly["recipient"] == "contact@crownthrive.com"
    assert hourly["collision_safe"] is True


def test_four_resilience_lines_are_unique_and_ordered() -> None:
    manifest = _load(MANIFEST_PATH)
    lines = manifest["resilience_lines"]
    assert [line["class"] for line in lines] == ["hot", "warm", "cold_a", "cold_b"]
    assert [line["ordinal"] for line in lines] == [1, 2, 3, 4]
    assert len({line["line_id"] for line in lines}) == 4


def test_topology_uses_existing_penta_network_owners() -> None:
    topology = _load(TOPOLOGY_PATH)
    owners = topology["owners"]
    assert owners["connectivity"] == "ct.penta.wire"
    assert owners["routing"] == "ct.penta.route"
    assert owners["tunneling"] == "ct.penta.tun"
    assert owners["load"] == "ct.penta.load"
    assert owners["balancing"] == "ct.penta.balancer"
    assert owners["leases"] == "ct.penta.queue"
    assert owners["dnd"] == "ct.penta.dnd.v1"


def test_topology_contains_switches_router_gateway_and_failover_controller() -> None:
    topology = _load(TOPOLOGY_PATH)
    kinds = {node["kind"] for node in topology["nodes"]}
    assert {
        "virtual_switch",
        "virtual_router",
        "edge_gateway",
        "failover_controller",
        "health_sentinel",
    }.issubset(kinds)
    switches = [node for node in topology["nodes"] if node["kind"] == "virtual_switch"]
    assert len(switches) == 4


def test_dnd_is_scoped_and_does_not_default_to_global_maintenance() -> None:
    topology = _load(TOPOLOGY_PATH)
    policy = topology["dnd_failover_policy"]
    assert policy["scope_only"] is True
    assert policy["global_maintenance_default"] is False
    assert policy["preserve_p0_paths"] is True
    assert policy["ambiguous_mutation_retry"] is False


def test_receipt_schema_requires_next_phase_and_email_projection() -> None:
    schema = _load(RECEIPT_SCHEMA_PATH)
    required = set(schema["required"])
    assert "next_phase" in required
    assert "email_projection" in required
    assert "redundancy_state" in required
    assert schema["properties"]["email_projection"]["properties"]["recipient"]["const"] == (
        "contact@crownthrive.com"
    )


def test_no_silent_delete_is_a_contract_invariant() -> None:
    manifest = _load(MANIFEST_PATH)
    preservation = manifest["preservation"]
    assert preservation["no_silent_delete"] is True
    assert preservation["no_silent_overwrite"] is True
    assert preservation["archive_before_retirement"] is True
    assert preservation["supersession_pointer_required"] is True
    assert preservation["current_term_replacement"]["to"] == "Melanated"
    assert preservation["current_term_replacement"]["historical_source_text_preserved"] is True
