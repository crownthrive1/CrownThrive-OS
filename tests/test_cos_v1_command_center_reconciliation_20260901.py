from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/cos-v1-command-center-reconciliation.2026-09-01.v1.json"
STANDARD = ROOT / "developers/ACCOUNT-API-REVIEW-AND-SITES-RELEASE-STANDARD.md"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class COSV1CommandCenterReconciliationTests(unittest.TestCase):
    def test_sources_and_sites_source_namespaces_are_not_conflated(self) -> None:
        manifest = load_manifest()
        self.assertEqual(
            manifest["source_heads"]["crownthrive_os_main"],
            "90472fdce24d05a5f722b4029af4b466b43c3d4a",
        )
        site = manifest["command_center"]
        self.assertEqual(site["site_source_sha"], "d94e1dc01348091ae479cd200b3fe2bb86958968")
        self.assertFalse(site["site_source_is_crownthrive_os_git_sha"])
        self.assertEqual(site["version_number"], 21)
        self.assertFalse(site["access_policy_changed"])

    def test_customer_counts_do_not_absorb_governance_memberships(self) -> None:
        census = load_manifest()["member_census"]
        self.assertEqual(census["verified_live_users_or_profiles"], 1)
        self.assertEqual(census["active_stripe_subscriptions"], 1)
        self.assertEqual(census["held_customer_accounts"], 0)
        self.assertFalse(census["governance_memberships_are_customers"])
        self.assertFalse(census["public_125k_member_claim_supported"])

    def test_api_key_activation_is_entitlement_gated_and_secret_minimized(self) -> None:
        manifest = load_manifest()
        api = manifest["public_api"]
        self.assertEqual(api["status"], "CATALOG_READY_CUSTOMER_ACTIVATION_HELD")
        self.assertEqual(api["developer_accounts"], 0)
        self.assertEqual(api["api_keys"], 0)
        flow = manifest["account_key_activation"]["required_flow"]
        self.assertIn("require approved plan and entitlement", flow)
        self.assertIn("persist only prefix and SHA-256 hash", flow)
        self.assertFalse(manifest["stripe"]["payment_is_entitlement"])

    def test_security_and_release_fail_closed(self) -> None:
        manifest = load_manifest()
        security = manifest["thrivebase_private"]["security_advisor"]
        self.assertEqual(security["error"], 21)
        self.assertTrue(security["gate"].startswith("HOLD_"))
        self.assertIn(
            "blanket USING (true) policies",
            manifest["thrivebase_private"]["prohibited_shortcuts"],
        )
        self.assertEqual(manifest["release_gate"]["decision"], "HOLD_NO_COMMAND_CENTER_DEPLOYMENT")
        self.assertFalse(manifest["site_release_default"]["site_replacement_allowed"])
        self.assertFalse(manifest["site_release_default"]["audience_expansion_allowed"])

    def test_four_hour_route_reuses_existing_clocks(self) -> None:
        route = load_manifest()["four_hour_review"]
        self.assertEqual(route["clock"], "ct.schedule.founder-operating-loop.4h.v1")
        self.assertFalse(route["duplicate_dispatch_clock_created"])
        self.assertIn("Communications Watch", route["outbound_route"])

    def test_standard_preserves_phase_and_native_sites_boundaries(self) -> None:
        standard = STANDARD.read_text(encoding="utf-8")
        self.assertIn("Public ecosystem rollout: Phase 0", standard)
        self.assertIn("Internal institutional controls: Phase 3 — Execute", standard)
        self.assertIn("does not perform a native provider write", standard)
        self.assertIn("Governed autonomy. Evidence-backed execution.", standard)


if __name__ == "__main__":
    unittest.main()
