import os
import unittest
from unittest.mock import patch

from runtime.penta_mailgun_redundancy import available_lanes, certification_snapshot, select_lane


class PentaMailerMailgunRedundancyTests(unittest.TestCase):
    def test_primary_secondary_are_detected_without_secret_values(self):
        with patch.dict(os.environ, {
            "MAILGUN_API_KEY_PRIMARY": "primary-secret-placeholder",
            "MAILGUN_API_KEY_SECONDARY": "secondary-secret-placeholder",
            "MAILGUN_DOMAIN": "mg.example.test",
        }, clear=True):
            snapshot = certification_snapshot()
            self.assertTrue(snapshot["redundancy_ready"])
            self.assertTrue(snapshot["domain_bound"])
            self.assertFalse(snapshot["secret_values_persisted"])
            rendered = repr(snapshot)
            self.assertNotIn("primary-secret-placeholder", rendered)
            self.assertNotIn("secondary-secret-placeholder", rendered)

    def test_failover_selects_secondary_when_primary_excluded(self):
        with patch.dict(os.environ, {
            "MAILGUN_API_KEY_PRIMARY": "primary-secret-placeholder",
            "MAILGUN_API_KEY_SECONDARY": "secondary-secret-placeholder",
        }, clear=True):
            self.assertEqual(select_lane(exclude={"primary"}).lane, "secondary")

    def test_unbound_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(available_lanes(), [])
            with self.assertRaisesRegex(RuntimeError, "HOLD_UNBOUND"):
                select_lane()


if __name__ == "__main__":
    unittest.main()
