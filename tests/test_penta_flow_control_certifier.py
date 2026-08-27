import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "penta_flow_control_certifier.py"
sys.path.insert(0, str(ROOT / "runtime"))
from penta_d3_approval import BASE_RELEASE_GATES  # noqa: E402


NOW = datetime(2026, 8, 27, 17, 0, tzinfo=timezone.utc)
COMMIT = "9" * 40
CONTENT_SHA = "8" * 64


def d3_gate(key):
    value = {
        "state": "PASS",
        "evidence_ref": f"dail://flow-control/{key}",
        "evidence_sha256": "7" * 64,
        "exact_version_ref": COMMIT,
        "content_sha256": CONTENT_SHA,
        "verified_by": "ct.penta.agent.vergence",
        "verified_at": "2026-08-27T16:59:00Z",
    }
    if key == "rollback_readback":
        value.update(
            {
                "rollback_tested": True,
                "baseline_sha256": "6" * 64,
                "post_rollback_sha256": "6" * 64,
            }
        )
    return value


BASE = {
    "campaign_id": "ct.penta.flow-control.20260826.v1",
    "producer_ids": ["penta-build", "penta-runtime"],
    "release": {
        "repository": "crownthrive1/CrownThrive-OS",
        "commit_sha": COMMIT,
    },
    "binding": {
        "max_concurrency": 4,
        "max_claim_batch": 8,
        "max_cost_minor": 0,
        "max_internal_units": 1000000,
        "independent_evidence_required": True,
        "provider_write_authority": False,
        "money_movement_authority": False,
        "rights_disposition_authority": False,
        "credential_authority": False,
        "nonrenewing": True,
    },
    "runtime_readback": {
        "adapter_enabled": False,
        "provider_jobs_released": False,
        "paid_cost_minor": 0,
        "readback_verified": True,
    },
    "independent_verifier_receipt": {
        "receipt_id": "vr-test-001",
        "verifier_id": "independent-verifier-01",
        "campaign_id": "ct.penta.flow-control.20260826.v1",
        "release_commit": COMMIT,
        "decision": "PASS",
        "evidence_sha256": "a" * 64,
    },
    "rollback_readback": {
        "baseline_sha": "b" * 64,
        "rollback_tested": True,
        "pre_rollback_readback_sha": "c" * 64,
        "post_rollback_readback_sha": "b" * 64,
        "post_rollback_matches_baseline": True,
    },
    "d3_approval": {
        "window": {
            "window_id": "ct.d3.founder-production-window.20260827.v1",
            "founder_ref": "ct.person.founder.kavonte-jones-sr",
            "risk_class": "D3",
            "approval_effect": "human_approval_predicate_only",
            "starts_at": "2026-08-27T01:23:52.144189Z",
            "expires_at": "2026-09-10T01:23:52.144189Z",
            "nonrenewing": True,
            "exact_candidate_required": True,
            "independent_evidence_required": True,
            "independent_evidence_substitution_allowed": False,
            "revoked": False,
        },
        "candidate": {
            "subject_ref": "ct.penta.flow-control.20260826.v1",
            "risk_class": "D3",
            "environment": "production",
            "action_class": "production_release",
            "exact_version_ref": COMMIT,
            "content_sha256": CONTENT_SHA,
            "producer_ref": "penta-runtime",
            "requested_effects": [],
        },
        "gates": {key: d3_gate(key) for key in BASE_RELEASE_GATES},
    },
}


class FlowControlCertifierTests(unittest.TestCase):
    def test_complete_independent_evidence_certifies(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        decision, checks = verify(BASE, now=NOW)
        self.assertEqual(decision, "CERTIFIED")
        self.assertFalse([c for c in checks if c["status"] == "FAIL"])

    def test_missing_independent_receipt_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence.pop("independent_verifier_receipt")
        decision, checks = verify(evidence, now=NOW)
        self.assertEqual(decision, "NOT_CERTIFIED")
        self.assertTrue(any(c["check"] == "independent_receipt" for c in checks if c["status"] == "FAIL"))

    def test_same_verifier_as_producer_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence["independent_verifier_receipt"]["verifier_id"] = "penta-runtime"
        decision, checks = verify(evidence, now=NOW)
        self.assertEqual(decision, "NOT_CERTIFIED")
        self.assertTrue(any(c["check"] == "receipt.independence" for c in checks if c["status"] == "FAIL"))

    def test_enabled_adapter_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence["runtime_readback"]["adapter_enabled"] = True
        decision, checks = verify(evidence, now=NOW)
        self.assertEqual(decision, "NOT_CERTIFIED")

    def test_incomplete_rollback_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence["rollback_readback"]["rollback_tested"] = False
        decision, checks = verify(evidence, now=NOW)
        self.assertEqual(decision, "NOT_CERTIFIED")

    def test_cli_returns_nonzero_for_missing_receipt(self):
        evidence = copy.deepcopy(BASE)
        evidence.pop("independent_verifier_receipt")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "evidence.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NOT_CERTIFIED", result.stdout)

    def test_missing_d3_window_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence.pop("d3_approval")
        decision, checks = verify(evidence, now=NOW)
        self.assertEqual(decision, "NOT_CERTIFIED")
        self.assertTrue(any(c["check"] == "d3.approval" for c in checks if c["status"] == "FAIL"))

    def test_d3_candidate_must_match_release_commit(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence["d3_approval"]["candidate"]["exact_version_ref"] = "5" * 40
        decision, checks = verify(evidence, now=NOW)
        self.assertEqual(decision, "NOT_CERTIFIED")
        self.assertTrue(any(c["check"] == "d3.exact_release" for c in checks if c["status"] == "FAIL"))

    def test_rollback_digest_must_match_baseline(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence["rollback_readback"]["post_rollback_readback_sha"] = "d" * 64
        decision, checks = verify(evidence, now=NOW)
        self.assertEqual(decision, "NOT_CERTIFIED")
        self.assertTrue(any(c["check"] == "rollback.digest_readback" for c in checks if c["status"] == "FAIL"))


if __name__ == "__main__":
    unittest.main()
