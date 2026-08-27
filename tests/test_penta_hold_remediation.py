import unittest

from runtime.penta_hold_remediation import (
    CheckFailure,
    DAILLedger,
    EventType,
    PentaHoldRemediator,
    PullRequestState,
)


def pr(*failures, head="a" * 40, current=None, total=4, successful=0):
    return PullRequestState(
        repository="crownthrive1/CrownThrive-OS",
        number=551,
        head_sha=head,
        current_head_sha=current or head,
        draft=True,
        failures=tuple(failures),
        required_checks_total=total,
        required_checks_successful=successful,
    )


class PentaHoldRemediationTests(unittest.TestCase):
    def test_routes_interoperability_hold_to_pentainterops(self):
        subject = PentaHoldRemediator()
        plans = subject.evaluate(
            pr(CheckFailure("Penta Interoperability Production", "failure", "penta.immune child-member absent"))
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].owner_penta, "PentaInterOps")
        self.assertEqual(plans[0].disposition, "AUTO_REMEDIATE")
        self.assertTrue(plans[0].safe_to_autoremediate)

    def test_provider_custody_never_autoremediates_or_fabricates_evidence(self):
        subject = PentaHoldRemediator()
        plans = subject.evaluate(
            pr(CheckFailure("Governed Merge Gate", "failure", "Supabase migration-count drift; provider custody evidence stale"))
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].owner_penta, "PentaBind")
        self.assertEqual(plans[0].disposition, "EVIDENCE_REQUIRED")
        self.assertFalse(plans[0].safe_to_autoremediate)

    def test_unclassified_failure_escalates_fail_closed(self):
        subject = PentaHoldRemediator()
        self.assertEqual(subject.evaluate(pr(CheckFailure("Unknown Consequential Gate", "failure", "unexpected"))), [])
        self.assertEqual(subject.ledger.records[-1].event_type, EventType.REMEDIATION_ESCALATED)
        self.assertEqual(subject.ledger.records[-1].payload["reason"], "unclassified_or_ambiguous")

    def test_stale_head_is_superseded_and_never_routed(self):
        subject = PentaHoldRemediator()
        plans = subject.evaluate(
            pr(
                CheckFailure("Penta Runtime Suite", "failure", "family census"),
                head="a" * 40,
                current="b" * 40,
            )
        )
        self.assertEqual(plans, [])
        self.assertEqual(subject.ledger.records[-1].event_type, EventType.STALE_SUPERSEDED)

    def test_exact_head_fingerprint_dedupes_signature_noise_but_changes_with_head(self):
        subject = PentaHoldRemediator()
        first = CheckFailure("Penta Runtime Suite", "failure", "bad at 2026-08-27T13:00:00Z sha abcdef123456")
        second = CheckFailure("Penta Runtime Suite", "failure", "bad at 2026-08-27T14:00:00Z sha deadbee123456")
        one = subject.fingerprint(pr(first), first)
        two = subject.fingerprint(pr(second), second)
        self.assertEqual(one, two)
        different_pr = pr(second, head="b" * 40)
        self.assertNotEqual(subject.fingerprint(different_pr, second), one)

    def test_attempt_cap_escalates_instead_of_looping_forever(self):
        attempts = {}
        subject = PentaHoldRemediator(max_attempts=2, attempt_store=attempts)
        state = pr(CheckFailure("Penta Runtime Suite", "failure", "family-census mismatch"))
        self.assertEqual(len(subject.evaluate(state)), 1)
        self.assertEqual(len(subject.evaluate(state)), 1)
        self.assertEqual(subject.evaluate(state), [])
        self.assertEqual(subject.ledger.records[-1].event_type, EventType.REMEDIATION_ESCALATED)
        self.assertEqual(subject.ledger.records[-1].payload["reason"], "attempt_cap")

    def test_green_exact_head_hands_off_without_granting_merge_authority(self):
        subject = PentaHoldRemediator()
        state = pr(total=4, successful=4)
        subject.evaluate(state)
        self.assertEqual(
            [record.event_type for record in subject.ledger.records],
            [EventType.HOLD_CLEARED, EventType.PENTAPR_HANDOFF_READY],
        )
        self.assertFalse(subject.ledger.records[-1].payload["merge_authority_granted"])

    def test_completion_requires_retest_and_explicitly_disallows_waiver(self):
        subject = PentaHoldRemediator()
        state = pr(CheckFailure("Penta Runtime Suite", "failure", "family-census mismatch"))
        plan = subject.evaluate(state)[0]
        subject.record_completion(state, plan, evidence={"commit": "abc", "tests": "passed"})
        self.assertEqual(subject.ledger.records[-2].event_type, EventType.REMEDIATION_COMPLETED)
        self.assertEqual(subject.ledger.records[-1].event_type, EventType.RETEST_REQUESTED)
        self.assertEqual(subject.ledger.records[-1].payload, {"exact_head_required": True, "waiver_allowed": False})

    def test_dail_hash_chain_detects_tampering(self):
        ledger = DAILLedger()
        subject = PentaHoldRemediator(ledger=ledger)
        subject.evaluate(pr(CheckFailure("Penta Runtime Suite", "failure", "family-census mismatch")))
        self.assertTrue(ledger.verify())
        ledger.records[0].payload = {"tampered": True}
        self.assertFalse(ledger.verify())


if __name__ == "__main__":
    unittest.main()
