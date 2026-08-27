import unittest

from runtime.penta_evi_builder import (
    AutonomyEnvelope,
    TestReceipt,
    build_bundle,
    build_repair_memory,
    certify_bundle,
)

HEAD = "a" * 40
OTHER = "b" * 40


def valid_bundle(authority="D2"):
    return build_bundle(
        work_order_id="wo-1",
        subject="repo-local repair",
        source_ref="issue:121",
        repo="crownthrive1/CrownThrive-OS",
        head_sha=HEAD,
        target_state="CONTROLLED_TEST",
        authority_level=authority,
        observations=[{"kind": "evidence_gap", "result": "observed"}],
        claims=[{"claim": "tests passed", "scope": "exact head"}],
        evidence_refs=["tests:test_penta_evi_builder"],
        test_receipts=[TestReceipt("unit", "PASS", "unittest")],
        rollback={"method": "git_revert", "target": HEAD},
        fallback={"method": "hold", "redundancy": "known-good-main"},
        created_at="2026-08-26T00:00:00Z",
    )


class PentaEVIBuilderTests(unittest.TestCase):
    def test_build_is_exact_head_and_unverified(self):
        bundle = valid_bundle()
        self.assertEqual(bundle["head_sha"], HEAD)
        self.assertEqual(bundle["certification_state"], "UNVERIFIED")
        self.assertFalse(bundle["production_promotion"])
        self.assertEqual(len(bundle["receipt_sha256"]), 64)

    def test_independent_verifier_can_pass_exact_head(self):
        decision = certify_bundle(valid_bundle(), verifier="penta.certify", current_head_sha=HEAD)
        self.assertEqual(decision["status"], "PASS")
        self.assertTrue(decision["independent_verifier"])
        self.assertFalse(decision["production_promotion_authorized"])

    def test_builder_cannot_self_certify(self):
        decision = certify_bundle(valid_bundle(), verifier="penta.evi-builder", current_head_sha=HEAD)
        self.assertEqual(decision["status"], "HOLD")
        self.assertIn("producer cannot independently certify its own evidence", decision["reasons"])

    def test_sha_drift_fails_closed(self):
        decision = certify_bundle(valid_bundle(), verifier="penta.certify", current_head_sha=OTHER)
        self.assertEqual(decision["status"], "HOLD")
        self.assertIn("certified head does not match current head", decision["reasons"])

    def test_missing_evidence_and_failed_test_fail_closed(self):
        bundle = valid_bundle()
        body = {k: v for k, v in bundle.items() if k != "receipt_sha256"}
        body["evidence_refs"] = []
        body["test_receipts"] = [{"name": "unit", "status": "FAIL", "source": "unittest", "details": ""}]
        from runtime.penta_evi_builder import sha256_json
        body["receipt_sha256"] = sha256_json(body)
        decision = certify_bundle(body, verifier="penta.certify", current_head_sha=HEAD)
        self.assertEqual(decision["status"], "HOLD")
        self.assertIn("evidence references are required", decision["reasons"])
        self.assertIn("one or more required tests did not pass", decision["reasons"])

    def test_d3_requires_human_gate(self):
        decision = certify_bundle(valid_bundle("D3"), verifier="penta.certify", current_head_sha=HEAD)
        self.assertEqual(decision["status"], "HOLD")
        passed = certify_bundle(valid_bundle("D3"), verifier="penta.certify", current_head_sha=HEAD, human_gate=True)
        self.assertEqual(passed["status"], "PASS")

    def test_forbidden_autonomy_grants_rejected(self):
        with self.assertRaises(ValueError):
            AutonomyEnvelope(permit_self_certification=True).validate()

    def test_receipt_tamper_detected(self):
        bundle = valid_bundle()
        bundle["claims"][0]["claim"] = "tampered"
        decision = certify_bundle(bundle, verifier="penta.certify", current_head_sha=HEAD)
        self.assertEqual(decision["status"], "HOLD")
        self.assertIn("evidence receipt digest mismatch", decision["reasons"])

    def test_repair_memory_is_advisory(self):
        bundle = valid_bundle()
        memory = build_repair_memory(
            weakness_fingerprint="weakness-1",
            recipe={"handler": "patch_known_code"},
            evidence_receipt_sha256=bundle["receipt_sha256"],
            successful_head_sha=HEAD,
        )
        self.assertTrue(memory["advisory_only"])
        self.assertTrue(memory["requires_retest"])
        self.assertFalse(memory["grants_authority"])


if __name__ == "__main__":
    unittest.main()
