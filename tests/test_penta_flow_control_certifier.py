import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "penta_flow_control_certifier.py"


BASE = {
    "campaign_id": "ct.penta.flow-control.20260826.v1",
    "producer_ids": ["penta-build", "penta-runtime"],
    "release": {
        "repository": "crownthrive1/CrownThrive-OS",
        "commit_sha": "618fc84a503152d5075019272789c9694974e11a",
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
        "release_commit": "618fc84a503152d5075019272789c9694974e11a",
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
}


class FlowControlCertifierTests(unittest.TestCase):
    def test_complete_independent_evidence_certifies(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        decision, checks = verify(BASE)
        self.assertEqual(decision, "CERTIFIED")
        self.assertFalse([c for c in checks if c["status"] == "FAIL"])

    def test_missing_independent_receipt_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence.pop("independent_verifier_receipt")
        decision, checks = verify(evidence)
        self.assertEqual(decision, "NOT_CERTIFIED")
        self.assertTrue(any(c["check"] == "independent_receipt" for c in checks if c["status"] == "FAIL"))

    def test_same_verifier_as_producer_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence["independent_verifier_receipt"]["verifier_id"] = "penta-runtime"
        decision, checks = verify(evidence)
        self.assertEqual(decision, "NOT_CERTIFIED")
        self.assertTrue(any(c["check"] == "receipt.independence" for c in checks if c["status"] == "FAIL"))

    def test_enabled_adapter_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence["runtime_readback"]["adapter_enabled"] = True
        decision, checks = verify(evidence)
        self.assertEqual(decision, "NOT_CERTIFIED")

    def test_incomplete_rollback_cannot_certify(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from penta_flow_control_certifier import verify

        evidence = copy.deepcopy(BASE)
        evidence["rollback_readback"]["rollback_tested"] = False
        decision, checks = verify(evidence)
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


if __name__ == "__main__":
    unittest.main()
