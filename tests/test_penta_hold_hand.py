import copy
import unittest

from runtime.penta_hold_hand import (
    HoldHandError,
    PENTA_LAYERS,
    REQUIRED_PREDICATES,
    evaluate_agentic_case,
    evaluate_hold,
)


HEAD = "a" * 40
BASE = {
    "campaign_id": "ct.penta.flow-control.20260826.v1",
    "hold_evidence_sha256": "b" * 64,
    "exact_head_sha": HEAD,
    "producer_ids": ["penta-runtime", "penta-build"],
    "observations": [
        {
            "predicate": predicate,
            "status": "PASS",
            "producer_id": f"independent-{predicate}",
            "evidence_sha256": str(index + 1).zfill(64),
            "exact_head_sha": HEAD,
            "independent": True,
        }
        for index, predicate in enumerate(REQUIRED_PREDICATES)
    ],
}


class PentaHoldHandTests(unittest.TestCase):
    def test_missing_evidence_keeps_hand_raised_and_routes_help(self):
        packet = copy.deepcopy(BASE)
        packet["observations"] = []
        decision = evaluate_hold(packet)
        self.assertEqual(decision["hand_state"], "RAISED")
        self.assertTrue(decision["hand_remains_visible"])
        self.assertEqual(len(decision["remediation_actions"]), len(REQUIRED_PREDICATES))
        self.assertTrue(all("PentaHelp" in action["routes"] for action in decision["remediation_actions"]))
        self.assertFalse(decision["certified"])

    def test_all_independent_exact_head_evidence_is_resolution_ready_only(self):
        decision = evaluate_hold(BASE)
        self.assertEqual(decision["hand_state"], "RESOLUTION_READY")
        self.assertTrue(decision["resolution_eligible"])
        self.assertFalse(decision["certified"])
        self.assertEqual(decision["next_gate"], "independent_resolution_receipt")

    def test_producer_self_pass_cannot_lower_hand(self):
        packet = copy.deepcopy(BASE)
        packet["observations"][0]["producer_id"] = "penta-runtime"
        decision = evaluate_hold(packet)
        self.assertEqual(decision["hand_state"], "RAISED")
        self.assertEqual(decision["predicates"][REQUIRED_PREDICATES[0]], "HOLD")

    def test_stale_head_evidence_is_ignored(self):
        packet = copy.deepcopy(BASE)
        packet["observations"][0]["exact_head_sha"] = "c" * 40
        decision = evaluate_hold(packet)
        self.assertEqual(decision["predicates"][REQUIRED_PREDICATES[0]], "UNKNOWN")
        self.assertEqual(decision["hand_state"], "RAISED")

    def test_invalid_evidence_digest_fails_closed(self):
        packet = copy.deepcopy(BASE)
        packet["observations"][0]["evidence_sha256"] = "not-a-digest"
        with self.assertRaises(HoldHandError):
            evaluate_hold(packet)


class PentaAgenticHoldTests(unittest.TestCase):
    def packet(self):
        agents = {
            "DISCOVER": "ct.penta.agent.vergence",
            "GOVERN": "ct.penta.agent.security",
            "EXECUTE": "ct.penta.agent.orchestrator",
            "VERIFY": "ct.penta.agent.topologist",
            "PRESERVE": "ct.penta.agent.vergence",
        }
        return {
            "case_id": "case-1",
            "exact_head_sha": HEAD,
            "content_sha256": "d" * 64,
            "originator_id": "ct.penta.agent.flex",
            "risk_class": "D3",
            "active_founder_authority": True,
            "verified_baseline": True,
            "hold_predicates_ready": True,
            "layer_receipts": [
                {
                    "layer": layer,
                    "agent_id": agents[layer],
                    "disposition": "PASS",
                    "exact_head_sha": HEAD,
                    "content_sha256": "d" * 64,
                    "agent_active": True,
                    "self_approval": False,
                    "independent": layer == "VERIFY",
                }
                for layer in PENTA_LAYERS
            ],
        }

    def test_all_layers_make_additive_resolution_eligible_only(self):
        decision = evaluate_agentic_case(self.packet())
        self.assertTrue(decision["resolution_eligible"])
        self.assertEqual(decision["hand_state"], "AGENTIC_RESOLUTION_READY")
        self.assertFalse(decision["certified"])
        self.assertFalse(decision["runtime_activated"])

    def test_missing_layer_keeps_hand_raised(self):
        packet = self.packet()
        packet["layer_receipts"] = packet["layer_receipts"][:-1]
        decision = evaluate_agentic_case(packet)
        self.assertEqual(decision["hand_state"], "RAISED")
        self.assertIn("PRESERVE", decision["missing_layers"])

    def test_originator_cannot_approve(self):
        packet = self.packet()
        packet["layer_receipts"][0]["agent_id"] = packet["originator_id"]
        decision = evaluate_agentic_case(packet)
        self.assertFalse(decision["resolution_eligible"])
        self.assertIn("DISCOVER", decision["missing_layers"])

    def test_stale_head_receipt_is_rejected(self):
        packet = self.packet()
        packet["layer_receipts"][0]["exact_head_sha"] = "c" * 40
        self.assertFalse(evaluate_agentic_case(packet)["resolution_eligible"])

    def test_one_agent_cannot_fill_all_layers(self):
        packet = self.packet()
        for receipt in packet["layer_receipts"]:
            receipt["agent_id"] = "ct.penta.agent.security"
        decision = evaluate_agentic_case(packet)
        self.assertFalse(decision["resolution_eligible"])
        self.assertEqual(decision["distinct_approvers"], 1)

    def test_d3_without_active_founder_binding_fails_closed(self):
        packet = self.packet()
        packet["active_founder_authority"] = False
        decision = evaluate_agentic_case(packet)
        self.assertFalse(decision["resolution_eligible"])
        self.assertTrue(any("founder authority" in reason for reason in decision["reasons"]))


if __name__ == "__main__":
    unittest.main()
