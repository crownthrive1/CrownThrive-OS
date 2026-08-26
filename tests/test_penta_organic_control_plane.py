import copy
import json
from pathlib import Path
import unittest

from penta.organic.body import OrganicControlPlane, OrganicError


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "penta/organic/contract.v1.json").read_text())
SIGNAL = json.loads((ROOT / "penta/organic/signal.example.json").read_text())


class OrganicControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.body = OrganicControlPlane(CONTRACT)

    def test_vault_identity_and_command_center_projection(self):
        event = self.body.ingest(SIGNAL, observed_at="2026-08-26T00:00:00+00:00")
        self.assertEqual(event["governance_destination"], "PentaBrain")
        self.assertTrue(self.body.verify_spine())
        snapshot = self.body.command_center_snapshot()
        self.assertTrue(snapshot["spine_integrity"])
        encoded = json.dumps(snapshot).lower()
        self.assertNotIn("private_key", encoded)
        self.assertNotIn("signature_ref", encoded)

    def test_ip_identity_and_private_material_fail_closed(self):
        for identity in (
            {"vault_id": "vault:192.0.2.1", "public_key_fingerprint": SIGNAL["identity"]["public_key_fingerprint"]},
            {**SIGNAL["identity"], "private_key": "never"},
        ):
            signal = copy.deepcopy(SIGNAL)
            signal["identity"] = identity
            with self.assertRaises(OrganicError):
                self.body.ingest(signal)

    def test_governance_plane_routes_amendment_and_adjudication(self):
        for signal_type, destination in (
            ("amendment_candidate", "PentaLegislature"),
            ("adjudication_case", "PentaJudicial"),
            ("authorized_execution", "PentaExecutive"),
        ):
            signal = copy.deepcopy(SIGNAL)
            signal["signal_id"] = "ct.signal." + signal_type
            signal["signal_type"] = signal_type
            event = self.body.ingest(signal, observed_at="2026-08-26T00:00:00+00:00")
            self.assertEqual(event["governance_destination"], destination)

    def test_health_load_cost_growth_and_recession(self):
        cases = [
            (0.1, 0.1, 10, 0.8, 2, "quarantine_and_recover"),
            (0.9, 0.9, 10, 0.8, 2, "shed_and_rebalance_load"),
            (0.9, 0.2, 150, 0.8, 2, "recede_noncritical_capacity"),
            (0.9, 0.65, 10, 0.8, 2, "grow_capacity"),
            (0.9, 0.1, 10, 0.8, 2, "recede_with_reserve"),
            (0.9, 0.4, 10, 0.8, 1, "restore_redundancy"),
        ]
        for index, (health, load, cost, capacity, redundancy, expected) in enumerate(cases):
            signal = copy.deepcopy(SIGNAL)
            signal["signal_id"] = f"ct.signal.case.{index}"
            signal["organ"].update(health=health, load=load, cost=cost, capacity=capacity, redundancy=redundancy)
            event = self.body.ingest(signal, observed_at="2026-08-26T00:00:00+00:00")
            self.assertEqual(event["assessment"]["disposition"], expected)

    def test_load_1000_signals_preserves_spine_and_learning(self):
        for index in range(1000):
            signal = copy.deepcopy(SIGNAL)
            signal["signal_id"] = f"ct.signal.load.{index}"
            signal["organ"]["load"] = (index % 70) / 100
            self.body.ingest(signal, observed_at=f"2026-08-26T00:{index % 60:02d}:00+00:00")
        self.assertTrue(self.body.verify_spine())
        self.assertEqual(self.body.learning["PentaRunners"]["observations"], 1000)
        self.assertEqual(self.body.command_center_snapshot()["event_count"], 1000)

    def test_spine_tampering_is_detected(self):
        self.body.ingest(SIGNAL, observed_at="2026-08-26T00:00:00+00:00")
        self.body.events[0]["assessment"]["disposition"] = "fabricated"
        self.assertFalse(self.body.verify_spine())


if __name__ == "__main__":
    unittest.main()
