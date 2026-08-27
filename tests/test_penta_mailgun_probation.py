from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import unittest

from runtime.penta_mailgun_probation import (
    DuplicateIncidentConflict,
    IncidentRegistry,
    ProviderReadback,
    SignalRejected,
    build_incident,
    classify_notice,
    controlled_release,
    queue_hold_active,
    trigger_probation_active,
)


MAILGUN_NOTICE = """What happened?
Your account is on probation and domains are limited to 100 messages / hour.
To maintain the rate the account has been temporarily disabled.

The account will be enabled in 1754 seconds.

Thank you,
Mailgun Team
"""

T0 = datetime(2026, 8, 26, 20, 0, tzinfo=timezone.utc)


def classification(seconds=1754):
    return classify_notice(
        MAILGUN_NOTICE.replace("1754 seconds", f"{seconds} seconds"),
        authenticated=True,
        source="mailgun",
    )


def incident(
    event_id="mailgun-event-001",
    *,
    received_at=T0,
    seconds=1754,
    account_ref="mailgun:crownthrive",
    domain_ref="mail.crownthrive.com",
    trigger_ref="trigger:cold-outreach",
):
    return build_incident(
        classification(seconds),
        provider_event_id=event_id,
        account_ref=account_ref,
        domain_ref=domain_ref,
        trigger_ref=trigger_ref,
        received_at=received_at,
    )


class NoticeClassificationTests(unittest.TestCase):
    def test_classifies_exact_authenticated_notice_and_extracts_seconds(self):
        result = classification()
        self.assertEqual(result.kind, "mailgun_account_probation_temporarily_disabled")
        self.assertEqual(result.hourly_limit, 100)
        self.assertEqual(result.provider_enable_seconds, 1754)

    def test_rejects_generic_403_and_local_429(self):
        for text in (
            "HTTP 403 Forbidden: API credential is not authorized.",
            "HTTP 429: local rolling limit exceeded; retry later.",
        ):
            with self.subTest(text=text):
                with self.assertRaises(SignalRejected):
                    classify_notice(text, authenticated=True, source="mailgun")

    def test_rejects_spoofed_or_wrong_source_notice(self):
        with self.assertRaises(SignalRejected):
            classify_notice(MAILGUN_NOTICE, authenticated=False, source="mailgun")
        with self.assertRaises(SignalRejected):
            classify_notice(MAILGUN_NOTICE, authenticated=True, source="forwarded-email")

    def test_requires_all_probation_disablement_terms(self):
        incomplete = MAILGUN_NOTICE.replace("temporarily disabled", "delayed")
        with self.assertRaises(SignalRejected):
            classify_notice(incomplete, authenticated=True, source="mailgun")

    def test_requires_accepted_hourly_limit_and_bounded_enable_estimate(self):
        with self.assertRaises(SignalRejected):
            classify_notice(
                MAILGUN_NOTICE.replace("100 messages", "200 messages"),
                authenticated=True,
                source="mailgun",
            )
        with self.assertRaises(SignalRejected):
            classify_notice(
                MAILGUN_NOTICE.replace("1754 seconds", "86401 seconds"),
                authenticated=True,
                source="mailgun",
            )


class WindowPolicyTests(unittest.TestCase):
    def setUp(self):
        accepted = IncidentRegistry().accept(incident())
        self.state = accepted.state

    def test_three_hour_hold_and_seventy_two_hour_probation_are_half_open(self):
        self.assertEqual(self.state.hold_until, T0 + timedelta(hours=3))
        self.assertEqual(self.state.probation_until, T0 + timedelta(hours=72))

        self.assertFalse(queue_hold_active(self.state, T0 - timedelta(microseconds=1)))
        self.assertTrue(queue_hold_active(self.state, T0))
        self.assertTrue(
            queue_hold_active(self.state, T0 + timedelta(hours=3) - timedelta(microseconds=1))
        )
        self.assertFalse(queue_hold_active(self.state, T0 + timedelta(hours=3)))

        self.assertFalse(trigger_probation_active(self.state, T0 - timedelta(microseconds=1)))
        self.assertTrue(trigger_probation_active(self.state, T0))
        self.assertTrue(
            trigger_probation_active(
                self.state, T0 + timedelta(hours=72) - timedelta(microseconds=1)
            )
        )
        self.assertFalse(trigger_probation_active(self.state, T0 + timedelta(hours=72)))

    def test_hold_uses_maximum_of_three_hours_and_provider_estimate(self):
        short = incident(seconds=1754)
        self.assertEqual(short.provider_enable_estimate, T0 + timedelta(seconds=1754))
        self.assertEqual(short.hold_until, T0 + timedelta(hours=3))

        long = incident(event_id="mailgun-event-long", seconds=4 * 60 * 60)
        self.assertEqual(long.provider_enable_estimate, T0 + timedelta(hours=4))
        self.assertEqual(long.hold_until, T0 + timedelta(hours=4))


class IncidentReconciliationTests(unittest.TestCase):
    def test_exact_duplicate_is_idempotent(self):
        registry = IncidentRegistry()
        original = incident()
        first = registry.accept(original)
        replay = registry.accept(original)

        self.assertEqual(first.result, "accepted")
        self.assertEqual(replay.result, "idempotent_replay")
        self.assertEqual(replay.state, first.state)
        self.assertEqual(replay.state.incident_ids, (original.provider_event_id,))

    def test_conflicting_duplicate_is_rejected_without_mutation(self):
        registry = IncidentRegistry()
        original = registry.accept(incident()).state
        conflicting = incident(trigger_ref="trigger:different")

        with self.assertRaises(DuplicateIncidentConflict):
            registry.accept(conflicting)
        self.assertEqual(
            registry.state_for(original.account_ref, original.domain_ref, original.trigger_ref),
            original,
        )
        unrelated = registry.state_for(
            original.account_ref, original.domain_ref, "trigger:different"
        )
        self.assertIsNotNone(unrelated)
        self.assertEqual(unrelated.hold_until, original.hold_until)
        self.assertFalse(trigger_probation_active(unrelated, T0))

    def test_distinct_incident_extends_and_never_shortens_windows(self):
        registry = IncidentRegistry()
        first = registry.accept(incident()).state
        later = registry.accept(
            incident("mailgun-event-002", received_at=T0 + timedelta(hours=1))
        ).state
        self.assertEqual(later.hold_until, T0 + timedelta(hours=4))
        self.assertEqual(later.probation_until, T0 + timedelta(hours=73))

        stale = registry.accept(
            incident("mailgun-event-003", received_at=T0 - timedelta(hours=1))
        ).state
        self.assertEqual(stale.hold_until, later.hold_until)
        self.assertEqual(stale.probation_until, later.probation_until)
        self.assertGreaterEqual(stale.hold_until, first.hold_until)
        self.assertGreaterEqual(stale.probation_until, first.probation_until)

    def test_route_hold_is_global_while_probation_is_per_trigger(self):
        registry = IncidentRegistry()
        first = registry.accept(incident(trigger_ref="trigger:a")).state
        registry.accept(
            incident(
                "mailgun-event-b",
                received_at=T0 + timedelta(hours=1),
                trigger_ref="trigger:b",
            )
        )
        trigger_a = registry.state_for(first.account_ref, first.domain_ref, "trigger:a")
        trigger_b = registry.state_for(first.account_ref, first.domain_ref, "trigger:b")
        unrelated = registry.state_for(first.account_ref, first.domain_ref, "trigger:unrelated")
        self.assertEqual(trigger_a.hold_until, T0 + timedelta(hours=4))
        self.assertEqual(trigger_b.hold_until, T0 + timedelta(hours=4))
        self.assertEqual(unrelated.hold_until, T0 + timedelta(hours=4))
        self.assertEqual(trigger_a.probation_until, T0 + timedelta(hours=72))
        self.assertEqual(trigger_b.probation_until, T0 + timedelta(hours=73))
        self.assertFalse(trigger_probation_active(unrelated, T0 + timedelta(hours=2)))


class ControlledReleaseTests(unittest.TestCase):
    def setUp(self):
        registry = IncidentRegistry()
        self.offending = registry.accept(incident()).state
        self.state = registry.state_for(
            self.offending.account_ref,
            self.offending.domain_ref,
            "trigger:unrelated",
        )
        self.release_at = self.state.hold_until

    def readback(self, *, enabled=True, observed_at=None, account_ref=None, domain_ref=None):
        return ProviderReadback(
            account_ref=account_ref or self.state.account_ref,
            domain_ref=domain_ref or self.state.domain_ref,
            enabled=enabled,
            observed_at=observed_at or self.release_at,
        )

    def decide(self, *, now=None, readback=None, pending=5, sent=()):
        return controlled_release(
            self.state,
            now=now or self.release_at,
            provider_readback=readback,
            pending_count=pending,
            sent_at=sent,
        )

    def test_release_requires_hold_expiry_and_fresh_enabled_readback(self):
        still_held = self.decide(
            now=self.release_at - timedelta(microseconds=1),
            readback=self.readback(observed_at=self.release_at - timedelta(microseconds=1)),
        )
        self.assertEqual((still_held.allowed_count, still_held.reason), (0, "queue_hold_active"))

        missing = self.decide(readback=None)
        disabled = self.decide(readback=self.readback(enabled=False))
        stale = self.decide(
            readback=self.readback(observed_at=self.release_at - timedelta(microseconds=1))
        )
        wrong_scope = self.decide(readback=self.readback(domain_ref="other.example"))
        self.assertEqual(missing.reason, "provider_enabled_readback_required")
        self.assertEqual(disabled.reason, "provider_enabled_readback_required")
        self.assertEqual(stale.reason, "provider_readback_stale")
        self.assertEqual(wrong_scope.reason, "provider_readback_scope_mismatch")

        enabled = self.decide(readback=self.readback())
        self.assertEqual((enabled.allowed_count, enabled.reason), (2, "controlled_release"))

    def test_offending_trigger_remains_blocked_after_route_hold(self):
        readback = ProviderReadback(
            account_ref=self.offending.account_ref,
            domain_ref=self.offending.domain_ref,
            enabled=True,
            observed_at=self.release_at,
        )
        decision = controlled_release(
            self.offending,
            now=self.release_at,
            provider_readback=readback,
            pending_count=5,
            sent_at=(),
        )
        self.assertEqual((decision.allowed_count, decision.reason), (0, "trigger_probation_active"))

    def test_controlled_batch_is_minimum_of_two_pending_and_budget(self):
        readback = self.readback()
        self.assertEqual(self.decide(readback=readback, pending=50).allowed_count, 2)
        self.assertEqual(self.decide(readback=readback, pending=1).allowed_count, 1)
        self.assertEqual(self.decide(readback=readback, pending=0).allowed_count, 0)

    def test_rolling_ten_per_hour_budget_boundaries(self):
        readback = self.readback()
        recent = lambda count: [
            self.release_at - timedelta(minutes=30, microseconds=index) for index in range(count)
        ]

        with_eight = self.decide(readback=readback, sent=recent(8))
        with_nine = self.decide(readback=readback, sent=recent(9))
        with_ten = self.decide(readback=readback, sent=recent(10))
        self.assertEqual((with_eight.rolling_used, with_eight.allowed_count), (8, 2))
        self.assertEqual((with_nine.rolling_used, with_nine.allowed_count), (9, 1))
        self.assertEqual((with_ten.rolling_used, with_ten.allowed_count), (10, 0))
        self.assertEqual(with_ten.reason, "rolling_hourly_limit_reached")

        exact_boundary = [self.release_at - timedelta(hours=1), *recent(9)]
        after_boundary = [
            self.release_at - timedelta(hours=1) + timedelta(microseconds=1),
            *recent(9),
        ]
        boundary_decision = self.decide(readback=readback, sent=exact_boundary)
        after_decision = self.decide(readback=readback, sent=after_boundary)
        self.assertEqual((boundary_decision.rolling_used, boundary_decision.allowed_count), (9, 1))
        self.assertEqual((after_decision.rolling_used, after_decision.allowed_count), (10, 0))

    def test_future_send_timestamp_fails_closed(self):
        with self.assertRaises(ValueError):
            self.decide(
                readback=self.readback(),
                sent=[self.release_at + timedelta(microseconds=1)],
            )


class ProductionSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.root = root
        cls.relay = (root / "supabase/functions/mailgun-relay-control/index.ts").read_text()
        cls.dispatcher = (root / "supabase/functions/penta-mail/index.ts").read_text()
        cls.os_worker = (
            root / "supabase/functions/crownthrive-os-v2-runtime/index.ts"
        ).read_text()
        cls.migration_paths = (
            "supabase/migrations/20260826234739_pentamail_mailgun_probation_queue_control.sql",
            "supabase/migrations/20260827001419_pentamail_receipt_chain_epoch_correction.sql",
            "supabase/migrations/20260827001902_pentamail_provider_control_fk_indexes.sql",
            "supabase/migrations/20260827002646_os_v2_notification_trigger_identity.sql",
            "supabase/migrations/20260827003843_pentamail_notification_recipient_privacy_boundary.sql",
            "supabase/migrations/20260827005615_pentamail_probation_concurrency_hardening.sql",
            "supabase/migrations/20260827010541_os_v2_governed_notification_claim.sql",
            "supabase/migrations/20260827010838_pentamail_incident_projection_fix.sql",
            "supabase/migrations/20260827011146_pentamail_receipt_epoch_anchor_hardening.sql",
            "supabase/migrations/20260827011347_pentamail_service_role_assertion_hardening.sql",
            "supabase/migrations/20260827011427_pentamail_readback_probe_ordering.sql",
        )
        cls.migrations = {path: (root / path).read_text() for path in cls.migration_paths}
        cls.main_sql = cls.migrations[cls.migration_paths[0]]
        cls.correction_sql = cls.migrations[cls.migration_paths[1]]
        cls.trigger_sql = cls.migrations[cls.migration_paths[3]]
        cls.privacy_sql = cls.migrations[cls.migration_paths[4]]
        cls.hardening_sql = cls.migrations[cls.migration_paths[5]]
        cls.os_claim_sql = cls.migrations[cls.migration_paths[6]]
        cls.incident_projection_sql = cls.migrations[cls.migration_paths[7]]
        cls.receipt_anchor_sql = cls.migrations[cls.migration_paths[8]]
        cls.service_role_assertion_sql = cls.migrations[cls.migration_paths[9]]
        cls.ordered_readback_sql = cls.migrations[cls.migration_paths[10]]
        cls.workflow = (
            root / ".github/workflows/pentamailer-mailgun-delivery-resilience.yml"
        ).read_text()
        cls.deployment_receipt = json.loads(
            (
                root
                / "developers/manifests/pentamailer-mailgun-deployment-receipt.v1.json"
            ).read_text()
        )
        cls.version_registry = json.loads(
            (root / "docs/versioning/VERSION_REGISTRY.json").read_text()
        )

    def test_incident_identity_is_bound_to_attempt_not_response_text(self):
        self.assertIn("p_provider_event_id: `mailgun-api:${providerAttemptId}`", self.relay)
        self.assertNotIn("p_provider_event_id: `mailgun-api:${responseSha}`", self.relay)
        self.assertIn("penta_mail_start_mailgun_attempt_v1", self.relay)
        self.assertIn("penta_mail_accept_mailgun_probation_v3", self.relay)
        self.assertIn("PENTAMAIL_PROVIDER_EVENT_CONFLICT", self.hardening_sql)

    def test_provider_calls_have_bounded_time_and_ambiguous_outcomes_stop(self):
        self.assertIn("AbortSignal.timeout(15000)", self.relay)
        self.assertIn("AbortSignal.timeout(30000)", self.relay)
        self.assertIn("penta_mail_start_mailgun_attempt_v1", self.relay)
        self.assertIn("penta_mail_record_mailgun_attempt_outcome_v1", self.relay)
        self.assertIn('p_outcome_state: "ambiguous"', self.relay)
        self.assertIn("reconciliation_required: true", self.relay)
        self.assertIn("penta_mail_complete_outbox_v3", self.dispatcher)
        self.assertIn("state = 'reconciliation_required'", self.hardening_sql)
        self.assertIn("`penta-outbox:${m.message_id}`", self.dispatcher)
        self.assertNotIn("`${m.message_id}:${m.lease_id}`", self.dispatcher)

    def test_readback_and_start_barriers_fail_closed(self):
        for token in (
            "last_readback_enabled is not true",
            "last_readback_at is distinct from v_control.enabled_readback_at",
            "mailgun:relay.crownthrive.com:send-control",
            "penta_mail_reserve_mailgun_rate_v2",
        ):
            self.assertIn(token, self.hardening_sql + self.main_sql)
        self.assertIn("penta_mail_record_mailgun_readback_v3", self.relay)
        self.assertIn("last_readback_probe_started_at", self.ordered_readback_sql)
        self.assertIn("ignored_out_of_order", self.ordered_readback_sql)
        self.assertIn("probe_started_at", self.ordered_readback_sql)
        self.assertIn("else null", self.main_sql)

    def test_only_governed_v3_incident_and_ordered_readback_rpcs_are_exposed(self):
        self.assertIn("penta_mail_accept_mailgun_probation_v3", self.relay)
        self.assertIn("penta_mail_record_mailgun_readback_v3", self.relay)
        self.assertIn(
            "revoke execute on function public.penta_mail_accept_mailgun_probation_v2",
            self.incident_projection_sql,
        )
        self.assertIn(
            "grant execute on function public.penta_mail_accept_mailgun_probation_v3",
            self.incident_projection_sql,
        )
        self.assertIn(
            "revoke execute on function public.penta_mail_record_mailgun_readback_v2",
            self.ordered_readback_sql,
        )
        self.assertIn(
            "grant execute on function public.penta_mail_record_mailgun_readback_v3",
            self.ordered_readback_sql,
        )

    def test_controlled_release_is_two_across_workers_and_route(self):
        self.assertIn("Math.min(2", self.os_worker)
        self.assertIn("claim_mail_notifications_v1(${boundedLimit})", self.os_worker)
        self.assertIn("least(coalesce(p_limit, 2), 2)", self.os_claim_sql)
        self.assertIn("p.probation_until > v_now", self.os_claim_sql)
        self.assertIn("for update skip locked", self.os_claim_sql)
        self.assertIn("controlled_release_batch_limit", self.hardening_sql)
        self.assertIn("v_batch_count >= 2", self.hardening_sql)
        self.assertIn("reserved_at > clock_timestamp() - interval '1 minute'", self.hardening_sql)
        self.assertIn("p_limit:2", self.dispatcher)

    def test_probation_events_are_coalesced_into_a_queued_digest(self):
        for token in (
            "coalesced_queued_during_trigger_probation",
            "trigger_probation_digest",
            "available_at = greatest(available_at, v_probation_until)",
            "deferred_event_count",
        ):
            self.assertIn(token, self.trigger_sql + self.hardening_sql)
        self.assertNotIn("'notification_state', 'suppressed_during_trigger_probation'", self.trigger_sql)
        self.assertEqual(self.deployment_receipt["live_readback"]["queued_probation_digests"], 1)
        self.assertGreater(
            self.deployment_receipt["live_readback"]["coalesced_digest_event_count"],
            1,
        )

    def test_provider_payload_is_digest_only_at_public_boundary(self):
        self.assertIn("`${response.status}\\n${responseText}`", self.relay)
        self.assertNotIn("message: providerMessage", self.relay)
        self.assertIn("raw_provider_body_retained", self.relay)

    def test_private_recipient_is_resolved_only_through_governed_database_policy(self):
        for token in (
            "penta_mail_notification_recipient_v1",
            "penta_mail_recipient_allowed_v1",
            "os_v2.system_notification_preferences",
            "to service_role",
        ):
            self.assertIn(token, self.privacy_sql)
        self.assertIn('rpc("penta_mail_notification_recipient_v1")', self.dispatcher)
        self.assertIn('rpc<boolean>("penta_mail_recipient_allowed_v1"', self.relay)

    def test_changed_public_sources_contain_no_private_recipient_literal(self):
        sources = "\n".join(
            [self.relay, self.dispatcher, self.os_worker, *self.migrations.values()]
        )
        addresses = {
            value.lower()
            for value in re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", sources, re.I)
        }
        self.assertLessEqual(addresses, {"contact@crownthrive.com"})

    def test_receipt_epoch_is_immutably_anchored_and_mutations_are_revoked(self):
        for token in (
            "penta_mail_receipt_epoch_anchor_fk_v1",
            "foreign key (starts_after_receipt_id, starts_after_chain_sha256)",
            "penta_mail_validate_receipt_epoch_anchor_v1",
            "revoke insert, update, delete, truncate",
            "from service_role",
        ):
            self.assertIn(token, self.receipt_anchor_sql)
        for token in (
            "revoke insert, update, delete, truncate on integration_control.penta_mail_provider_control_v1 from service_role",
            "revoke insert, update, delete, truncate on integration_control.penta_mail_trigger_probation_v1 from service_role",
            "revoke insert, update, delete, truncate on public.penta_mail_outbox_v1 from service_role",
        ):
            self.assertIn(token, self.hardening_sql)
        security = self.deployment_receipt["security_readback"]
        self.assertFalse(security["service_role_direct_provider_control_update"])
        self.assertFalse(security["service_role_direct_trigger_probation_update"])
        self.assertFalse(security["service_role_direct_outbox_update"])
        self.assertFalse(security["service_role_direct_receipt_epoch_insert"])
        self.assertTrue(self.deployment_receipt["receipt_chain_readback"]["anchor_verified"])

    def test_service_role_assertion_checks_invoker_not_security_definer_owner(self):
        self.assertIn(
            "session_user not in ('postgres','service_role')",
            self.service_role_assertion_sql,
        )
        self.assertIn(
            "current_setting('request.jwt.claim.role', true)",
            self.service_role_assertion_sql,
        )

    def test_receipt_and_version_registry_cover_the_final_control_plane(self):
        expected_names = [
            Path(path).stem.split("_", 1)[1] for path in self.migration_paths
        ]
        self.assertEqual(
            [entry["name"] for entry in self.deployment_receipt["database_migrations"]],
            expected_names,
        )
        component = next(
            entry
            for entry in self.version_registry["components"]
            if entry["component_id"] == "ct.pentamailer.mailgun-delivery-resilience"
        )
        self.assertEqual(
            component["evidence_ref"],
            "developers/manifests/pentamailer-mailgun-deployment-receipt.v1.json",
        )

    def test_workflow_tracks_every_governed_migration_and_evidence_asset(self):
        tracked_paths = (
            *self.migration_paths,
            "developers/manifests/pentamailer-mailgun-deployment-receipt.v1.json",
            "docs/versioning/VERSION_REGISTRY.json",
        )
        for path in tracked_paths:
            with self.subTest(path=path):
                self.assertEqual(self.workflow.count(f"- '{path}'"), 2)
        for token in (
            "penta_mail_accept_mailgun_probation_v3",
            "penta_mail_record_mailgun_readback_v3",
            "penta_mail_start_mailgun_attempt_v1",
            "penta_mail_record_mailgun_attempt_outcome_v1",
            "AbortSignal.timeout(15000)",
            "AbortSignal.timeout(30000)",
            "claim_mail_notifications_v1(${boundedLimit})",
            "v_batch_count >= 2",
            "interval '1 minute'",
            "penta_mail_receipt_epoch_anchor_fk_v1",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.workflow)


if __name__ == "__main__":
    unittest.main()
