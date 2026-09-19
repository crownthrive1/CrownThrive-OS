from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from governed_current_pr_preflight_v2 import validate_legacy_readiness_payload


class LegacyReadinessBootstrapTests(unittest.TestCase):
    def packet(self):
        return {
            "schema": "ct.penta.pr.self-certification.v1",
            "originator_identity": "ct.originator",
            "self_certifier_identity": "ct.originator",
            "self_certification_state": "SELF_CERTIFIED",
            "provider_results_manufactured": False,
            "required_gate_bypass": False,
            "final_institutional_certification_state": "PENDING_REQUIRED_GATES_READBACK_AND_DAIL",
            "dail_binding_state": "REQUIRED_BEFORE_INSTITUTIONAL_CERTIFICATION",
        }

    def receipt(self):
        return {
            "schema": "crownthrive.penta.serialized.git-receipt/v1",
            "self_certification": {
                "state": "SELF_CERTIFIED",
                "originator": "ct.originator",
                "provider_results_manufactured": False,
                "final_gate_bypassed": False,
            },
        }

    def test_legacy_packet_is_downgraded_to_zero_authority_readiness(self):
        result = validate_legacy_readiness_payload(self.packet(), self.receipt())
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["canonical_semantics"], "originator_readiness_evidence")
        self.assertFalse(result["independent_certification"])
        self.assertFalse(result["authority_created"])
        self.assertFalse(result["merge_authority"])
        self.assertFalse(result["release_authority"])
        self.assertTrue(result["requires_pentacertifier"])

    def test_provider_truth_manufacture_fails_closed(self):
        packet = self.packet()
        packet["provider_results_manufactured"] = True
        with self.assertRaises(ValueError):
            validate_legacy_readiness_payload(packet, self.receipt())

    def test_gate_bypass_fails_closed(self):
        packet = self.packet()
        packet["required_gate_bypass"] = True
        with self.assertRaises(ValueError):
            validate_legacy_readiness_payload(packet, self.receipt())

    def test_identity_mismatch_fails_closed(self):
        packet = self.packet()
        packet["self_certifier_identity"] = "ct.other"
        with self.assertRaises(ValueError):
            validate_legacy_readiness_payload(packet, self.receipt())

    def test_authority_claim_fails_closed(self):
        for field in ("independent_certification", "authority_created", "merge_authority", "release_authority"):
            with self.subTest(field=field):
                packet = self.packet()
                packet[field] = True
                with self.assertRaises(ValueError):
                    validate_legacy_readiness_payload(packet, self.receipt())

    def test_final_certification_must_remain_pending(self):
        packet = self.packet()
        packet["final_institutional_certification_state"] = "CERTIFIED"
        with self.assertRaises(ValueError):
            validate_legacy_readiness_payload(packet, self.receipt())

    def test_dail_must_remain_pending(self):
        packet = self.packet()
        packet["dail_binding_state"] = "BOUND"
        with self.assertRaises(ValueError):
            validate_legacy_readiness_payload(packet, self.receipt())

    def test_receipt_provider_truth_and_bypass_fail_closed(self):
        for field in ("provider_results_manufactured", "final_gate_bypassed"):
            with self.subTest(field=field):
                receipt = self.receipt()
                receipt["self_certification"][field] = True
                with self.assertRaises(ValueError):
                    validate_legacy_readiness_payload(self.packet(), receipt)

    def test_partial_canonical_semantics_cannot_use_legacy_bridge(self):
        packet = self.packet()
        packet["canonical_semantics"] = "some_other_semantics"
        with self.assertRaises(ValueError):
            validate_legacy_readiness_payload(packet, self.receipt())


if __name__ == "__main__":
    unittest.main()
