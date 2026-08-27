#!/usr/bin/env python3
"""Adversarial and concurrency tests for the collision v2 contract."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collision_rtc_v2 import (  # noqa: E402
    ContractError,
    Intent,
    LeaseBook,
    RepairPlan,
    RepairState,
    build_rtc_event,
    classify_collision,
    disposition_for,
    normalize_path,
)


ZERO40 = "0" * 40
ONE40 = "1" * 40
TWO40 = "2" * 40
ZERO64 = "0" * 64
ONE64 = "1" * 64


def make_intent(
    claims: list[dict[str, str]],
    *,
    target_id: str = "1",
    authority: str = "D1",
    base_sha: str = ZERO40,
    head_sha: str = ONE40,
    intent_id: str | None = None,
) -> Intent:
    return Intent.from_mapping(
        {
            "schema_version": "2.0.0",
            "intent_id": intent_id or str(uuid.uuid4()),
            "repository": "crownthrive1/CrownThrive-OS",
            "target": {"kind": "pull_request", "id": target_id},
            "agent": {
                "agent_id": "ct.subagent.collision.preflight-sentinel",
                "instance_id": str(uuid.uuid4()),
            },
            "versions": {
                "base_sha": base_sha,
                "head_sha": head_sha,
                "executable_sha256": ZERO64,
                "config_sha256": ZERO64,
                "policy_sha256": ONE64,
            },
            "authority_class": authority,
            "correlation_id": str(uuid.uuid4()),
            "claims": claims,
        }
    )


class ContractTests(unittest.TestCase):
    def test_rejects_traversal_absolute_and_backslash_paths(self) -> None:
        for candidate in ("../secret", "/root/secret", "a\\b", "./../x", ""):
            with self.subTest(candidate=candidate), self.assertRaises(ContractError):
                normalize_path(candidate)

    def test_normalization_deduplicates_identical_claims(self) -> None:
        intent = make_intent(
            [
                {"domain_type": "path", "key": "docs/../docs/a.mdx", "access": "mutate"},
                {"domain_type": "path", "key": "docs/a.mdx", "access": "mutate"},
            ]
        )
        self.assertEqual(len(intent.claims), 1)

    def test_prose_marker_does_not_invent_runtime_collision(self) -> None:
        left = make_intent(
            [{"domain_type": "path", "key": "guides/vault-overview.mdx", "access": "mutate"}],
            target_id="1",
        )
        right = make_intent(
            [{"domain_type": "path", "key": "guides/credential-safety.mdx", "access": "mutate"}],
            target_id="2",
        )
        collision = classify_collision(left, right)
        self.assertLessEqual(collision.severity, 1)
        self.assertNotIn("runtime", collision.collision_class.lower())

    def test_exact_path_mutation_holds(self) -> None:
        claim = [{"domain_type": "path", "key": "docs.json", "access": "mutate"}]
        collision = classify_collision(make_intent(claim, target_id="1"), make_intent(claim, target_id="2"))
        self.assertEqual(collision.severity, 2)
        self.assertEqual(disposition_for([collision])["disposition"], "HOLD")

    def test_byte_identical_direct_stack_overlap_is_awareness(self) -> None:
        claim = [
            {
                "domain_type": "path",
                "key": "standards/shared.mdx",
                "access": "mutate",
                "value_digest": ONE64,
            }
        ]
        upstream = make_intent(claim, target_id="1", base_sha=ZERO40, head_sha=ONE40)
        downstream = make_intent(claim, target_id="2", base_sha=ONE40, head_sha=TWO40)
        collision = classify_collision(upstream, downstream)
        self.assertEqual(collision.severity, 1)
        self.assertIn("byte_identical_inherited_path_overlap", collision.reasons)

    def test_observe_observe_is_clear(self) -> None:
        claim = [{"domain_type": "runtime_resource", "key": "hourly-cycle", "access": "observe"}]
        collision = classify_collision(make_intent(claim, target_id="1"), make_intent(claim, target_id="2"))
        self.assertEqual(collision.severity, 0)

    def test_structured_identity_collision_is_semantic(self) -> None:
        claim = [{"domain_type": "stable_id", "key": "ct.agent.same", "access": "create"}]
        left = make_intent(claim, target_id="1")
        right = make_intent(claim, target_id="2")
        collision = classify_collision(left, right)
        self.assertEqual(collision.severity, 3)
        self.assertEqual(collision.fingerprint, classify_collision(right, left).fingerprint)

    def test_runtime_collision_cannot_be_downgraded_by_stack(self) -> None:
        claim = [{"domain_type": "runtime_resource", "key": "css-hourly", "access": "mutate"}]
        collision = classify_collision(make_intent(claim, target_id="stack-a"), make_intent(claim, target_id="stack-b"))
        self.assertEqual(collision.severity, 4)
        self.assertEqual(disposition_for([collision])["disposition"], "HOLD")

    def test_d3_overlap_always_requires_human_review(self) -> None:
        claim = [{"domain_type": "path", "key": "index.mdx", "access": "mutate"}]
        collision = classify_collision(
            make_intent(claim, target_id="1", authority="D3"), make_intent(claim, target_id="2")
        )
        self.assertEqual(collision.severity, 5)
        self.assertEqual(disposition_for([collision])["disposition"], "HUMAN_REVIEW_REQUIRED")

    def test_source_generation_conflict_is_explicit(self) -> None:
        left = make_intent(
            [
                {
                    "domain_type": "source_generation",
                    "key": "institutional-compendium",
                    "access": "mutate",
                    "value_digest": ZERO64,
                }
            ],
            target_id="v1",
        )
        right = make_intent(
            [
                {
                    "domain_type": "source_generation",
                    "key": "institutional-compendium",
                    "access": "mutate",
                    "value_digest": ONE64,
                }
            ],
            target_id="v2",
        )
        collision = classify_collision(left, right)
        self.assertEqual(collision.severity, 3)
        self.assertIn("source_generation_conflicting_value", collision.reasons)

    def test_fingerprint_is_order_independent(self) -> None:
        claims = [
            {"domain_type": "path", "key": "b.mdx", "access": "mutate"},
            {"domain_type": "path", "key": "a.mdx", "access": "mutate"},
        ]
        shared_id = str(uuid.uuid4())
        first = make_intent(claims, intent_id=shared_id)
        raw = first.as_dict()
        raw["claims"] = list(reversed(raw["claims"]))
        second = Intent.from_mapping(raw)
        self.assertEqual(first.fingerprint, second.fingerprint)


class RtcTests(unittest.TestCase):
    def setUp(self) -> None:
        self.intent = make_intent(
            [{"domain_type": "path", "key": "docs.json", "access": "mutate"}]
        )

    def test_event_contains_version_and_idempotency_bindings(self) -> None:
        observed = datetime(2026, 8, 23, 12, tzinfo=timezone.utc)
        event = build_rtc_event(
            "collision.intent.observed",
            self.intent,
            sequence=1,
            observed_at=observed,
            payload={"state": "HELD"},
        )
        self.assertEqual(event["schema_version"], "2.0.0")
        self.assertEqual(event["versions"]["head_sha"], self.intent.head_sha)
        self.assertEqual(len(event["idempotency_key"]), 64)
        self.assertEqual(len(event["event_hash"]), 64)
        self.assertEqual(event["visibility"], "restricted")

    def test_event_idempotency_key_is_replay_stable(self) -> None:
        observed = datetime(2026, 8, 23, 12, tzinfo=timezone.utc)
        first = build_rtc_event(
            "collision.intent.observed", self.intent, sequence=4, observed_at=observed, payload={"x": 1}
        )
        second = build_rtc_event(
            "collision.intent.observed", self.intent, sequence=4, observed_at=observed, payload={"x": 1}
        )
        self.assertNotEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])


class LeaseAndRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.intent = make_intent(
            [{"domain_type": "runtime_resource", "key": "css-hourly", "access": "mutate"}]
        )
        self.owner = str(uuid.uuid4())
        self.now = datetime.now(timezone.utc)

    def test_single_owner_and_monotonic_fence(self) -> None:
        book = LeaseBook()
        first = book.acquire(
            domain_key="runtime_resource:css-hourly",
            intent=self.intent,
            expected_main_sha=TWO40,
            owner_agent_id=self.intent.agent_id,
            owner_instance_id=self.owner,
            now=self.now,
        )
        with self.assertRaisesRegex(ContractError, "already_leased"):
            book.acquire(
                domain_key=first.domain_key,
                intent=self.intent,
                expected_main_sha=TWO40,
                owner_agent_id=self.intent.agent_id,
                owner_instance_id=self.owner,
                now=self.now,
            )
        book.release(first, now=self.now + timedelta(seconds=1))
        second = book.acquire(
            domain_key=first.domain_key,
            intent=self.intent,
            expected_main_sha=TWO40,
            owner_agent_id=self.intent.agent_id,
            owner_instance_id=self.owner,
            now=self.now + timedelta(seconds=2),
        )
        self.assertGreater(second.fence_token, first.fence_token)

    def test_concurrent_acquire_through_serialization_gate_has_one_winner(self) -> None:
        book = LeaseBook()
        barrier = threading.Barrier(8)
        outcomes: list[str] = []
        outcome_lock = threading.Lock()
        # Production lease acquisition is serialized by the transaction-scoped
        # advisory lock described by LeaseBook's contract. Mirror that boundary
        # here rather than requiring the provider-neutral in-memory model itself
        # to be a cross-thread synchronization primitive.
        serialization_gate = threading.Lock()

        def contender() -> None:
            barrier.wait()
            with serialization_gate:
                try:
                    book.acquire(
                        domain_key="runtime_resource:css-hourly",
                        intent=self.intent,
                        expected_main_sha=TWO40,
                        owner_agent_id=self.intent.agent_id,
                        owner_instance_id=str(uuid.uuid4()),
                        now=self.now,
                    )
                    outcome = "won"
                except ContractError:
                    outcome = "held"
            with outcome_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=contender) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(outcomes.count("won"), 1)
        self.assertEqual(outcomes.count("held"), 7)

    def test_repair_rejects_stale_main_and_fence(self) -> None:
        other = make_intent(self.intent.as_dict()["claims"], target_id="2")
        collision = classify_collision(self.intent, other)
        plan = RepairPlan.compile(collision, self.intent, current_main_sha=TWO40)
        plan = plan.transition(
            RepairState.HELD, current_main_sha=TWO40, current_head_sha=self.intent.head_sha
        )
        plan = plan.transition(
            RepairState.PLANNED, current_main_sha=TWO40, current_head_sha=self.intent.head_sha
        )
        with self.assertRaisesRegex(ContractError, "stale_version"):
            plan.transition(RepairState.LEASED, current_main_sha=ZERO40, current_head_sha=self.intent.head_sha)

        book = LeaseBook()
        lease = book.acquire(
            domain_key=collision.domains[0],
            intent=self.intent,
            expected_main_sha=TWO40,
            owner_agent_id=self.intent.agent_id,
            owner_instance_id=self.owner,
            now=self.now,
        )
        leased = plan.transition(
            RepairState.LEASED,
            current_main_sha=TWO40,
            current_head_sha=self.intent.head_sha,
            lease=lease,
        )
        wrong_fence = replace(lease, fence_token=lease.fence_token + 1)
        with self.assertRaisesRegex(ContractError, "fence_token_mismatch"):
            leased.transition(
                RepairState.APPLYING,
                current_main_sha=TWO40,
                current_head_sha=self.intent.head_sha,
                lease=wrong_fence,
            )

    def test_prohibited_repairs_fail_closed(self) -> None:
        other = make_intent(self.intent.as_dict()["claims"], target_id="2")
        collision = classify_collision(self.intent, other)
        for action in ("merge", "force_push", "provider_write", "rights_determination"):
            with self.subTest(action=action), self.assertRaises(ContractError):
                RepairPlan.compile(collision, self.intent, current_main_sha=TWO40, action_kind=action)

    def test_retry_dead_letters_at_bound(self) -> None:
        other = make_intent(self.intent.as_dict()["claims"], target_id="2")
        collision = classify_collision(self.intent, other)
        plan = RepairPlan.compile(collision, self.intent, current_main_sha=TWO40)
        plan = replace(plan, state=RepairState.ROLLED_BACK)
        plan = plan.retry_or_dead_letter(maximum_retries=3)
        self.assertEqual(plan.state, RepairState.PLANNED)
        plan = replace(plan, state=RepairState.ROLLED_BACK).retry_or_dead_letter(maximum_retries=3)
        self.assertEqual(plan.state, RepairState.PLANNED)
        plan = replace(plan, state=RepairState.ROLLED_BACK).retry_or_dead_letter(maximum_retries=3)
        self.assertEqual(plan.state, RepairState.DEAD_LETTER)


if __name__ == "__main__":
    unittest.main(verbosity=2)
