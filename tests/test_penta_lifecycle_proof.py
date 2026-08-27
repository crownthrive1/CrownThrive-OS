import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from penta_lifecycle_proof import build_receipt, verify_receipt


class PentaLifecycleProofTests(unittest.TestCase):
    def base(self, **overrides):
        data = dict(
            pr=1,
            previous="READY",
            current="MERGE_CANDIDATE",
            head_sha="abc123",
            observed_head_sha="abc123",
            authority="PentaMerge",
            checks={"failed": False, "pending": False, "governed_ok": True},
            observed_at="2026-08-26T00:00:00Z",
        )
        data.update(overrides)
        return data

    def test_valid_transition_receipt_verifies(self):
        receipt = build_receipt(**self.base())
        verify_receipt(receipt)

    def test_exact_head_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "exact_head_readback_failed"):
            build_receipt(**self.base(observed_head_sha="moved"))

    def test_illegal_transition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "illegal_transition"):
            build_receipt(**self.base(previous="OPEN", current="MERGED", terminal_sha="merge1"))

    def test_merge_requires_terminal_sha(self):
        with self.assertRaisesRegex(ValueError, "merged_without_terminal_sha"):
            build_receipt(**self.base(previous="MERGE_CANDIDATE", current="MERGED"))

    def test_merge_receipt_is_immutable_and_verifiable(self):
        receipt = build_receipt(**self.base(previous="MERGE_CANDIDATE", current="MERGED", terminal_sha="merge1"))
        verify_receipt(receipt)
        receipt["terminal_sha"] = "tampered"
        with self.assertRaisesRegex(ValueError, "receipt_digest_mismatch"):
            verify_receipt(receipt)

    def test_revert_is_a_new_terminal_event_not_unmerge(self):
        candidate = build_receipt(**self.base(previous="MERGED", current="REVERT_CANDIDATE", terminal_sha=None))
        reverted = build_receipt(**self.base(previous="REVERT_CANDIDATE", current="REVERTED", terminal_sha="revert1", previous_receipt_sha256=candidate["receipt_sha256"]))
        verify_receipt(candidate)
        verify_receipt(reverted)


if __name__ == "__main__":
    unittest.main()
