from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "runtime" / "penta_institutional_services.py"
spec = importlib.util.spec_from_file_location("penta_institutional_services", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

DecisionPacketError = module.DecisionPacketError
build_decision_packet = module.build_decision_packet
evaluate_decision_packet = module.evaluate_decision_packet
validate_decision_packet = module.validate_decision_packet

NOW = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)
APPROVAL_TIME = "2026-08-26T07:55:00Z"


class InstitutionalServicesTests(unittest.TestCase):
    def packet(self, system: str, action: str, **overrides):
        params = {
            "issuing_system": system,
            "action_class": action,
            "summary": f"Evaluate {action}",
            "evidence_refs": ["evidence://test/1"],
            "risk_score": 25,
            "impact_score": 50,
            "now": NOW,
        }
        params.update(overrides)
        return build_decision_packet(**params)

    def test_analytics_is_advisory_by_default(self):
        packet = self.packet("penta.analytics", "forecast_metric")
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "advisory_ready")

    def test_impact_is_advisory_by_default(self):
        packet = self.packet("penta.impact", "evaluate_program")
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "advisory_ready")

    def test_capital_transfer_cannot_self_authorize(self):
        packet = self.packet("penta.capital", "transfer_funds", risk_score=80)
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "governance_required")
        joined = " ".join(result["reasons"])
        self.assertIn("human gate", joined)
        self.assertIn("required_capability", joined)
        self.assertIn("authority trace", joined)
        self.assertIn("provider binding", joined)

    def test_capital_transfer_can_become_authorized_ready_but_not_executed(self):
        packet = self.packet(
            "penta.capital",
            "transfer_funds",
            risk_score=80,
            required_capability="capital.transfer.approve",
            human_gate_required=True,
            human_roles=["authorized_capital_officer"],
            quorum=1,
            approvals=[{
                "principal": "principal:test-capital-officer",
                "role": "authorized_capital_officer",
                "decision": "approve",
                "timestamp": APPROVAL_TIME,
            }],
            authority_trace={
                "chlom_ref": "chlom://capability/capital.transfer.approve",
                "dail_ref": None,
                "accountable_owner": "CrownThrive Holdings",
                "provider_binding_ref": "provider://certified/capital-rail/test",
            },
        )
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "authorized_ready")
        self.assertIn("separately certified route/provider", result["reasons"][0])

    def test_legal_binding_action_requires_governance(self):
        packet = self.packet("penta.legal", "sign_contract", risk_score=75)
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "governance_required")

    def test_penta_legal_cannot_claim_counsel_role(self):
        packet = self.packet("penta.legal", "provide_legal_advice")
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "hold_fail_closed")
        self.assertIn("legal counsel", result["reasons"][0])

    def test_audit_cannot_certify_release(self):
        packet = self.packet("penta.audit", "certify_release")
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "hold_fail_closed")
        self.assertIn("PentaAssure", result["reasons"][0])

    def test_policy_enactment_requires_authority_and_human_gate(self):
        packet = self.packet("penta.policy", "enact_policy", risk_score=85)
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "governance_required")
        self.assertTrue(result["controls"]["capability_required"])

    def test_high_risk_risk_acceptance_requires_independent_review(self):
        packet = self.packet(
            "penta.risk",
            "accept_risk",
            risk_score=95,
            required_capability="risk.accept.D3",
            human_gate_required=True,
            human_roles=["risk_owner"],
            quorum=1,
            approvals=[{
                "principal": "principal:test-risk-owner",
                "role": "risk_owner",
                "decision": "approve",
                "timestamp": APPROVAL_TIME,
            }],
            authority_trace={
                "chlom_ref": "chlom://capability/risk.accept.D3",
                "dail_ref": None,
                "accountable_owner": "risk-owner:test",
                "provider_binding_ref": None,
            },
        )
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "governance_required")
        self.assertIn("independent review", " ".join(result["reasons"]))

    def test_security_cannot_self_expand_privilege(self):
        packet = self.packet("penta.security", "self_expand_privilege")
        result = evaluate_decision_packet(packet, now=NOW)
        self.assertEqual(result["disposition"], "hold_fail_closed")

    def test_required_human_gate_must_define_quorum(self):
        with self.assertRaises(DecisionPacketError):
            self.packet(
                "penta.capital",
                "transfer_funds",
                human_gate_required=True,
                human_roles=[],
                quorum=0,
            )

    def test_duplicate_evidence_rejected(self):
        with self.assertRaises(DecisionPacketError):
            self.packet(
                "penta.analytics",
                "forecast_metric",
                evidence_refs=["evidence://same", "evidence://same"],
            )

    def test_expired_unconverged_packet_rejected(self):
        with self.assertRaises(DecisionPacketError):
            self.packet(
                "penta.policy",
                "draft_policy",
                expires_at="2026-08-26T07:00:00Z",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
