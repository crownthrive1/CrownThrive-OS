import unittest

from runtime.penta_immune import (
    AutonomyPolicy,
    WeaknessCandidate,
    build_repair_plan,
    propose_penta,
    rank_candidates,
    remember_repair,
    select_candidate,
    verify_repair_result,
)


def candidate(
    id="candidate-1",
    *,
    authority="D2",
    severity=4,
    recurrence=3,
    confidence=5,
    reversibility=5,
    testability=5,
    blast_radius=1,
):
    return WeaknessCandidate(
        id=id,
        kind="known_governance_defect",
        source_ref="issue:121",
        authority_level=authority,
        handler="patch_known_code",
        severity=severity,
        recurrence=recurrence,
        confidence=confidence,
        reversibility=reversibility,
        testability=testability,
        blast_radius=blast_radius,
        rollback={"method": "git_revert", "scope": "candidate commit"},
        fallback={"method": "hold", "redundancy": "known-good-main"},
        metadata={"repo": "crownthrive1/CrownThrive-OS"},
    )


class PentaImmuneTests(unittest.TestCase):
    def test_hunter_prioritizes_high_value_reversible_candidate(self):
        high = candidate("high")
        low = candidate("low", severity=1, recurrence=1, confidence=2, reversibility=2, testability=2, blast_radius=4)
        self.assertEqual(rank_candidates([low, high])[0].id, "high")

    def test_plan_always_contains_rollback_and_redundancy(self):
        plan = build_repair_plan(candidate())
        self.assertEqual(plan["status"], "READY")
        self.assertTrue(plan["rollback"])
        self.assertTrue(plan["fallback"])
        self.assertTrue(plan["redundancy_required"])
        self.assertFalse(plan["production_promotion_authorized"])

    def test_d3_is_held(self):
        plan = build_repair_plan(candidate(authority="D3"))
        self.assertEqual(plan["status"], "HOLD")
        self.assertIn("candidate exceeds autonomous authority", plan["reasons"])

    def test_kill_switch_halts_repairs(self):
        plan = build_repair_plan(candidate(), AutonomyPolicy(kill_switch_state="tripped"))
        self.assertEqual(plan["status"], "HOLD")
        self.assertIn("kill switch is tripped", plan["reasons"])

    def test_retry_cap_is_fail_closed(self):
        result = select_candidate([candidate()], attempt_counts={"candidate-1": 2})
        self.assertIsNone(result["selected"])
        self.assertIn("candidate retry cap reached", result["considered"][0]["reasons"])

    def test_exact_head_test_binding_required(self):
        plan = build_repair_plan(candidate())
        result = verify_repair_result(
            plan,
            tested_head_sha="a" * 40,
            current_head_sha="b" * 40,
            test_receipts=[{"name": "unit", "status": "PASS"}],
        )
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("tested head does not match current head", result["reasons"])

    def test_successful_repair_can_enter_advisory_memory(self):
        c = candidate()
        plan = build_repair_plan(c)
        result = verify_repair_result(
            plan,
            tested_head_sha="a" * 40,
            current_head_sha="a" * 40,
            test_receipts=[{"name": "unit", "status": "PASS"}],
        )
        memory = remember_repair(c, plan=plan, repair_result=result, evidence_receipt_sha256="e" * 64)
        self.assertTrue(memory["advisory_only"])
        self.assertTrue(memory["requires_retest"])
        self.assertFalse(memory["grants_certification"])

    def test_failed_repair_is_not_learned_as_success(self):
        c = candidate()
        plan = build_repair_plan(c)
        result = verify_repair_result(
            plan,
            tested_head_sha="a" * 40,
            current_head_sha="a" * 40,
            test_receipts=[{"name": "unit", "status": "FAIL"}],
        )
        with self.assertRaises(ValueError):
            remember_repair(c, plan=plan, repair_result=result, evidence_receipt_sha256="e" * 64)

    def test_new_pentas_are_candidates_not_self_activated(self):
        proposal = propose_penta(name="PentaExample", purpose="bounded example", evidence_refs=["evidence:test"])
        self.assertEqual(proposal["state"], "CANDIDATE")
        self.assertTrue(proposal["requires_external_governance"])
        self.assertFalse(proposal["self_activation_authorized"])

    def test_external_or_arbitrary_handler_is_rejected(self):
        bad = WeaknessCandidate(
            id="bad",
            kind="known_governance_defect",
            source_ref="external:target",
            authority_level="D1",
            handler="run_arbitrary_shell",
            severity=1,
            recurrence=1,
            confidence=1,
            reversibility=1,
            testability=1,
            blast_radius=1,
            rollback={"method": "none"},
            fallback={"method": "hold"},
        )
        with self.assertRaises(ValueError):
            bad.validate()


if __name__ == "__main__":
    unittest.main()
