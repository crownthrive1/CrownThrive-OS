import copy
import json
import unittest
from pathlib import Path

from scripts import validate_security_governance as security


ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads(security.PROVIDER_RELEASE_HOLDS.read_text(encoding="utf-8"))


class ProviderReleaseSecurityHoldTests(unittest.TestCase):
    def test_repository_record_satisfies_fail_closed_boundary(self):
        self.assertEqual(security.provider_release_hold_errors(RECORD), [])

    def test_database_push_permission_fails_closed(self):
        unsafe = copy.deepcopy(RECORD)
        unsafe["release_predicate"]["database_push_allowed"] = True
        self.assertIn(
            "provider security boundary must prohibit database push",
            security.provider_release_hold_errors(unsafe),
        )

    def test_claimed_migration_lineage_fails_closed(self):
        unsafe = copy.deepcopy(RECORD)
        unsafe["supabase_migration_lineage"]["local_to_provider_one_to_one_lineage_proven"] = True
        self.assertIn(
            "provider migration lineage must not be claimed proven",
            security.provider_release_hold_errors(unsafe),
        )

    def test_claimed_deno_lockfile_fails_closed(self):
        unsafe = copy.deepcopy(RECORD)
        unsafe["deno_dependency_boundary"]["deno_lock_present"] = True
        self.assertIn(
            "Deno dependency record must not claim a lockfile exists",
            security.provider_release_hold_errors(unsafe),
        )

    def test_major_release_unblocked_fails_closed(self):
        unsafe = copy.deepcopy(RECORD)
        unsafe["release_predicate"]["major_release_blocked"] = False
        self.assertIn(
            "provider security boundary must block the major release",
            security.provider_release_hold_errors(unsafe),
        )

    def test_provider_advisory_count_drift_fails_closed(self):
        unsafe = copy.deepcopy(RECORD)
        unsafe["supabase_advisory_snapshot"]["performance"]["total"] = 0
        self.assertIn(
            "Supabase performance advisory snapshot drifted",
            security.provider_release_hold_errors(unsafe),
        )


if __name__ == "__main__":
    unittest.main()
