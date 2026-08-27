import copy
import unittest

from runtime.penta_hold_hand import HoldHandError, REQUIRED_PREDICATES, evaluate_hold


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


if __name__ == "__main__":
    unittest.main()
