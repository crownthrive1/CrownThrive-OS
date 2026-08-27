from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_release_governance_invariants.py"
)
SPEC = importlib.util.spec_from_file_location("release_governance_invariants", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReleaseGovernanceInvariantTests(unittest.TestCase):
    def test_current_repository_is_fail_closed(self) -> None:
        MODULE.validate_all()

    def test_negative_bypass_vectors_are_detected(self) -> None:
        MODULE.self_test()

    def test_human_d3_major_lane_is_fail_closed(self) -> None:
        MODULE.validate_major_publisher()

    def test_provider_writers_share_one_lease(self) -> None:
        MODULE.validate_provider_writer_lease()


if __name__ == "__main__":
    unittest.main()
