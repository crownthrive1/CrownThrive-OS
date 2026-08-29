from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "specs/cos-v1/pentadnd/pentadnd.manifest.v1.json"
TOPOLOGY = ROOT / "specs/cos-v1/pentadnd/virtual-network-topology.v1.json"
RECEIPT_SCHEMA = ROOT / "schemas/cos-v1/pentadnd/run-receipt.v1.schema.json"
README = ROOT / "docs/cos-v1/pentadnd/README.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class PentaDNDContractTests(unittest.TestCase):
    def test_identity_and_authority_are_bounded(self) -> None:
        manifest = load(MANIFEST)
        self.assertEqual(manifest["system_id"], "ct.penta.dnd.v1")
        self.assertEqual(manifest["protocol_id"], "ct.protocol.pentadnd.scoped-maintenance.v1")
        self.assertEqual(manifest["context_id"], "ct.context.sol-ultra.pro-hourly.v1")
        authority = manifest["authority"]
        self.assertEqual(authority["autonomy_class"], "A2")
        self.assertEqual(authority["decision_ceiling"], "D2")
        self.assertTrue(authority["d3_human_reserved"])
        self.assertFalse(authority["self_approval_allowed"])
        self.assertFalse(authority["money_movement_allowed"])
        self.assertFalse(authority["rights_grant_allowed"])
        self.assertFalse(authority["credential_export_allowed"])
        self.assertFalse(authority["destructive_delete_allowed"])

    def test_hourly_pass_requires_next_phase_and_email(self) -> None:
        hourly = load(MANIFEST)["hourly_job"]
        self.assertEqual(hourly["database_primary_schedule"], "17 * * * *")
        self.assertEqual(hourly["github_warm_fallback_schedule"], "23 * * * *")
        self.assertTrue(hourly["collision_safe"])
        self.assertTrue(hourly["write_next_phase"])
        self.assertTrue(hourly["send_completion_email"])
        self.assertEqual(hourly["recipient"], "contact@crownthrive.com")

    def test_four_lines_are_unique_and_ordered(self) -> None:
        lines = load(MANIFEST)["resilience_lines"]
        self.assertEqual([line["class"] for line in lines], ["hot", "warm", "cold_a", "cold_b"])
        self.assertEqual([line["ordinal"] for line in lines], [1, 2, 3, 4])
        self.assertEqual(len({line["line_id"] for line in lines}), 4)

    def test_topology_uses_existing_penta_network_family(self) -> None:
        topology = load(TOPOLOGY)
        owners = topology["owners"]
        self.assertEqual(owners["connectivity"], "ct.penta.wire")
        self.assertEqual(owners["routing"], "ct.penta.route")
        self.assertEqual(owners["tunneling"], "ct.penta.tun")
        self.assertEqual(owners["load"], "ct.penta.load")
        self.assertEqual(owners["balancing"], "ct.penta.balancer")
        self.assertEqual(owners["leases"], "ct.penta.queue")
        self.assertEqual(owners["dnd"], "ct.penta.dnd.v1")

    def test_switch_router_gateway_and_failover_nodes_exist(self) -> None:
        nodes = load(TOPOLOGY)["nodes"]
        kinds = {node["kind"] for node in nodes}
        self.assertTrue({"virtual_switch", "virtual_router", "edge_gateway", "failover_controller", "health_sentinel"}.issubset(kinds))
        self.assertEqual(sum(node["kind"] == "virtual_switch" for node in nodes), 4)

    def test_scope_only_and_no_ambiguous_retry(self) -> None:
        policy = load(TOPOLOGY)["dnd_failover_policy"]
        self.assertTrue(policy["scope_only"])
        self.assertFalse(policy["global_maintenance_default"])
        self.assertTrue(policy["preserve_p0_paths"])
        self.assertFalse(policy["ambiguous_mutation_retry"])
        self.assertTrue(policy["read_only_planning_when_redundancy_unverified"])

    def test_receipt_requires_four_lines_next_phase_and_email(self) -> None:
        schema = load(RECEIPT_SCHEMA)
        required = set(schema["required"])
        self.assertTrue({"redundancy_state", "next_phase", "email_projection", "evidence"}.issubset(required))
        self.assertEqual(schema["properties"]["email_projection"]["properties"]["recipient"]["const"], "contact@crownthrive.com")
        self.assertEqual(set(schema["properties"]["redundancy_state"]["required"]), {"hot", "warm", "cold_a", "cold_b"})

    def test_no_silent_delete_and_melanated_successor_policy(self) -> None:
        preservation = load(MANIFEST)["preservation"]
        self.assertTrue(preservation["no_silent_delete"])
        self.assertTrue(preservation["no_silent_overwrite"])
        self.assertTrue(preservation["archive_before_retirement"])
        self.assertTrue(preservation["supersession_pointer_required"])
        replacement = preservation["current_term_replacement"]
        self.assertEqual(replacement["from"], "Kulture")
        self.assertEqual(replacement["to"], "Melanated")
        self.assertTrue(replacement["historical_source_text_preserved"])

    def test_document_does_not_claim_current_production(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("implementation candidate", text)
        self.assertIn("pending migration, canaries, independent certification and production readback", text)


if __name__ == "__main__":
    unittest.main()
