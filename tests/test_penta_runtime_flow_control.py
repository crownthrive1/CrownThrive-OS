import concurrent.futures
import dataclasses
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from penta.runtime.flow_control import (
    AdmissionConflict,
    AuthorityError,
    AuthorityReceipt,
    BackpressureError,
    CostCeilingError,
    ExceptionLedger,
    LeaseError,
    LoadSnapshot,
    PentaBalancer,
    PentaBudget,
    PentaCostLedger,
    PentaForecast,
    PentaFlowControl,
    PentaMeter,
    PentaRate,
    QueueCapacityError,
    StaleLoadError,
)
from penta.runtime.flow_control.core import RetentionCapacityError


NOW = 1_800_000_000
SCOPE = "factory.candidate.execute"
ISSUER = "controlled-test-configured-issuer"
ENVIRONMENT = "controlled-test"


class PentaRuntimeFlowControlTests(unittest.TestCase):
    def runtime(
        self,
        *,
        capacity=2,
        ceiling=100,
        receipt_expires=NOW + 600,
        max_resident=4,
        max_retained=None,
    ):
        runtime = PentaFlowControl(
            max_resident_jobs=max_resident,
            max_retained_jobs=max_retained,
            registered_rates=(self.rate(),),
        )
        runtime.load.observe(LoadSnapshot("factory-a", capacity, 0, NOW, 60))
        runtime.costs.configure("factory-a", ceiling_units=ceiling)
        runtime.authority.register(
            AuthorityReceipt(
                "receipt-1",
                "worker-1",
                (SCOPE,),
                NOW - 1,
                receipt_expires,
                "evidence:founder:bounded-approval",
                ISSUER,
                ENVIRONMENT,
            )
        )
        return runtime

    @staticmethod
    def rate(*, operation="build", units=1):
        return PentaRate.create(
            rate_book_id="controlled-test-rates",
            version="1.0.0",
            effective_at=NOW,
            rates={operation: units},
            evidence_ref="rate-source:controlled-test",
        )

    def complete(self, runtime, claim, *, result=None, now=NOW + 1, operation="build", quantity=1):
        return runtime.complete(
            claim,
            result={"readback": "local"} if result is None else result,
            operation=operation,
            quantity=quantity,
            rate=self.rate(operation=operation),
            usage_evidence_ref="worker-readback:controlled-test",
            now=now,
        )

    @staticmethod
    def admit(runtime, key="request-1", *, priority=50, cost=10, attempts=2, routes=("factory-a",)):
        return runtime.queue.admit(
            idempotency_key=key,
            payload={"objective": key},
            priority=priority,
            route_candidates=routes,
            required_scope=SCOPE,
            estimated_cost_units=cost,
            max_attempts=attempts,
            now=NOW,
        )

    def claim(self, runtime, *, now=NOW, lease_seconds=30):
        return runtime.claim(
            worker_id="worker-1",
            authority_receipt_id="receipt-1",
            lease_seconds=lease_seconds,
            now=now,
        )

    def test_idempotent_admission_and_conflicting_reuse(self):
        runtime = self.runtime()
        first = self.admit(runtime)
        replay = self.admit(runtime)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(first.job_id, replay.job_id)
        with self.assertRaises(AdmissionConflict):
            self.admit(runtime, cost=11)

    def test_bounded_queue_releases_capacity_only_at_terminal_state(self):
        runtime = self.runtime(max_resident=1)
        self.admit(runtime, "one")
        with self.assertRaises(QueueCapacityError):
            self.admit(runtime, "two")
        claim = self.claim(runtime)
        self.complete(runtime, claim)
        second = self.admit(runtime, "two")
        self.assertFalse(second.idempotent_replay)

    def test_concurrent_idempotent_admission_creates_one_job(self):
        runtime = PentaFlowControl(max_resident_jobs=2)

        def admit(_):
            return self.admit(runtime, "same-request")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(admit, range(64)))
        self.assertEqual(len({result.job_id for result in results}), 1)
        self.assertEqual(sum(not result.idempotent_replay for result in results), 1)

    def test_higher_priority_is_claimed_first(self):
        runtime = self.runtime()
        low = self.admit(runtime, "low", priority=1)
        high = self.admit(runtime, "high", priority=100)
        claim = self.claim(runtime)
        self.assertEqual(claim.job_id, high.job_id)
        self.assertNotEqual(claim.job_id, low.job_id)

    def test_cost_ceiling_is_checked_before_lease(self):
        runtime = self.runtime(ceiling=5)
        admission = self.admit(runtime, cost=6)
        with self.assertRaises(CostCeilingError):
            self.claim(runtime)
        snapshot = runtime.queue.snapshot(admission.job_id)
        self.assertEqual(snapshot["state"], "queued")
        self.assertEqual(snapshot["attempts"], 0)
        self.assertEqual(snapshot["fencing_token"], 0)
        self.assertEqual(runtime.load.local_inflight("factory-a"), 0)

    def test_missing_cost_ceiling_fails_closed(self):
        runtime = PentaFlowControl(max_resident_jobs=1)
        runtime.load.observe(LoadSnapshot("factory-a", 1, 0, NOW, 60))
        runtime.authority.register(
            AuthorityReceipt(
                "receipt-1",
                "worker-1",
                (SCOPE,),
                NOW - 1,
                NOW + 10,
                "evidence:1",
                ISSUER,
                ENVIRONMENT,
            )
        )
        admission = self.admit(runtime)
        with self.assertRaises(CostCeilingError):
            self.claim(runtime)
        self.assertEqual(runtime.queue.snapshot(admission.job_id)["state"], "queued")

    def test_stale_load_fails_closed_without_reserving_cost(self):
        runtime = self.runtime()
        runtime.load.observe(LoadSnapshot("factory-a", 2, 0, NOW + 61, 60))
        self.admit(runtime)
        with self.assertRaises(StaleLoadError):
            self.claim(runtime, now=NOW)
        self.assertEqual(runtime.costs.status("factory-a")["reserved_units"], 0)

    def test_fresh_full_capacity_applies_backpressure(self):
        runtime = self.runtime(capacity=1)
        runtime.load.observe(LoadSnapshot("factory-a", 1, 1, NOW + 1, 60))
        self.admit(runtime)
        with self.assertRaises(BackpressureError):
            self.claim(runtime, now=NOW + 1)

    def test_balancing_is_deterministic_and_input_order_independent(self):
        runtime = self.runtime()
        runtime.load.observe(LoadSnapshot("factory-b", 2, 0, NOW, 60))
        runtime.costs.configure("factory-b", ceiling_units=100)
        routes = runtime.load.eligible(("factory-b", "factory-a"), now=NOW)
        forward = PentaBalancer.choose("job-stable", routes)
        reverse = PentaBalancer.choose("job-stable", tuple(reversed(routes)))
        self.assertEqual(forward.route_id, reverse.route_id)
        self.assertIn(forward.route_id, {"factory-a", "factory-b"})

    def test_lease_is_capped_by_authority_expiry(self):
        runtime = self.runtime(receipt_expires=NOW + 5)
        self.admit(runtime)
        claim = self.claim(runtime, lease_seconds=60)
        self.assertEqual(claim.lease_expires_at, NOW + 5)
        with self.assertRaises(LeaseError):
            runtime.validate_claim(claim, now=NOW + 5)

    def test_revocation_invalidates_an_existing_claim(self):
        runtime = self.runtime()
        self.admit(runtime)
        claim = self.claim(runtime)
        runtime.authority.revoke("receipt-1", now=NOW + 1, reason="founder stop")
        with self.assertRaises(AuthorityError):
            runtime.validate_claim(claim, now=NOW + 1)
        with self.assertRaises(AuthorityError):
            self.complete(runtime, claim, result={"readback": "ok"})

    def test_fencing_rejects_old_worker_after_expiry_and_retry(self):
        runtime = self.runtime()
        admission = self.admit(runtime)
        first = self.claim(runtime, lease_seconds=5)
        runtime.reap_expired(retry_delay_seconds=0, now=NOW + 5)
        second = self.claim(runtime, now=NOW + 5, lease_seconds=5)
        self.assertGreater(second.fencing_token, first.fencing_token)
        with self.assertRaises(LeaseError):
            self.complete(runtime, first, result={}, now=NOW + 6)
        self.assertEqual(runtime.queue.snapshot(admission.job_id)["fencing_token"], 2)

    def test_retry_exhaustion_moves_to_dead_letter(self):
        runtime = self.runtime()
        admission = self.admit(runtime, attempts=2)
        first = self.claim(runtime)
        state = runtime.fail(
            first,
            exception_class="ProviderError",
            code="timeout",
            message="request 101 timed out",
            evidence_ref="raw:1",
            retry_delay_seconds=0,
            now=NOW + 1,
        )
        self.assertEqual(state["state"], "queued")
        second = self.claim(runtime, now=NOW + 1)
        state = runtime.fail(
            second,
            exception_class="ProviderError",
            code="timeout",
            message="request 102 timed out",
            evidence_ref="raw:2",
            retry_delay_seconds=0,
            now=NOW + 2,
        )
        self.assertEqual(state["state"], "dead_letter")
        self.assertEqual(runtime.queue.snapshot(admission.job_id)["attempts"], 2)

    def test_completion_is_verification_not_certification_or_provider_effect(self):
        runtime = self.runtime()
        self.admit(runtime)
        claim = self.claim(runtime)
        result = self.complete(runtime, claim, result={"local_tests": "pass"})
        self.assertEqual(result["state"], "implementation_verified")
        self.assertFalse(result["certification_effect"])
        self.assertFalse(result["provider_effect"])
        self.assertFalse(result["money_movement"])

    def test_exception_consolidation_preserves_every_raw_evidence_record(self):
        ledger = ExceptionLedger()
        ledger.record(
            exception_class="ProviderError",
            code="timeout",
            message="job 101 timed out with trace abcdef0123456789",
            evidence_ref="raw:101",
            observed_at=NOW,
        )
        ledger.record(
            exception_class="ProviderError",
            code="timeout",
            message="job 202 timed out with trace fedcba9876543210",
            evidence_ref="raw:202",
            observed_at=NOW + 1,
        )
        report = ledger.report()
        self.assertEqual(report["raw_evidence_count"], 2)
        self.assertEqual(report["fingerprint_count"], 1)
        self.assertEqual(report["groups"][0]["raw_evidence_count"], 2)
        self.assertEqual(report["groups"][0]["evidence_refs"], ["raw:101", "raw:202"])
        self.assertEqual(len(report["raw_evidence"]), 2)

    def test_report_declares_nonvoting_noncertifying_no_money_movement(self):
        report = self.runtime().report()
        self.assertFalse(report["quorum_eligible"])
        self.assertFalse(report["vote_eligible"])
        self.assertFalse(report["certification_effect"])
        self.assertFalse(report["money_movement"])

    def test_runtime_objects_are_json_serializable_and_schema_conformant(self):
        runtime = self.runtime()
        self.admit(runtime)
        claim = self.claim(runtime)
        self.complete(runtime, claim)
        schema = json.loads(
            (Path(__file__).resolve().parents[1] / "schemas/penta/runtime-flow-control.schema.json").read_text()
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        objects = [
            runtime.authority._receipts["receipt-1"].to_dict(),
            runtime.load._snapshots["factory-a"].to_dict(),
            self.rate().to_dict(),
            claim.to_dict(),
            runtime.costs.meter.records()[0].to_dict(),
            runtime.costs.status("factory-a"),
            runtime.costs.ledger.entries()[0].to_dict(),
            PentaForecast.project([1], periods=1).to_dict(),
            runtime.exceptions.report(),
            runtime.report(),
        ]
        for item in objects:
            json.dumps(item)
            self.assertEqual(list(validator.iter_errors(item)), [], item["schema"])

        admission = {
            "schema": "ct.penta.runtime-flow-control.admission.v1",
            "idempotency_key": "schema-admission",
            "payload": {},
            "priority": 1,
            "route_candidates": ["factory-a"],
            "required_scope": SCOPE,
            "estimated_cost_units": 1,
            "max_attempts": 1,
        }
        self.assertEqual(list(validator.iter_errors(admission)), [])
        for field, invalid in (
            ("required_scope", "factory.*"),
            ("estimated_cost_units", (1 << 63)),
            ("idempotency_key", "bad\nkey"),
        ):
            candidate = dict(admission)
            candidate[field] = invalid
            self.assertTrue(list(validator.iter_errors(candidate)), field)

    def test_stop_control_is_irreversible_and_preserves_failure_recovery(self):
        runtime = self.runtime()
        self.admit(runtime)
        claim = self.claim(runtime)
        first = runtime.stop(
            reason="release rollback drill",
            evidence_ref="recovery:controlled-test:v1",
            now=NOW + 1,
        )
        replay = runtime.stop(
            reason="different text cannot rewrite custody",
            evidence_ref="recovery:other",
            now=NOW + 2,
        )
        self.assertEqual(first, replay)
        self.assertFalse(runtime.report()["queue"]["new_admission_enabled"])
        with self.assertRaises(QueueCapacityError):
            self.admit(runtime, key="blocked-after-stop")
        failed = runtime.fail(
            claim,
            exception_class="RecoveryStop",
            code="rollback_drill",
            message="controlled-test stop",
            evidence_ref="recovery:controlled-test:v1",
            retry_delay_seconds=0,
            now=NOW + 1,
        )
        self.assertEqual(failed["state"], "queued")

    def test_completion_requires_configured_rate_and_respects_reservation(self):
        runtime = self.runtime(ceiling=10)
        self.admit(runtime, cost=1)
        claim = self.claim(runtime)
        conflicting = self.rate(units=100_000)
        with self.assertRaises(CostCeilingError):
            runtime.complete(
                claim,
                result={"readback": "local"},
                operation="build",
                quantity=1,
                rate=conflicting,
                usage_evidence_ref="worker-readback:controlled-test",
                now=NOW + 1,
            )
        with self.assertRaises(AdmissionConflict):
            runtime.costs.register_rate(conflicting)

        high = PentaRate.create(
            rate_book_id="controlled-test-high",
            version="1.0.0",
            effective_at=NOW,
            rates={"build": 2},
            evidence_ref="rate-source:controlled-test-high",
        )
        runtime.costs.register_rate(high)
        with self.assertRaises(CostCeilingError):
            runtime.complete(
                claim,
                result={"readback": "local"},
                operation="build",
                quantity=1,
                rate=high,
                usage_evidence_ref="worker-readback:controlled-test",
                now=NOW + 1,
            )
        self.assertEqual(runtime.queue.snapshot(claim.job_id)["state"], "leased")
        self.assertEqual(runtime.costs.status("factory-a")["reserved_units"], 1)
        self.assertEqual(runtime.costs.meter.records(), ())

    def test_exception_class_and_code_are_never_exposed(self):
        ledger = ExceptionLedger()
        ledger.record(
            exception_class="CLASSSECRET",
            code="CODESECRET",
            message="safe message",
            evidence_ref="safe:reference",
            observed_at=NOW,
        )
        encoded = json.dumps(ledger.report())
        self.assertNotIn("CLASSSECRET", encoded)
        self.assertNotIn("CODESECRET", encoded)
        self.assertIn("exception_class_digest", encoded)
        self.assertIn("code_digest", encoded)

    def test_rate_book_is_canonical_immutable_and_versioned(self):
        first = PentaRate.create(
            rate_book_id="factory-rates",
            version="1.0.0",
            effective_at=NOW,
            rates={"test": 3, "build": 5},
            evidence_ref="rate-source:v1",
        )
        second = PentaRate.create(
            rate_book_id="factory-rates",
            version="1.0.0",
            effective_at=NOW,
            rates={"build": 5, "test": 3},
            evidence_ref="rate-source:v1",
        )
        self.assertEqual(first.rates, (("build", 5), ("test", 3)))
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.estimate("test", 4), 12)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.version = "2.0.0"

    def test_future_effective_rate_cannot_be_used_early(self):
        future_rate = PentaRate.create(
            rate_book_id="future-rates",
            version="1.0.0",
            effective_at=NOW + 10,
            rates={"build": 1},
            evidence_ref="rate-source:future-controlled-test",
        )
        runtime = PentaFlowControl(max_resident_jobs=4, registered_rates=(future_rate,))
        runtime.load.observe(LoadSnapshot("factory-a", 1, 0, NOW, 60))
        runtime.costs.configure("factory-a", ceiling_units=10)
        runtime.authority.register(
            AuthorityReceipt(
                "receipt-1",
                "worker-1",
                (SCOPE,),
                NOW - 1,
                NOW + 600,
                "evidence:founder:bounded-approval",
                ISSUER,
                ENVIRONMENT,
            )
        )
        self.admit(runtime, cost=1)
        claim = self.claim(runtime)
        with self.assertRaises(CostCeilingError):
            runtime.complete(
                claim,
                result={"readback": "local"},
                operation="build",
                quantity=1,
                rate=future_rate,
                usage_evidence_ref="worker-readback:controlled-test",
                now=NOW + 1,
            )
        self.assertEqual(runtime.queue.snapshot(claim.job_id)["state"], "leased")

    def test_rate_book_rejects_negative_noninteger_and_overflow(self):
        for invalid in (-1, True, 1.5):
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, TypeError)):
                PentaRate.create(
                    rate_book_id="rates",
                    version="1",
                    effective_at=NOW,
                    rates={"build": invalid},
                    evidence_ref="rate-source",
                )
        rate = PentaRate.create(
            rate_book_id="rates",
            version="1",
            effective_at=NOW,
            rates={"build": (1 << 63) - 1},
            evidence_ref="rate-source",
        )
        with self.assertRaises(OverflowError):
            rate.estimate("build", 2)

    def test_meter_is_append_only_and_idempotent(self):
        meter = PentaMeter()
        rate = PentaRate.create(
            rate_book_id="rates",
            version="1",
            effective_at=NOW,
            rates={"build": 7},
            evidence_ref="rate-source",
        )
        first = meter.record(
            idempotency_key="usage-1",
            operation="build",
            quantity=3,
            rate=rate,
            evidence_ref="worker-readback:1",
            observed_at=NOW,
            job_id="job-1",
            route_id="factory-a",
            fencing_token=1,
            reservation_id="job-1:1",
            result_digest="0" * 64,
        )
        replay = meter.record(
            idempotency_key="usage-1",
            operation="build",
            quantity=3,
            rate=rate,
            evidence_ref="worker-readback:1",
            observed_at=NOW,
            job_id="job-1",
            route_id="factory-a",
            fencing_token=1,
            reservation_id="job-1:1",
            result_digest="0" * 64,
        )
        self.assertIs(first, replay)
        self.assertEqual(first.estimated_cost_units, 21)
        self.assertEqual(len(meter.records()), 1)
        with self.assertRaises(AdmissionConflict):
            meter.record(
                idempotency_key="usage-1",
                operation="build",
                quantity=4,
                rate=rate,
                evidence_ref="worker-readback:1",
                observed_at=NOW,
                job_id="job-1",
                route_id="factory-a",
                fencing_token=1,
                reservation_id="job-1:1",
                result_digest="0" * 64,
            )

    def test_cost_ledger_is_append_only_idempotent_and_operational_only(self):
        ledger = PentaCostLedger()
        args = {
            "idempotency_key": "entry-1",
            "event_type": "reservation_created",
            "route_id": "factory-a",
            "job_id": "job-1",
            "reservation_id": "job-1:1",
            "units": 5,
            "evidence_ref": "runtime:job-1:1",
        }
        first = ledger.record(**args)
        replay = ledger.record(**args)
        self.assertIs(first, replay)
        self.assertEqual(len(ledger.entries()), 1)
        self.assertFalse(ledger.accounting_source_of_truth)
        self.assertFalse(ledger.treasury_source_of_truth)
        self.assertFalse(ledger.money_movement)
        with self.assertRaises(AdmissionConflict):
            ledger.record(**{**args, "units": 6})

    def test_budget_reservation_lifecycle_appends_operational_entries(self):
        budget = PentaBudget()
        budget.configure("factory-a", ceiling_units=20)
        reservation = budget.reserve(
            job_id="job-1", fencing_token=1, route_id="factory-a", units=7
        )
        self.assertEqual(budget.status("factory-a")["reserved_units"], 7)
        budget.finalize(reservation.reservation_id)
        self.assertEqual(budget.status("factory-a")["accounted_units"], 7)
        self.assertEqual(
            [entry.event_type for entry in budget.ledger.entries()],
            ["reservation_created", "runtime_units_accounted"],
        )

    def test_budget_reservations_are_atomic_under_concurrency(self):
        budget = PentaBudget()
        budget.configure("factory-a", ceiling_units=10)

        def reserve(index):
            try:
                budget.reserve(
                    job_id=f"job-{index}",
                    fencing_token=1,
                    route_id="factory-a",
                    units=1,
                )
                return True
            except CostCeilingError:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            outcomes = list(pool.map(reserve, range(100)))
        self.assertEqual(sum(outcomes), 10)
        self.assertEqual(budget.status("factory-a")["reserved_units"], 10)
        self.assertEqual(len(budget.ledger.entries()), 10)

    def test_forecast_is_integer_advisory_and_never_authorizes_spend(self):
        forecast = PentaForecast.project([2, 3, 4], periods=5)
        self.assertEqual(forecast.projected_cost_units, 15)
        self.assertTrue(forecast.advisory_only)
        self.assertFalse(forecast.authorizes_spend)
        self.assertEqual(PentaForecast.project([], periods=0).projected_cost_units, 0)
        with self.assertRaises(ValueError):
            PentaForecast.project([], periods=1)
        with self.assertRaises(ValueError):
            PentaForecast.project([1], periods=-1)

    def test_forecast_rejects_integer_overflow(self):
        with self.assertRaises(OverflowError):
            PentaForecast.project([(1 << 63) - 1, 1], periods=1)
        with self.assertRaises(OverflowError):
            PentaForecast.project([(1 << 63) - 1], periods=2)

    def test_admission_payload_claim_and_candidate_views_are_deeply_immutable(self):
        runtime = self.runtime()
        source = {"objective": "build", "nested": {"steps": ["one"]}}
        admission = runtime.queue.admit(
            idempotency_key="immutable",
            payload=source,
            priority=50,
            route_candidates=("factory-a",),
            required_scope=SCOPE,
            estimated_cost_units=10,
            max_attempts=2,
            now=NOW,
        )
        source["nested"]["steps"].append("injected")
        candidate = runtime.queue.candidates(now=NOW)[0]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            candidate.priority = 100
        with self.assertRaises(TypeError):
            candidate.payload["objective"] = "mutated"
        with self.assertRaises(TypeError):
            candidate.payload["nested"]["steps"][0] = "mutated"
        claim = self.claim(runtime)
        self.assertEqual(claim.payload["nested"]["steps"], ["one"])
        self.assertEqual(runtime.queue.snapshot(admission.job_id)["priority"], 50)

    def test_every_claim_field_is_bound_to_lease_job_authority_and_reservation(self):
        runtime = self.runtime()
        self.admit(runtime)
        claim = self.claim(runtime)
        tampered = (
            dataclasses.replace(claim, job_id="job-unknown"),
            dataclasses.replace(claim, worker_id="worker-2"),
            dataclasses.replace(claim, route_id="factory-b"),
            dataclasses.replace(claim, fencing_token=claim.fencing_token + 1),
            dataclasses.replace(claim, lease_expires_at=claim.lease_expires_at - 1),
            dataclasses.replace(claim, attempt=claim.attempt + 1),
            dataclasses.replace(claim, payload={"objective": "different"}),
            dataclasses.replace(claim, authority_receipt_id="receipt-other"),
            dataclasses.replace(claim, cost_reservation_id="reservation-other"),
        )
        for altered in tampered:
            with self.subTest(field=altered), self.assertRaises((LeaseError, CostCeilingError)):
                runtime.validate_claim(altered, now=NOW + 1)
        self.assertEqual(runtime.queue.snapshot(claim.job_id)["state"], "leased")
        self.assertEqual(runtime.costs.status("factory-a")["reserved_units"], 10)
        self.assertEqual(runtime.load.local_inflight("factory-a"), 1)

    def test_completion_invalid_input_is_atomic_and_exact_replay_is_idempotent(self):
        runtime = self.runtime()
        self.admit(runtime)
        claim = self.claim(runtime)
        with self.assertRaises(ValueError):
            runtime.complete(
                claim,
                result={"invalid": object()},
                operation="build",
                quantity=1,
                rate=self.rate(),
                usage_evidence_ref="worker-readback:1",
                now=NOW + 1,
            )
        with self.assertRaises(CostCeilingError):
            runtime.complete(
                claim,
                result={"ok": True},
                operation="missing-operation",
                quantity=1,
                rate=self.rate(),
                usage_evidence_ref="worker-readback:1",
                now=NOW + 1,
            )
        self.assertEqual(runtime.queue.snapshot(claim.job_id)["state"], "leased")
        self.assertEqual(runtime.costs.status("factory-a")["reserved_units"], 10)
        self.assertEqual(runtime.load.local_inflight("factory-a"), 1)
        self.assertEqual(len(runtime.costs.meter.records()), 0)

        result_source = {"readback": {"checks": ["pass"]}}
        first = self.complete(runtime, claim, result=result_source)
        result_source["readback"]["checks"].append("injected")
        replay = self.complete(runtime, claim, result={"readback": {"checks": ["pass"]}}, now=NOW + 99)
        self.assertEqual(first, replay)
        self.assertEqual(replay["result"]["readback"]["checks"], ["pass"])
        self.assertEqual(len(runtime.costs.meter.records()), 1)
        usage = runtime.costs.meter.records()[0]
        self.assertEqual(usage.job_id, claim.job_id)
        self.assertEqual(usage.route_id, claim.route_id)
        self.assertEqual(usage.fencing_token, claim.fencing_token)
        self.assertEqual(usage.reservation_id, claim.cost_reservation_id)
        self.assertEqual(usage.result_digest, replay["result_digest"])
        with self.assertRaises(AdmissionConflict):
            self.complete(runtime, claim, result={"readback": {"checks": ["different"]}})
        self.assertEqual(len(runtime.costs.meter.records()), 1)

    def test_failure_and_reap_reject_negative_delay_without_partial_mutation(self):
        runtime = self.runtime()
        self.admit(runtime)
        claim = self.claim(runtime, lease_seconds=5)
        with self.assertRaises(ValueError):
            runtime.fail(
                claim,
                exception_class="ProviderError",
                code="timeout",
                message="timed out",
                evidence_ref="raw:1",
                retry_delay_seconds=-1,
                now=NOW + 1,
            )
        self.assertEqual(runtime.exceptions.report()["raw_evidence_count"], 0)
        self.assertEqual(runtime.queue.snapshot(claim.job_id)["state"], "leased")
        self.assertEqual(runtime.costs.status("factory-a")["reserved_units"], 10)
        self.assertEqual(runtime.load.local_inflight("factory-a"), 1)
        with self.assertRaises(ValueError):
            runtime.reap_expired(retry_delay_seconds=-1, now=NOW + 5)
        self.assertEqual(runtime.exceptions.report()["raw_evidence_count"], 0)
        self.assertEqual(runtime.queue.snapshot(claim.job_id)["state"], "leased")

    def test_load_ttl_is_exclusive_and_same_timestamp_conflict_fails_closed(self):
        load = self.runtime().load
        with self.assertRaises(StaleLoadError):
            load.eligible(("factory-a",), now=NOW + 60)
        exact = LoadSnapshot("factory-a", 2, 0, NOW, 60)
        load.observe(exact)
        with self.assertRaises(StaleLoadError):
            load.observe(LoadSnapshot("factory-a", 2, 1, NOW, 60))
        self.assertEqual(load.eligible(("factory-a",), now=NOW)[0].used, 0)

    def test_boolean_integer_overflow_attempt_and_timestamp_inputs_fail_closed(self):
        runtime = self.runtime()
        for field, value in (("priority", True), ("cost", True), ("attempts", True)):
            kwargs = {"priority": 50, "cost": 1, "attempts": 2}
            kwargs[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.admit(runtime, f"bad-{field}", **kwargs)
        with self.assertRaises(ValueError):
            self.admit(runtime, "too-many-attempts", attempts=101)
        with self.assertRaises(OverflowError):
            self.admit(runtime, "overflow-cost", cost=1 << 63)
        with self.assertRaises(ValueError):
            LoadSnapshot("factory-b", True, 0, NOW, 60)
        with self.assertRaises(ValueError):
            LoadSnapshot("factory-b", 1, 0, True, 60)
        self.admit(runtime, "valid")
        with self.assertRaises(ValueError):
            runtime.claim(
                worker_id="worker-1",
                authority_receipt_id="receipt-1",
                lease_seconds=True,
                now=NOW,
            )

    def test_wildcard_scopes_and_wrong_authority_context_are_rejected(self):
        scopes = [SCOPE]
        receipt = AuthorityReceipt(
            "receipt-scopes",
            "worker-1",
            scopes,
            NOW - 1,
            NOW + 10,
            "evidence:scope",
            ISSUER,
            ENVIRONMENT,
        )
        scopes.append("injected.scope")
        self.assertEqual(receipt.scopes, (SCOPE,))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            receipt.scopes = ("changed",)
        with self.assertRaises(ValueError):
            AuthorityReceipt(
                "wild",
                "worker-1",
                ("factory.*",),
                NOW,
                NOW + 1,
                "evidence:wild",
                ISSUER,
                ENVIRONMENT,
            )
        runtime = self.runtime()
        with self.assertRaises(ValueError):
            runtime.queue.admit(
                idempotency_key="wild-job",
                payload={},
                priority=1,
                route_candidates=("factory-a",),
                required_scope="*",
                estimated_cost_units=0,
                max_attempts=1,
                now=NOW,
            )
        with self.assertRaises(AuthorityError):
            runtime.authority.register(
                AuthorityReceipt(
                    "wrong-issuer",
                    "worker-1",
                    (SCOPE,),
                    NOW,
                    NOW + 1,
                    "evidence:wrong",
                    "untrusted-issuer",
                    ENVIRONMENT,
                )
            )
        with self.assertRaises(AuthorityError):
            runtime.authority.register(
                AuthorityReceipt(
                    "wrong-environment",
                    "worker-1",
                    (SCOPE,),
                    NOW,
                    NOW + 1,
                    "evidence:wrong",
                    ISSUER,
                    "production",
                )
            )

    def test_released_reservation_cannot_be_reused_for_same_job_and_fence(self):
        budget = PentaBudget(max_reservations=2)
        budget.configure("factory-a", ceiling_units=20)
        reservation = budget.reserve(
            job_id="job-1", fencing_token=1, route_id="factory-a", units=5
        )
        budget.release(reservation.reservation_id)
        with self.assertRaises(CostCeilingError):
            budget.reserve(job_id="job-1", fencing_token=1, route_id="factory-a", units=5)
        self.assertEqual(budget.status("factory-a")["reserved_units"], 0)

    def test_all_retained_runtime_histories_are_bounded_and_fail_closed(self):
        runtime = self.runtime(max_resident=1, max_retained=2)
        for key in ("one", "two"):
            self.admit(runtime, key)
            self.complete(runtime, self.claim(runtime))
        with self.assertRaises(RetentionCapacityError):
            self.admit(runtime, "three")
        with self.assertRaises(AttributeError):
            runtime.queue.max_retained_jobs = 100
        replay = self.admit(runtime, "one")
        self.assertTrue(replay.idempotent_replay)

        ledger = ExceptionLedger(max_records=1)
        ledger.record(
            exception_class="E", code="one", message="one", evidence_ref="raw:1", observed_at=NOW
        )
        with self.assertRaises(RetentionCapacityError):
            ledger.record(
                exception_class="E", code="two", message="two", evidence_ref="raw:2", observed_at=NOW
            )
        cost_ledger = PentaCostLedger(max_entries=1)
        base = {
            "event_type": "event",
            "route_id": "factory-a",
            "job_id": "job-1",
            "reservation_id": "job-1:1",
            "units": 1,
            "evidence_ref": "runtime:1",
        }
        cost_ledger.record(idempotency_key="one", **base)
        with self.assertRaises(RetentionCapacityError):
            cost_ledger.record(idempotency_key="two", **{**base, "job_id": "job-2"})

    def test_exception_report_redacts_secrets_and_keeps_http_status_semantics(self):
        ledger = ExceptionLedger()
        ledger.record(
            exception_class="ProviderError",
            code="http_error",
            message="HTTP 401 Bearer super.secret password=hunter2 user@example.com",
            evidence_ref="https://example.test/read?X-Amz-Signature=signed-secret",
            observed_at=NOW,
        )
        ledger.record(
            exception_class="ProviderError",
            code="http_error",
            message="HTTP 500 Bearer another.secret password=different admin@example.com",
            evidence_ref="https://example.test/read?token=private-token",
            observed_at=NOW + 1,
        )
        report = ledger.report()
        self.assertEqual(report["raw_evidence_count"], 2)
        self.assertEqual(report["fingerprint_count"], 2)
        rendered = repr(report)
        for secret in (
            "super.secret",
            "hunter2",
            "user@example.com",
            "signed-secret",
            "private-token",
        ):
            self.assertNotIn(secret, rendered)
        self.assertTrue(all(item["redacted"] for item in report["raw_evidence"]))
        self.assertTrue(all(len(item["evidence_ref_digest"]) == 64 for item in report["raw_evidence"]))

    def test_budget_status_and_runtime_report_are_truthful_operational_readbacks(self):
        runtime = self.runtime()
        status = runtime.costs.status("factory-a")
        self.assertEqual(status["schema"], "ct.penta.runtime-flow-control.budget-status.v1")
        self.assertEqual(status["route_id"], "factory-a")
        self.assertFalse(status["money_movement"])
        self.admit(runtime)
        claim = self.claim(runtime)
        self.complete(runtime, claim)
        report = runtime.report()
        self.assertEqual(report["lifecycle_state"], "CONTROLLED_TEST")
        self.assertFalse(report["external_effects_enabled"])
        self.assertFalse(report["durable_store_bound"])
        self.assertFalse(report["issuer_authentication"])
        self.assertEqual(report["queue"]["state_counts"]["implementation_verified"], 1)
        self.assertEqual(report["costs"]["meter"]["record_count"], 1)
        self.assertEqual(report["costs"]["reservation_states"]["accounted"], 1)
        self.assertFalse(report["certification_effect"])

    def test_manifest_bindings_reconcile_to_the_canonical_component_registry(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (root / "developers/manifests/penta-runtime-flow-control.v1.json").read_text()
        )
        registry_path = root / manifest["canonical_registry"]["path"]
        registry_bytes = registry_path.read_bytes()
        registry = json.loads(registry_bytes)
        self.assertEqual(manifest["canonical_registry"]["registry_id"], registry["registry_id"])
        self.assertEqual(manifest["canonical_registry"]["version"], registry["version"])
        self.assertEqual(
            manifest["canonical_registry"]["sha256"],
            hashlib.sha256(registry_bytes).hexdigest(),
        )
        canonical = {component["key"]: component for component in registry["components"]}
        for member in manifest["members"]:
            component = canonical[member["canonical_key"]]
            self.assertEqual(member["canonical_contract"], component["contract"])
            self.assertEqual(member["canonical_axis"], component["axis"])
            if member["name"] == "PentaQueue":
                self.assertEqual(member["registry_relationship"], "primitive_under_component")
                self.assertIn("PentaQueue", component["primitives"])
            else:
                self.assertEqual(member["name"], component["name"])
                self.assertEqual(member["registry_relationship"], "component")

        workforce = json.loads(
            (root / "data/penta/systems.extensions.operations-workforce.json").read_text()
        )
        institutional_cost = next(
            system for system in workforce["systems"] if system["machine_key"] == "penta.cost"
        )
        runtime_costs = canonical["penta.costs"]
        self.assertEqual(institutional_cost["canonical_name"], "PentaCost")
        self.assertEqual(runtime_costs["name"], "PentaCosts")
        self.assertNotEqual(institutional_cost["machine_key"], runtime_costs["key"])
        self.assertNotIn(institutional_cost["canonical_name"], runtime_costs["aliases"])
        self.assertIn(
            "penta.cost / PentaCost",
            manifest["cost_family_boundary"]["PentaCost_identity_boundary"],
        )


if __name__ == "__main__":
    unittest.main()
