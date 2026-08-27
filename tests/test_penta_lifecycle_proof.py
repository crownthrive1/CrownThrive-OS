import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from penta_lifecycle_proof import build_receipt, verify_receipt


def base(**overrides):
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


def test_valid_transition_receipt_verifies():
    receipt = build_receipt(**base())
    verify_receipt(receipt)


def test_exact_head_is_fail_closed():
    with pytest.raises(ValueError, match="exact_head_readback_failed"):
        build_receipt(**base(observed_head_sha="moved"))


def test_illegal_transition_is_rejected():
    with pytest.raises(ValueError, match="illegal_transition"):
        build_receipt(**base(previous="OPEN", current="MERGED", terminal_sha="merge1"))


def test_merge_requires_terminal_sha():
    with pytest.raises(ValueError, match="merged_without_terminal_sha"):
        build_receipt(**base(previous="MERGE_CANDIDATE", current="MERGED"))


def test_merge_receipt_is_immutable_and_verifiable():
    receipt = build_receipt(**base(previous="MERGE_CANDIDATE", current="MERGED", terminal_sha="merge1"))
    verify_receipt(receipt)
    receipt["terminal_sha"] = "tampered"
    with pytest.raises(ValueError, match="receipt_digest_mismatch"):
        verify_receipt(receipt)


def test_revert_is_a_new_terminal_event_not_unmerge():
    candidate = build_receipt(**base(previous="MERGED", current="REVERT_CANDIDATE", terminal_sha=None))
    reverted = build_receipt(**base(previous="REVERT_CANDIDATE", current="REVERTED", terminal_sha="revert1", previous_receipt_sha256=candidate["receipt_sha256"]))
    verify_receipt(candidate)
    verify_receipt(reverted)
