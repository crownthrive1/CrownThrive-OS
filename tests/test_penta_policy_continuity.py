from datetime import datetime, timedelta, timezone
import unittest

from runtime.penta_policy_continuity import (
    ControlAuthority,
    ReleaseEvidence,
    current_control,
    evaluate_autonomous_release,
    stale_current_controls,
    supersession_story,
)


class PentaPolicyContinuityTests(unittest.TestCase):
    def evidence(self, **overrides):
        base = dict(
            risk_class="D0",
            genuine_pass=True,
            independent_certification_pass=10,
            independent_certification_required=10,
            health_pass=5,
            health_required=5,
            route_verified=True,
            rollback_readback_verified=True,
            maintenance_active=False,
            human_approval_state="not_required",
        )
        base.update(overrides)
        return ReleaseEvidence(**base)

    def test_d0_d2_exact_evidence_is_autonomous_without_vote_quorum(self):
        for risk in ("D0", "D1", "D2"):
            decision = evaluate_autonomous_release(self.evidence(risk_class=risk))
            self.assertTrue(decision.accepted)
            self.assertEqual(decision.authority_model, "autonomous_exact_evidence")
            self.assertFalse(decision.vote_quorum_required)
            self.assertEqual(decision.oidc_role, "execution_identity_attestation_only")

    def test_d3_remains_human_reserved(self):
        held = evaluate_autonomous_release(
            self.evidence(risk_class="D3", human_approval_state="pending")
        )
        self.assertFalse(held.accepted)
        self.assertEqual(held.reason, "d3_human_approval_required")
        approved = evaluate_autonomous_release(
            self.evidence(risk_class="D3", human_approval_state="approved")
        )
        self.assertTrue(approved.accepted)

    def test_every_exact_gate_remains_fail_closed(self):
        cases = (
            ({"genuine_pass": False}, "candidate_not_genuine_pass"),
            ({"independent_certification_pass": 9}, "independent_certification_incomplete"),
            ({"health_pass": 4}, "provider_health_incomplete"),
            ({"route_verified": False}, "route_not_verified"),
            ({"rollback_readback_verified": False}, "rollback_readback_not_verified"),
            ({"maintenance_active": True}, "maintenance_active"),
        )
        for patch, reason in cases:
            with self.subTest(reason=reason):
                decision = evaluate_autonomous_release(self.evidence(**patch))
                self.assertFalse(decision.accepted)
                self.assertEqual(decision.reason, reason)

    def test_newest_current_control_wins_and_old_current_is_drift(self):
        now = datetime.now(timezone.utc)
        old = ControlAuthority(
            "ct.site.autopublish.v1", "factory_release_authority", "1.0.0",
            now - timedelta(days=1), "current", "sovereign_vote_quorum",
        )
        new = ControlAuthority(
            "ct.factory.autonomous.exact-evidence-promotion.v1",
            "factory_release_authority", "1.0.0", now, "current",
            "autonomous_exact_evidence",
        )
        self.assertEqual(current_control((old, new), "factory_release_authority"), new)
        self.assertEqual(stale_current_controls((old, new), "factory_release_authority"), (old,))

    def test_supersession_story_is_historical_not_authority(self):
        now = datetime.now(timezone.utc)
        old = ControlAuthority(
            "ct.site.autopublish.v1", "factory_release_authority", "1.0.0",
            now - timedelta(days=1), "superseded", "sovereign_vote_quorum",
        )
        new = ControlAuthority(
            "ct.factory.autonomous.exact-evidence-promotion.v1",
            "factory_release_authority", "1.0.0", now, "current",
            "autonomous_exact_evidence",
        )
        story = supersession_story(old, new)
        self.assertIn("preserved as historical fact", story)
        self.assertIn("does not grant the historical control present authority", story)

    def test_no_financial_or_checkout_authority_is_manufactured(self):
        decision = evaluate_autonomous_release(self.evidence())
        self.assertFalse(decision.money_movement)
        self.assertFalse(decision.checkout_activation)


if __name__ == "__main__":
    unittest.main()
