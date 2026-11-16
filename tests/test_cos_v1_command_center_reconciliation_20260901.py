from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/cos-v1-command-center-reconciliation.2026-09-01.v1.json"
STANDARD = ROOT / "developers/ACCOUNT-API-REVIEW-AND-SITES-RELEASE-STANDARD.md"
PAGE = ROOT / "technology/crownthrive-command-center.mdx"
SCHEDULER_TOPOLOGY = ROOT / "developers/contracts/agent-scheduler-topology-production.v1.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def load_scheduler_topology() -> dict:
    return json.loads(SCHEDULER_TOPOLOGY.read_text(encoding="utf-8"))


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

    def test_four_hour_review_is_folded_into_the_canonical_relay(self) -> None:
        route = load_manifest()["four_hour_review"]
        external = load_scheduler_topology()["canonical_external_clock_model"]
        self.assertEqual(route["clock"], "ct.schedule.founder-operating-loop.4h.v1")
        self.assertEqual(route["topology"], "folded_into_existing_external_evidence_relay")
        self.assertFalse(route["duplicate_dispatch_clock_created"])
        self.assertEqual(external["post_maintenance_target_count"], 2)
        self.assertEqual(
            external["external_evidence_relay"]["schedule_id"],
            "ct.schedule.external-evidence-relay.hourly.v1",
        )
        self.assertEqual(
            external["communications"]["canonical_name"],
            "CrownThrive Communications Watch",
        )
        self.assertIn("Communications Watch", route["outbound_route"])

    def test_internal_clocks_and_retired_external_scaffolding_stay_separate(self) -> None:
        topology = load_scheduler_topology()
        external = topology["canonical_external_clock_model"]
        relay = external["external_evidence_relay"]
        communications = external["communications"]
        backup = external["backup_continuity"]
        maintenance = external["maintenance_coordinator"]

        self.assertEqual(relay["cadence"], "hourly at minute 17")
        self.assertEqual(relay["external_task_id"], "6a8620e935cc8191bbd31075e12dd22a")
        self.assertEqual(relay["state"], "ACTIVE_CONNECTOR_FAILURE_DOMAIN_ONLY")
        self.assertFalse(relay["authority_expansion"])

        self.assertEqual(communications["binding_id"], "ct.automation.email-attention.v1")
        self.assertEqual(
            communications["failure_domain"],
            "email_and_communications_connector",
        )
        self.assertEqual(
            communications["state"],
            "ACTIVE_COMMUNICATIONS_FAILURE_DOMAIN_ONLY",
        )

        self.assertEqual(backup["internal_clock"], "pg_cron")
        self.assertEqual(
            backup["external_connector_parent"],
            relay["schedule_id"],
        )
        self.assertEqual(
            backup["dedicated_external_clock"],
            "RETIRED_SCHEDULING_SCAFFOLDING",
        )
        self.assertEqual(
            maintenance["state"],
            "RETIRED_SCHEDULING_SCAFFOLDING",
        )
        self.assertFalse(maintenance["task_enabled"])
        self.assertTrue(maintenance["maintenance_closed"])

        retired = topology["retired_external_scaffolding"]
        for key in (
            "document_recovery_state",
            "penta_hourly_delivery_watch_state",
            "penta_reward_v5_review_state",
        ):
            self.assertEqual(retired[key], "RETIRED_SCHEDULING_SCAFFOLDING")
        self.assertTrue(retired["historical_records_preserved"])

    def test_scheduler_invariants_preserve_authority_and_recovery_boundaries(self) -> None:
        invariants = load_scheduler_topology()["invariants"]
        for key in (
            "no_duplicate_clocks",
            "no_recursive_external_schedulers",
            "originator_verifier_separation",
            "d3_human_reserved",
            "append_or_supersede_history",
        ):
            with self.subTest(invariant=key):
                self.assertTrue(invariants[key])
        for key in (
            "scheduler_clock_creates_authority",
            "authority_expansion",
            "money_movement_from_scheduler",
            "provider_write_authority_from_scheduler",
            "raw_secret_export",
            "direct_main_write_from_scheduler",
        ):
            with self.subTest(invariant=key):
                self.assertFalse(invariants[key])

    def test_later_provider_migration_custody_remains_held(self) -> None:
        lineage = load_scheduler_topology()["source_lineage"]
        self.assertEqual(
            lineage["later_provider_migration_source_custody"],
            "HOLD_PENDING_AUTHORITATIVE_RECOVERY",
        )
        self.assertEqual(
            lineage["history_policy"],
            "append_or_supersede_never_silent_delete",
        )
        self.assertIn(
            "20260826205712_schedule_penta_judicial_timeout_v1",
            lineage["later_provider_migrations_without_local_sql"],
        )

    def test_page_labels_provider_and_phase_values_as_historical(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("Freshness boundary", page)
        self.assertIn("2026-08-24T05:28:25.137432+00:00", page)
        self.assertIn("Historical institutional snapshot", page)
        self.assertIn("not current institutional-phase assertions", page)
        self.assertIn("2026-09-01", page)
        self.assertIn("not a current provider readback", page)
        self.assertNotIn("| Field | Verified state |", page)
        self.assertNotIn("Provider readback:", page)
        self.assertIn("Historical connection observations", page)

    def test_page_metadata_preserves_hold_and_excludes_retired_phase_tokens(self) -> None:
        frontmatter = PAGE.read_text(encoding="utf-8").split("---", 2)[1]
        keywords = next(line for line in frontmatter.splitlines() if line.startswith("keywords:"))
        self.assertIn('"historical phase snapshot"', keywords)
        self.assertNotRegex(keywords, r'"Phase[ ]+2([.][0-9]+)?([^"]*)?"')
        self.assertIn('tag: "Prototype · HOLD"', frontmatter)
        self.assertIn('content_state: "unresolved"', frontmatter)

    def test_standard_preserves_phase_and_native_sites_boundaries(self) -> None:
        standard = STANDARD.read_text(encoding="utf-8")
        self.assertIn("Public ecosystem rollout: Phase 0", standard)
        self.assertIn("Internal institutional controls: Phase 3 — Execute", standard)
        self.assertIn("does not perform a native provider write", standard)
        self.assertIn("Governed autonomy. Evidence-backed execution.", standard)


if __name__ == "__main__":
    unittest.main()
