"""Regression and live-repository certification tests for Penta interoperability."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penta_interop", ROOT / "runtime" / "penta_interop.py")
interop = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = interop
SPEC.loader.exec_module(interop)


def fake_member(maturity: str) -> dict:
    return {
        "maturity": maturity,
        "canonical_name": "Test",
        "portal_route": "/penta/test",
        "source": "data/penta/test.json",
        "dependencies": [],
    }


def authority() -> dict:
    return {
        "chlom_ref": "chlom:authority:test",
        "dail_ref": "dail:authority:test",
        "accountable_owner": "role:owner",
    }


def dail_plan() -> dict:
    return {
        "dail_write_mode": "transactional_outbox",
        "dail_event_plan_ref": "ct.dail.plan:penta-handoff:v1",
    }


class PentaInteropTests(unittest.TestCase):
    def test_hash_is_deterministic(self):
        payload = {"b": 2, "a": [1, 3]}
        self.assertEqual(interop.receipt_sha256(payload), interop.receipt_sha256(dict(payload)))
        self.assertEqual(len(interop.receipt_sha256(payload)), 64)

    def test_unknown_target_fails_closed(self):
        snapshot = {"members": {"penta.error": fake_member("production")}}
        envelope = interop.build_envelope(
            source_member="penta.error",
            target_member="penta.missing",
            operation="report_failure",
            requested_effect="prepare",
            evidence_refs=["evidence:1"],
        )
        result = interop.evaluate_handoff(snapshot, envelope)
        self.assertEqual(result["disposition"], "hold_fail_closed")
        self.assertFalse(result["eligible"])

    def test_implemented_member_may_receive_non_execution_handoff(self):
        snapshot = {
            "members": {
                "penta.error": fake_member("production"),
                "penta.compliance": fake_member("implemented"),
            }
        }
        envelope = interop.build_envelope(
            source_member="penta.error",
            target_member="penta.compliance",
            operation="prepare_remediation_packet",
            requested_effect="prepare",
            evidence_refs=["evidence:failure:1"],
        )
        result = interop.evaluate_handoff(snapshot, envelope)
        self.assertEqual(result["disposition"], "workflow_ready")
        self.assertTrue(result["eligible"])

    def test_implemented_member_cannot_execute(self):
        snapshot = {
            "members": {
                "penta.error": fake_member("production"),
                "penta.compliance": fake_member("implemented"),
            }
        }
        envelope = interop.build_envelope(
            source_member="penta.error",
            target_member="penta.compliance",
            operation="submit_attestation",
            requested_effect="execute",
            evidence_refs=["evidence:controls:1"],
            authority_trace=authority(),
            readback_strategy="verify attestation receipt",
            metadata=dail_plan(),
        )
        result = interop.evaluate_handoff(snapshot, envelope)
        self.assertEqual(result["disposition"], "governance_required")
        self.assertTrue(any("target maturity" in reason for reason in result["reasons"]))

    def test_production_members_can_be_execution_ready_with_required_evidence(self):
        snapshot = {
            "members": {
                "penta.error": fake_member("production"),
                "penta.metric": fake_member("production"),
            }
        }
        envelope = interop.build_envelope(
            source_member="penta.error",
            target_member="penta.metric",
            operation="record_failure_metric",
            requested_effect="execute",
            evidence_refs=["evidence:error:1"],
            authority_trace=authority(),
            readback_strategy="verify metric snapshot",
            metadata=dail_plan(),
        )
        result = interop.evaluate_handoff(snapshot, envelope)
        self.assertEqual(result["disposition"], "execution_ready")
        self.assertTrue(result["eligible"])

    def test_provider_execution_requires_binding_and_readback(self):
        snapshot = {
            "members": {
                "penta.error": fake_member("production"),
                "penta.metric": fake_member("production"),
            }
        }
        envelope = interop.build_envelope(
            source_member="penta.error",
            target_member="penta.metric",
            operation="export_metric",
            requested_effect="execute",
            evidence_refs=["evidence:metric:1"],
            authority_trace=authority(),
            provider_effect=True,
            metadata=dail_plan(),
        )
        result = interop.evaluate_handoff(snapshot, envelope)
        self.assertEqual(result["disposition"], "governance_required")
        self.assertTrue(any("provider binding" in reason for reason in result["reasons"]))
        self.assertTrue(any("readback" in reason for reason in result["reasons"]))

    def test_execution_without_dail_plan_fails_closed(self):
        snapshot = {
            "members": {
                "penta.error": fake_member("production"),
                "penta.metric": fake_member("production"),
            }
        }
        envelope = interop.build_envelope(
            source_member="penta.error",
            target_member="penta.metric",
            operation="record_failure_metric",
            requested_effect="execute",
            evidence_refs=["evidence:error:2"],
            authority_trace=authority(),
            readback_strategy="verify metric snapshot",
        )
        result = interop.evaluate_handoff(snapshot, envelope)
        self.assertEqual(result["disposition"], "governance_required")
        self.assertTrue(any("DAIL event plan" in reason for reason in result["reasons"]))

    def test_live_repository_interoperability_certifies(self):
        snapshot = interop.build_interoperability_snapshot(ROOT)
        self.assertEqual(snapshot["status"], "PASS", snapshot["blockers"])
        self.assertEqual(snapshot["production_state"], "production")
        self.assertEqual(snapshot["family_member_count"], snapshot["runtime_inventory_member_count"])
        self.assertEqual(snapshot["family_member_count"], snapshot["addressable_member_count"])
        self.assertEqual(snapshot["blocker_count"], 0)
        coverage = {item["machine_key"]: item for item in snapshot["coverage"]}
        for key in interop.REQUIRED_SPINE | interop.REQUIRED_OBSERVABILITY:
            self.assertIn(key, coverage, key)
        for key in (
            "penta.privacy",
            "penta.identity",
            "penta.data",
            "penta.records",
            "penta.procure",
            "penta.vendor",
            "penta.contracts",
            "penta.quality",
        ):
            self.assertIn(key, coverage, key)
            self.assertEqual(coverage[key]["maturity"], "implemented", key)
            self.assertFalse(coverage[key]["execution_eligible"], key)
        for key in ("penta.compliance", "penta.license"):
            self.assertIn(key, coverage, key)
            self.assertEqual(coverage[key]["maturity"], "production", key)
            self.assertTrue(coverage[key]["execution_eligible"], key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
