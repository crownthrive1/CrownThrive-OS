import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from penta_release_topology_certifier import verify  # noqa: E402

COMMIT = "9" * 40
ROLLBACK = "8" * 40
SHA = "a" * 64


def receipt(actor, *, semantic_stage, decision_key="state"):
    value = {
        "actor_id": actor,
        "exact_version_ref": COMMIT,
        "semantic_stage": semantic_stage,
        "evidence_ref": f"dail://release/{actor}",
        "evidence_sha256": SHA,
    }
    value[decision_key] = "PASS"
    return value


BASE = {
    "release": {
        "repository": "crownthrive1/CrownThrive-OS",
        "commit_sha": COMMIT,
        "risk_class": "D2",
    },
    "originator_id": "ct.agent.builder",
    "producer_ids": ["ct.agent.builder"],
    "stages": {
        "build": receipt("ct.agent.builder", semantic_stage="evidence"),
        "security_scan": receipt("ct.agent.scan", semantic_stage="evidence"),
        "threat_model": receipt("ct.agent.threat", semantic_stage="evidence"),
        "tests": receipt("ct.agent.test", semantic_stage="evidence"),
    },
    "penta_security_decision": receipt(
        "ct.penta.security", semantic_stage="decision", decision_key="decision"
    ),
    "chlom_authority_rights_decision": {
        **receipt("ct.chlom.authority", semantic_stage="decision", decision_key="decision"),
        "rights_check": "PASS",
        "authority_check": "PASS",
        "authority_expansion": False,
        "final_legal_or_rights_commitment": False,
    },
    "cie": {"required": False},
    "penta_certifier_receipt": receipt(
        "ct.penta.certifier", semantic_stage="decision", decision_key="decision"
    ),
    "rollback": {
        "rollback_ref": ROLLBACK,
        "bounded": True,
        "tested": True,
        "readback_verified": True,
    },
    "token_model": "UNRESOLVED",
}


class ReleaseTopologyCertifierTests(unittest.TestCase):
    def test_complete_independent_pre_release_topology_is_eligible(self):
        decision, checks = verify(BASE, phase="pre_release")
        self.assertEqual(decision, "PRE_RELEASE_ELIGIBLE")
        self.assertFalse([item for item in checks if item["status"] == "FAIL"])

    def test_complete_post_release_topology_is_verified(self):
        evidence = copy.deepcopy(BASE)
        evidence["release_execution"] = receipt(
            "ct.penta.release", semantic_stage="execution"
        )
        decision, checks = verify(evidence, phase="post_release")
        self.assertEqual(decision, "POST_RELEASE_VERIFIED")
        self.assertFalse([item for item in checks if item["status"] == "FAIL"])

    def test_missing_pentacertifier_fails_closed(self):
        evidence = copy.deepcopy(BASE)
        evidence.pop("penta_certifier_receipt")
        decision, checks = verify(evidence, phase="pre_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(
            any(x["check"] == "penta_certifier" for x in checks if x["status"] == "FAIL")
        )

    def test_originator_cannot_self_certify(self):
        evidence = copy.deepcopy(BASE)
        evidence["penta_certifier_receipt"]["actor_id"] = evidence["originator_id"]
        decision, checks = verify(evidence, phase="pre_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(
            any(
                x["check"] == "penta_certifier.independence"
                for x in checks
                if x["status"] == "FAIL"
            )
        )

    def test_required_cie_without_decision_fails_closed(self):
        evidence = copy.deepcopy(BASE)
        evidence["cie"] = {"required": True}
        decision, checks = verify(evidence, phase="pre_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(any(x["check"] == "cie" for x in checks if x["status"] == "FAIL"))

    def test_exact_head_drift_fails_closed(self):
        evidence = copy.deepcopy(BASE)
        evidence["stages"]["tests"]["exact_version_ref"] = "7" * 40
        decision, checks = verify(evidence, phase="pre_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(
            any(
                x["check"] == "stage.tests.exact_version"
                for x in checks
                if x["status"] == "FAIL"
            )
        )

    def test_pre_release_fails_if_execution_already_exists(self):
        evidence = copy.deepcopy(BASE)
        evidence["release_execution"] = receipt(
            "ct.penta.release", semantic_stage="execution"
        )
        decision, checks = verify(evidence, phase="pre_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(
            any(
                x["check"] == "release_execution.premature"
                for x in checks
                if x["status"] == "FAIL"
            )
        )

    def test_post_release_requires_execution(self):
        decision, checks = verify(BASE, phase="post_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(
            any(
                x["check"] == "release_execution"
                for x in checks
                if x["status"] == "FAIL"
            )
        )

    def test_certifier_cannot_also_execute_release(self):
        evidence = copy.deepcopy(BASE)
        evidence["release_execution"] = receipt(
            "ct.penta.certifier", semantic_stage="execution"
        )
        decision, checks = verify(evidence, phase="post_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(
            any(
                x["check"] == "release_execution.independence"
                for x in checks
                if x["status"] == "FAIL"
            )
        )

    def test_d3_requires_exact_human_reserved_approval(self):
        evidence = copy.deepcopy(BASE)
        evidence["release"]["risk_class"] = "D3"
        decision, checks = verify(evidence, phase="pre_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(
            any(x["check"] == "d3.approval" for x in checks if x["status"] == "FAIL")
        )

    def test_dail_semantic_stage_is_not_token_model(self):
        evidence = copy.deepcopy(BASE)
        evidence["token_model"] = {"classes": ["evidence", "decision", "execution"]}
        decision, checks = verify(evidence, phase="pre_release")
        self.assertEqual(decision, "RELEASE_HOLD")
        self.assertTrue(
            any(x["check"] == "token_model" for x in checks if x["status"] == "FAIL")
        )

    def test_unknown_phase_is_rejected(self):
        with self.assertRaises(ValueError):
            verify(BASE, phase="unknown")


if __name__ == "__main__":
    unittest.main()
