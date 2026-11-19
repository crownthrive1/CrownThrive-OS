from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260910160000_reconcile_gretna_cpanel_sites_authority.sql"
EVIDENCE = ROOT / "docs" / "evidence" / "gretna-cpanel-sites-authority-20260910.json"
CORRECTION = ROOT / "docs" / "evidence" / "gretna-cpanel-sites-authority-correction-20261119.json"


class PentaGretnaCpanelSitesAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        cls.correction = json.loads(CORRECTION.read_text(encoding="utf-8"))

    def test_vault_alias_requires_exactly_one_record(self) -> None:
        self.assertIn("select id,encode(extensions.digest(convert_to(secret,'UTF8'),'sha256'),'hex') into strict v_secret_id,v_fp", self.migration)
        self.assertIn("when no_data_found then", self.migration)
        self.assertIn("when too_many_rows then", self.migration)
        self.assertIn("gretna_cpanel_vault_alias_not_unique", self.migration)
        self.assertIn("gretna_cpanel_vault_secret_invalid", self.migration)
        self.assertNotIn("order by updated_at desc", self.migration)
        self.assertNotIn("limit 1", self.migration)

    def test_cpanel_does_not_assert_sites_provider_or_health(self) -> None:
        update = self.migration.split("update integration_control.website_surfaces", 1)[1].split("where surface_id", 1)[0]
        self.assertNotIn("provider_system=", update)
        self.assertNotIn("provider_connection_state=", update)
        self.assertNotIn("health_state=", update)
        self.assertIn("site_maintenance_authority", update)
        self.assertIn("supporting_cpanel_control", update)

    def test_historical_evidence_is_preserved_and_corrected_additively(self) -> None:
        self.assertEqual(self.evidence["observed_at"], "2026-09-10T16:01:12Z")
        self.assertEqual(self.correction["historical_evidence_ref"], "docs/evidence/gretna-cpanel-sites-authority-20260910.json")
        self.assertTrue(self.correction["historical_claims_preserved"])
        self.assertFalse(self.correction["historical_provider_observations"]["current_evidence"])

    def test_authority_and_credential_custody_remain_bounded(self) -> None:
        authority = self.correction["authority"]
        credential = self.correction["credential_identity"]
        self.assertEqual(authority["site_publication_authority"], "Sites")
        self.assertEqual(authority["cpanel_role"], "secondary_hosting_domain_control")
        self.assertFalse(authority["provider_write"])
        self.assertEqual(credential["selection_requirement"], "exactly_one_matching_record")
        self.assertFalse(credential["rotation_authorized"])
        self.assertFalse(credential["silent_replacement_authorized"])
        self.assertFalse(credential["duplicate_credential_creation_authorized"])


if __name__ == "__main__":
    unittest.main()
