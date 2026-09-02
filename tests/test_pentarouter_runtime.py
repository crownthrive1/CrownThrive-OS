from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.pentarouter_runtime import PentaRouterError, route_request, self_test, topology_inventory, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "runtime/pentarouter/pentarouter-system.v1.json"
SOURCE_SHA = "a" * 40


class PentaRouterRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.healthy = {
            "ct.node.pentarouter.primary": {"state": "healthy", "breaker": "closed", "capacity": 100},
            "ct.node.pentarouter.secondary": {"state": "healthy", "breaker": "closed", "capacity": 80},
            "ct.node.pentarouter.recovery": {"state": "healthy", "breaker": "closed", "capacity": 50},
        }

    def request(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "subject_id": "ct.test.subject",
            "operation": "system.status.read",
            "risk_class": "D0",
            "effect": "read",
            "requested_lane": "auto",
            "source_sha": SOURCE_SHA,
            "payload": {"test": True},
        }
        value.update(overrides)
        return value

    def test_manifest_is_valid_and_inventory_is_complete(self) -> None:
        self.assertEqual(validate_manifest(self.manifest), [])
        inventory = topology_inventory(self.manifest)
        self.assertEqual(inventory["planes"], 7)
        self.assertEqual(inventory["fabrics"], 6)
        self.assertEqual(inventory["bridges"], 7)
        self.assertEqual(inventory["meshes"], 6)
        self.assertEqual(inventory["nodes"], 6)
        self.assertEqual(inventory["router_nodes"], 3)
        self.assertEqual(inventory["lanes"], ["hot", "warm", "cold"])

    def test_hot_read_selects_primary_router(self) -> None:
        receipt = route_request(self.manifest, self.request(), self.healthy)
        self.assertEqual(receipt["state"], "ROUTE_READY")
        self.assertEqual(receipt["selected_lane"], "hot")
        self.assertEqual(receipt["selected_node_id"], "ct.node.pentarouter.primary")
        self.assertFalse(receipt["provider_execution_performed"])

    def test_secondary_router_preserves_hot_lane(self) -> None:
        health = dict(self.healthy)
        health["ct.node.pentarouter.primary"] = {"state": "unavailable", "breaker": "open", "capacity": 0}
        receipt = route_request(self.manifest, self.request(), health)
        self.assertEqual(receipt["selected_lane"], "hot")
        self.assertEqual(receipt["selected_node_id"], "ct.node.pentarouter.secondary")
        self.assertEqual(receipt["state"], "ROUTE_READY")

    def test_hot_fails_over_to_warm_after_hot_nodes_fail(self) -> None:
        health = dict(self.healthy)
        health["ct.node.pentarouter.primary"] = {"state": "unavailable", "breaker": "open", "capacity": 0}
        health["ct.node.pentarouter.secondary"] = {"state": "unavailable", "breaker": "open", "capacity": 0}
        receipt = route_request(self.manifest, self.request(), health)
        self.assertEqual(receipt["selected_lane"], "warm")
        self.assertEqual(receipt["selected_node_id"], "ct.node.pentarouter.recovery")
        self.assertEqual(receipt["state"], "DEGRADED_ROUTE_READY")
        self.assertTrue(receipt["fallback_used"])

    def test_warm_fails_over_to_cold(self) -> None:
        health = {
            "ct.node.pentarouter.primary": {"state": "unavailable", "breaker": "open", "capacity": 0},
            "ct.node.pentarouter.secondary": {"state": "unavailable", "breaker": "open", "capacity": 0},
            "ct.node.pentarouter.recovery": {"state": "healthy", "breaker": "closed", "capacity": 50},
        }
        request = self.request(
            operation="custom.write",
            risk_class="D2",
            effect="write",
            principal_id="did:crownthrive:test",
            idempotency_key="idem-1",
            dail_state="PASS",
            chlom_state="PASS",
        )
        manifest = json.loads(json.dumps(self.manifest))
        for node in manifest["nodes"]:
            if node["node_id"] == "ct.node.pentarouter.recovery":
                node["lanes"] = ["cold"]
        receipt = route_request(manifest, request, health)
        self.assertEqual(receipt["selected_lane"], "cold")
        self.assertEqual(receipt["state"], "DEGRADED_ROUTE_READY")

    def test_cold_failure_holds(self) -> None:
        health = {
            node_id: {"state": "unavailable", "breaker": "open", "capacity": 0}
            for node_id in self.healthy
        }
        receipt = route_request(self.manifest, self.request(operation="recovery.reconcile", effect="read"), health)
        self.assertEqual(receipt["state"], "HOLD_FAIL_CLOSED")
        self.assertIsNone(receipt["selected_node_id"])
        self.assertIn("cold", receipt["attempted_lanes"])

    def test_side_effect_requires_dail_chlom_principal_and_idempotency(self) -> None:
        receipt = route_request(
            self.manifest,
            self.request(operation="custom.write", risk_class="D2", effect="write"),
            self.healthy,
        )
        self.assertEqual(receipt["state"], "HOLD_FAIL_CLOSED")
        reasons = " ".join(receipt["hold_reasons"])
        self.assertIn("principal_id", reasons)
        self.assertIn("idempotency_key", reasons)
        self.assertIn("DAIL", reasons)
        self.assertIn("CHLOM", reasons)

    def test_d3_side_effect_requires_exact_human_authority(self) -> None:
        receipt = route_request(
            self.manifest,
            self.request(
                operation="commercial.license.accept",
                risk_class="D3",
                effect="rights",
                principal_id="did:crownthrive:test",
                idempotency_key="idem-d3",
                dail_state="PASS",
                chlom_state="PASS",
            ),
            self.healthy,
        )
        self.assertEqual(receipt["state"], "HOLD_FAIL_CLOSED")
        self.assertIn("human_authority_ref", " ".join(receipt["hold_reasons"]))

    def test_valid_d3_rights_route_is_readback_gated(self) -> None:
        receipt = route_request(
            self.manifest,
            self.request(
                operation="commercial.license.accept",
                risk_class="D3",
                effect="rights",
                principal_id="did:crownthrive:test",
                idempotency_key="idem-d3-ok",
                dail_state="PASS",
                chlom_state="PASS",
                human_authority_ref="ct.authority.human.test",
            ),
            self.healthy,
        )
        self.assertEqual(receipt["selected_lane"], "warm")
        self.assertTrue(receipt["provider_readback_required"])
        self.assertFalse(receipt["provider_execution_performed"])

    def test_money_route_requires_wallet_available(self) -> None:
        receipt = route_request(
            self.manifest,
            self.request(
                operation="commercial.wallet.intent.create",
                risk_class="D3",
                effect="money",
                principal_id="did:crownthrive:test",
                idempotency_key="idem-wallet",
                dail_state="PASS",
                chlom_state="PASS",
                human_authority_ref="ct.authority.human.test",
                wallet_state="UNAVAILABLE",
            ),
            self.healthy,
        )
        self.assertEqual(receipt["state"], "HOLD_FAIL_CLOSED")
        self.assertIn("wallet_state AVAILABLE", " ".join(receipt["hold_reasons"]))

    def test_hot_side_effect_is_prohibited(self) -> None:
        receipt = route_request(
            self.manifest,
            self.request(
                operation="custom.write",
                risk_class="D1",
                effect="write",
                requested_lane="hot",
                principal_id="did:crownthrive:test",
                idempotency_key="idem-hot-write",
                dail_state="PASS",
                chlom_state="PASS",
            ),
            self.healthy,
        )
        self.assertEqual(receipt["state"], "HOLD_FAIL_CLOSED")
        self.assertIn("hot lane cannot carry side effects", receipt["hold_reasons"])

    def test_secret_bearing_input_is_rejected(self) -> None:
        with self.assertRaises(PentaRouterError):
            route_request(self.manifest, self.request(payload={"access_token": "forbidden"}), self.healthy)

    def test_receipts_are_deterministic(self) -> None:
        request = self.request()
        self.assertEqual(
            route_request(self.manifest, request, self.healthy),
            route_request(self.manifest, request, self.healthy),
        )

    def test_contracts_and_survival_dimensions_are_present(self) -> None:
        route_contract = json.loads((ROOT / self.manifest["route_contract_ref"]).read_text(encoding="utf-8"))
        node_contract = json.loads((ROOT / self.manifest["node_contract_ref"]).read_text(encoding="utf-8"))
        survival = json.loads((ROOT / self.manifest["survival_contract_ref"]).read_text(encoding="utf-8"))
        self.assertFalse(route_contract["x-crownthrive-invariants"]["provider_execution_performed_by_router"])
        self.assertTrue(node_contract["x-crownthrive-no-provider-authority"])
        expected = {
            "persistent_identity",
            "persistent_state",
            "deterministic_functions",
            "queues",
            "leases",
            "recovery",
            "evidence",
            "authority_enforcement",
            "health_behavior",
            "model_degradation",
            "model_replacement",
            "restart_behavior",
        }
        self.assertEqual(set(survival["required_capabilities"]), expected)

    def test_existing_commercial_mesh_is_linked_not_duplicated(self) -> None:
        route = json.loads((ROOT / "commercialization/routing/mesh-routing.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(route["pentarouter_standard_ref"], "runtime/pentarouter/pentarouter-system.v1.json")
        self.assertEqual(self.manifest["commercialization_bridge_ref"], "commercialization/routing/mesh-routing.v1.json")

    def test_pentagreen_handoff_contains_only_source_tested_products(self) -> None:
        handoff = json.loads(
            (ROOT / "commercialization/pentagreen/pentarouter-stable-product-handoff.v1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(handoff["stable_products_only"])
        self.assertFalse(handoff["live_activation"])
        self.assertEqual(len(handoff["products"]), 3)
        self.assertTrue(all(product["stability_state"] == "SOURCE_TESTED" for product in handoff["products"]))
        self.assertTrue(all(product["activation_state"] == "HOLD" for product in handoff["products"]))

    def test_embedded_self_test_passes_without_provider_execution(self) -> None:
        result = self_test(self.manifest)
        self.assertEqual(result["determinism"], "PASS")
        self.assertFalse(result["provider_execution_performed"])


if __name__ == "__main__":
    unittest.main()
