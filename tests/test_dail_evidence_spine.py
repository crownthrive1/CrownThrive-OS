"""Focused regression tests for the DAIL v2 OS evidence-spine adapter."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
import json
import unittest
from uuid import NAMESPACE_URL, uuid5

from runtime.dail_evidence_spine import (
    DailConflictError,
    DailError,
    DailIntegrityError,
    DailLedger,
    DailUnavailableError,
    CANONICAL_CHAIN_ID,
    build_event,
    build_external_verification_receipt,
    build_factory_continuation_receipt,
    build_witness_head,
    dail_event_v2_preimage,
    prepare_unavailable_write,
    sha256_json,
    validate_event,
    verify_chain,
    verify_stripe_signature,
)


NOW_EPOCH = 2_000_000_000
NOW_ISO = "2033-05-18T03:33:20Z"
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
VERIFIER_ADMISSION_KEY_REF = "vault:dail:verifier-admission:test-v1"
VERIFIER_ADMISSION_KEY = b"test-only-dail-verifier-admission-key-32-bytes"


def stable_uuid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"https://crownthrive.com/dail-test/{label}"))


def authority(*, decision_class: str = "D2", approval_ref: str | None = "approval:change:1") -> dict:
    return {
        "authority_ref": "chlom:authority:runtime:1",
        "actor_ref": "ct.actor:operator:1",
        "decision_class": decision_class,
        "approval_ref": approval_ref,
        "human_authority": decision_class == "D3",
    }


def transition(*, new_state: str = "CONTROLLED_TEST") -> dict:
    return {
        "subject_type": "runtime_component",
        "subject_id": "ct.runtime.example",
        "previous_state": "IMPLEMENTED",
        "new_state": new_state,
        "change_class": "runtime_transition",
        "risk_class": "D2",
        "reason": "exercise the governed DAIL adapter",
        "affected_record_ids": ["ct.runtime.example", "ct.registry.components"],
        "rollback_ref": "git:revert:example",
    }


def material_request(
    *,
    source_event_id: str = "source-event-1",
    payload_value: int = 1,
    event_type: str = "ct.runtime.lifecycle.changed",
) -> dict:
    return {
        "event_type": event_type,
        "event_class": "material_transition",
        "source_system": "crownthrive-os",
        "source_event_id": source_event_id,
        "trust_domain": "crownthrive:runtime",
        "evidence_class": "E1_INTERNAL_HASHED",
        "correlation_id": "correlation:run:1",
        "causation_id": "request:run:1",
        "authority_basis": authority(),
        "visibility_class": "restricted",
        "payload_ref": f"vault:runtime:{source_event_id}",
        "payload": {"value": payload_value, "state": "CONTROLLED_TEST"},
        "transition": transition(),
        "event_id": stable_uuid(f"event:{source_event_id}"),
        "created_at": NOW_ISO,
    }


def stripe_header(raw: bytes, secret: bytes, timestamp: int = NOW_EPOCH) -> str:
    digest = hmac.new(secret, str(timestamp).encode("ascii") + b"." + raw, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={'0' * 64},v1={digest}"


def verified_stripe_receipt(*, raw: bytes = b'{"id":"evt_123","object":"event"}') -> dict:
    secret = b"whsec_test_old"
    verification = verify_stripe_signature(
        raw,
        stripe_header(raw, secret),
        {"vault:stripe:endpoint:old": secret},
        now=NOW_EPOCH,
    )
    return build_external_verification_receipt(
        verification,
        source_event_id="evt_123",
        producer_trust_domain="provider:stripe:acct_test",
        verifier_id="ct.verifier.stripe-webhook.v2",
        verifier_trust_domain="crownthrive:edge:dail-ingress",
        admission_key_version_ref=VERIFIER_ADMISSION_KEY_REF,
        admission_key=VERIFIER_ADMISSION_KEY,
        receipt_id=stable_uuid("verification:stripe:evt_123"),
        verified_at=NOW_ISO,
    )


def append_three_events() -> DailLedger:
    ledger = DailLedger(CANONICAL_CHAIN_ID)
    for number in range(1, 4):
        request = material_request(
            source_event_id=f"source-event-{number}",
            payload_value=number,
        )
        request["correlation_id"] = "correlation:chain:1"
        request["causation_id"] = None if number == 1 else f"dail:source-event-{number - 1}"
        ledger.append(idempotency_key=f"idempotency-{number}", **request)
    return ledger


class DailEnvelopeTests(unittest.TestCase):
    def test_full_envelope_is_hashed_and_payload_mutation_is_detected(self) -> None:
        event = build_event(
            chain_id=CANONICAL_CHAIN_ID,
            sequence_id=1,
            previous_event_hash=None,
            idempotency_key="idempotency-1",
            **material_request(),
        )
        expected_fields = {
            "chain_id",
            "sequence_id",
            "source_system",
            "source_event_id",
            "trust_domain",
            "evidence_class",
            "correlation_id",
            "causation_id",
            "authority_basis",
            "visibility_class",
            "payload_sha256",
            "payload_ref",
            "previous_event_hash",
            "verification_receipt_id",
            "correction_of_event_id",
            "supersedes_event_id",
            "event_hash",
        }
        self.assertTrue(expected_fields.issubset(event))
        validate_event(event)
        mutated = deepcopy(event)
        mutated["payload"]["content"]["value"] = 999
        with self.assertRaises(DailIntegrityError):
            validate_event(mutated)

    def test_material_transition_contract_and_classification_cannot_be_bypassed(self) -> None:
        request = material_request()
        request.pop("transition")
        with self.assertRaisesRegex(DailError, "transition object"):
            build_event(
                chain_id=CANONICAL_CHAIN_ID,
                sequence_id=1,
                previous_event_hash=None,
                idempotency_key="idempotency-1",
                **request,
            )

        event = build_event(
            chain_id=CANONICAL_CHAIN_ID,
            sequence_id=1,
            previous_event_hash=None,
            idempotency_key="idempotency-1",
            **material_request(),
        )
        event["payload"]["_dail_contract"]["classification"]["consequential"] = False
        event["payload_sha256"] = sha256_json(event["payload"])
        event["event_hash"] = sha256_json(dail_event_v2_preimage(event))
        with self.assertRaisesRegex(DailIntegrityError, "classification"):
            validate_event(event)

    def test_consequential_transition_requires_approval_and_d3_human_authority(self) -> None:
        request = material_request()
        request["authority_basis"] = authority(approval_ref=None)
        with self.assertRaisesRegex(DailError, "approval_ref"):
            build_event(
                chain_id=CANONICAL_CHAIN_ID,
                sequence_id=1,
                previous_event_hash=None,
                idempotency_key="idempotency-1",
                **request,
            )

        request = material_request()
        request["authority_basis"] = {
            **authority(decision_class="D3", approval_ref="human:approval:1"),
            "human_authority": False,
        }
        request["transition"] = {**transition(), "risk_class": "D3"}
        with self.assertRaisesRegex(DailError, "human-reserved"):
            build_event(
                chain_id=CANONICAL_CHAIN_ID,
                sequence_id=1,
                previous_event_hash=None,
                idempotency_key="idempotency-1",
                **request,
            )

    def test_external_event_binds_verified_receipt_but_not_the_secret(self) -> None:
        receipt = verified_stripe_receipt()
        event = build_event(
            chain_id=CANONICAL_CHAIN_ID,
            sequence_id=1,
            event_type="stripe.event.received",
            event_class="external_evidence",
            source_system="stripe",
            source_event_id="evt_123",
            trust_domain="provider:stripe:acct_test",
            evidence_class="E4_EXTERNAL_SYMMETRIC_VERIFIED",
            idempotency_key="stripe:evt_123",
            correlation_id="correlation:stripe:evt_123",
            causation_id=None,
            authority_basis=authority(decision_class="D1", approval_ref=None),
            actor_ref="ct.actor:operator:1",
            agent_id="ct.verifier.stripe-webhook.v2",
            entity_type="stripe_object:event",
            entity_id="evt_123",
            visibility_class="restricted",
            payload_ref="vault:stripe:event:evt_123",
            payload_sha256=receipt["verification"]["raw_body_sha256"],
            previous_event_hash=None,
            verification_receipts=[receipt],
            verifier_admission_keys={VERIFIER_ADMISSION_KEY_REF: VERIFIER_ADMISSION_KEY},
            event_id=stable_uuid("event:stripe:evt_123"),
            created_at=NOW_ISO,
        )
        self.assertEqual(event["verification_receipt_id"], receipt["receipt_id"])
        serialized = json.dumps({"receipt": receipt, "event": event})
        self.assertNotIn("whsec_test_old", serialized)

    def test_generic_admission_cannot_promote_reserved_evidence_or_anchor_state(self) -> None:
        for evidence_class in (
            "E2_SEPARATE_WORKLOAD_VERIFIED",
            "E5_EXTERNAL_ASYMMETRIC_ATTESTED",
            "E6_INDEPENDENTLY_ANCHORED",
        ):
            with self.subTest(evidence_class=evidence_class):
                with self.assertRaisesRegex(DailError, "dedicated authenticated admission"):
                    build_event(
                        chain_id=CANONICAL_CHAIN_ID,
                        sequence_id=1,
                        previous_event_hash=None,
                        idempotency_key=f"idempotency:{evidence_class}",
                        **{
                            **material_request(),
                            "evidence_class": evidence_class,
                        },
                    )

        with self.assertRaisesRegex(DailError, "cannot assert an anchor state"):
            build_event(
                chain_id=CANONICAL_CHAIN_ID,
                sequence_id=1,
                previous_event_hash=None,
                idempotency_key="idempotency:fake-anchor",
                **{
                    **material_request(),
                    "chain_anchor_state": "anchored_production",
                },
            )

    def test_e4_receipt_cannot_be_rebound_to_another_source_event(self) -> None:
        receipt = verified_stripe_receipt()
        with self.assertRaisesRegex(DailIntegrityError, "provenance"):
            build_event(
                chain_id=CANONICAL_CHAIN_ID,
                sequence_id=1,
                previous_event_hash=None,
                event_type="stripe.event.received",
                event_class="external_evidence",
                source_system="stripe",
                source_event_id="evt_other",
                trust_domain="provider:stripe:acct_test",
                evidence_class="E4_EXTERNAL_SYMMETRIC_VERIFIED",
                idempotency_key="stripe:evt_other",
                correlation_id="correlation:stripe:evt_other",
                causation_id=None,
                authority_basis=authority(decision_class="D1", approval_ref=None),
                actor_ref="ct.actor:operator:1",
                entity_type="stripe_object:event",
                entity_id="evt_other",
                visibility_class="restricted",
                payload_ref="vault:stripe:event:evt_other",
                payload_sha256=receipt["verification"]["raw_body_sha256"],
                verification_receipts=[receipt],
                verifier_admission_keys={
                    VERIFIER_ADMISSION_KEY_REF: VERIFIER_ADMISSION_KEY
                },
                created_at=NOW_ISO,
            )

    def test_unkeyed_receipt_digest_cannot_forge_verifier_admission(self) -> None:
        receipt = verified_stripe_receipt()
        forged = deepcopy(receipt)
        forged["admission"]["mac_sha256"] = "0" * 64
        unsigned = deepcopy(forged)
        unsigned.pop("receipt_sha256")
        forged["receipt_sha256"] = sha256_json(unsigned)

        request = {
            "chain_id": CANONICAL_CHAIN_ID,
            "sequence_id": 1,
            "previous_event_hash": None,
            "event_type": "stripe.event.received",
            "event_class": "external_evidence",
            "source_system": "stripe",
            "source_event_id": "evt_123",
            "trust_domain": "provider:stripe:acct_test",
            "evidence_class": "E4_EXTERNAL_SYMMETRIC_VERIFIED",
            "idempotency_key": "stripe:evt_123:forged",
            "correlation_id": "correlation:stripe:evt_123",
            "causation_id": None,
            "authority_basis": authority(decision_class="D1", approval_ref=None),
            "actor_ref": "ct.actor:operator:1",
            "entity_type": "stripe_object:event",
            "entity_id": "evt_123",
            "visibility_class": "restricted",
            "payload_ref": "vault:stripe:event:evt_123",
            "payload_sha256": receipt["verification"]["raw_body_sha256"],
            "verification_receipts": [forged],
            "verifier_admission_keys": {
                VERIFIER_ADMISSION_KEY_REF: VERIFIER_ADMISSION_KEY
            },
            "created_at": NOW_ISO,
        }
        with self.assertRaisesRegex(DailIntegrityError, "admission MAC"):
            build_event(**request)
        request["verification_receipts"] = [receipt]
        request["verifier_admission_keys"] = None
        with self.assertRaisesRegex(DailError, "admission keys"):
            build_event(**request)

    def test_sql_bound_identifiers_require_canonical_uuids(self) -> None:
        with self.assertRaisesRegex(DailError, "event_id must be a UUID"):
            build_event(
                chain_id=CANONICAL_CHAIN_ID,
                sequence_id=1,
                previous_event_hash=None,
                idempotency_key="idempotency:bad-uuid",
                **{
                    **material_request(),
                    "event_id": "not-a-uuid",
                },
            )


class StripeVerificationTests(unittest.TestCase):
    def test_exact_raw_bytes_multiple_v1_and_secret_rotation(self) -> None:
        raw = b'{\n  "id": "evt_123", "object": "event"\n}'
        old_secret = b"whsec_rotation_old"
        result = verify_stripe_signature(
            raw,
            stripe_header(raw, old_secret),
            {
                "vault:stripe:endpoint:new": b"whsec_rotation_new",
                "vault:stripe:endpoint:old": old_secret,
            },
            now=NOW_EPOCH,
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["outcome"], "verified")
        self.assertEqual(result["matched_secret_version_refs"], ["vault:stripe:endpoint:old"])
        self.assertEqual(result["candidate_signature_count"], 2)
        serialized = json.dumps(result)
        self.assertNotIn("whsec_rotation_old", serialized)
        self.assertNotIn("whsec_rotation_new", serialized)

    def test_mutated_body_wrong_signature_and_stale_timestamp_are_rejected(self) -> None:
        raw = b'{"id":"evt_123"}'
        secret = b"whsec_exact_bytes"
        header = stripe_header(raw, secret)
        mutated = verify_stripe_signature(
            raw + b"\n", header, {"vault:stripe:current": secret}, now=NOW_EPOCH
        )
        self.assertFalse(mutated["verified"])
        self.assertEqual(mutated["reason"], "signature_mismatch")

        wrong = verify_stripe_signature(
            raw, header, {"vault:stripe:wrong": b"wrong-secret"}, now=NOW_EPOCH
        )
        self.assertFalse(wrong["verified"])
        self.assertEqual(wrong["reason"], "signature_mismatch")

        stale = verify_stripe_signature(
            raw,
            stripe_header(raw, secret, NOW_EPOCH - 301),
            {"vault:stripe:current": secret},
            now=NOW_EPOCH,
        )
        self.assertFalse(stale["verified"])
        self.assertEqual(stale["reason"], "timestamp_outside_tolerance")

        with self.assertRaisesRegex(DailError, "never secret material"):
            verify_stripe_signature(
                raw,
                header,
                {"whsec_accidentally_used_as_a_ref": secret},
                now=NOW_EPOCH,
            )

    def test_verification_receipt_requires_producer_verifier_trust_separation(self) -> None:
        raw = b'{"id":"evt_123"}'
        secret = b"whsec_trust"
        verification = verify_stripe_signature(
            raw,
            stripe_header(raw, secret),
            {"vault:stripe:current": secret},
            now=NOW_EPOCH,
        )
        with self.assertRaisesRegex(DailError, "trust domains"):
            build_external_verification_receipt(
                verification,
                source_event_id="evt_123",
                producer_trust_domain="same-domain",
                verifier_id="verifier:1",
                verifier_trust_domain="same-domain",
                admission_key_version_ref=VERIFIER_ADMISSION_KEY_REF,
                admission_key=VERIFIER_ADMISSION_KEY,
                verified_at=NOW_ISO,
            )
        receipt = build_external_verification_receipt(
            verification,
            source_event_id="evt_123",
            producer_trust_domain="provider:stripe",
            verifier_id="ct.verifier.stripe",
            verifier_trust_domain="crownthrive:dail-ingress",
            admission_key_version_ref=VERIFIER_ADMISSION_KEY_REF,
            admission_key=VERIFIER_ADMISSION_KEY,
            verified_at=NOW_ISO,
        )
        self.assertEqual(receipt["evidence_class"], "E4_EXTERNAL_SYMMETRIC_VERIFIED")
        self.assertTrue(receipt["independence"]["trust_domain_labels_distinct"])
        self.assertFalse(
            receipt["independence"]["authenticated_workload_identity_verified_by_this_builder"]
        )
        self.assertFalse(receipt["independence"]["public_key_non_repudiation"])


class DailLedgerTests(unittest.TestCase):
    def test_idempotent_replay_and_conflicting_key_fail_closed(self) -> None:
        ledger = DailLedger(CANONICAL_CHAIN_ID)
        request = material_request()
        first = ledger.append(idempotency_key="idem-1", **request)
        replay = ledger.append(idempotency_key="idem-1", **request)
        self.assertFalse(first.idempotent_replay)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.replay_basis, "idempotency_key")
        self.assertEqual(first.event["event_hash"], replay.event["event_hash"])
        with self.assertRaisesRegex(DailConflictError, "idempotency"):
            ledger.append(
                idempotency_key="idem-1",
                **material_request(source_event_id="source-event-different", payload_value=2),
            )

    def test_duplicate_source_event_requires_the_original_idempotency_key(self) -> None:
        ledger = DailLedger(CANONICAL_CHAIN_ID)
        ledger.append(idempotency_key="idem-1", **material_request())
        with self.assertRaisesRegex(DailConflictError, "original idempotency key"):
            ledger.append(idempotency_key="idem-2", **material_request())
        with self.assertRaisesRegex(DailConflictError, "source event"):
            ledger.append(
                idempotency_key="idem-3",
                **material_request(payload_value=999),
            )

    def test_chain_detects_tamper_and_reorder(self) -> None:
        ledger = append_three_events()
        ledger.verify()
        events = ledger.events
        tampered = deepcopy(events)
        tampered[1]["actor_ref"] = "ct.actor:attacker"
        with self.assertRaises(DailIntegrityError):
            verify_chain(tampered)
        with self.assertRaisesRegex(DailIntegrityError, "previous hash|sequence"):
            verify_chain([events[1], events[0], events[2]])

    def test_external_witness_detects_tail_truncation(self) -> None:
        ledger = append_three_events()
        witness = build_witness_head(
            ledger.events,
            witness_id="external:witness:1",
            witness_trust_domain="third-party:transparency-log",
            observed_at=NOW_ISO,
        )
        truncated = ledger.events[:2]
        self.assertTrue(verify_chain(truncated)["ok"])
        with self.assertRaisesRegex(DailIntegrityError, "truncated"):
            verify_chain(truncated, witness_head=witness)
        self.assertEqual(ledger.verify(witness_head=witness)["witness_state"], "matched")


class WriteGateAndFactoryTests(unittest.TestCase):
    def test_dail_unavailability_fails_closed_except_explicit_low_risk_telemetry(self) -> None:
        with self.assertRaisesRegex(DailUnavailableError, "material or consequential"):
            prepare_unavailable_write(event_class="material_transition")
        with self.assertRaisesRegex(DailUnavailableError, "explicitly authorized"):
            prepare_unavailable_write(event_class="low_risk_telemetry")
        queued = prepare_unavailable_write(
            event_class="low_risk_telemetry",
            allow_unsealed_telemetry=True,
            source_system="penta-observability",
            source_event_id="metric:1",
            trust_domain="crownthrive:telemetry",
            idempotency_key="telemetry:metric:1",
            correlation_id="correlation:metric:1",
            causation_id=None,
            payload_ref="telemetry-buffer:metric:1",
            payload={"metric": "queue_depth", "value": 3},
            created_at=NOW_ISO,
        )
        self.assertEqual(queued["seal_state"], "queued_unsealed")
        self.assertIsNone(queued["dail_event_hash"])
        self.assertFalse(queued["counts_as_dail_evidence"])
        self.assertTrue(queued["requires_dail_append"])

    def test_factory_continuation_binds_exact_inputs_outputs_and_assurance(self) -> None:
        receipt = build_factory_continuation_receipt(
            factory_id="ct.factory.software",
            run_id="factory-run-1",
            stage="verify",
            source_digests={"git:crownthrive-support@head": SHA_A},
            artifact_digests={"artifact:dail-adapter.py": SHA_B},
            test_state={
                "status": "PASS",
                "receipt_ref": "tests:test_dail_evidence_spine",
                "receipt_sha256": SHA_C,
                "verifier_id": "ct.verifier.tests",
            },
            security_state={
                "status": "PASS",
                "receipt_ref": "security:review:1",
                "receipt_sha256": SHA_B,
                "verifier_id": "ct.verifier.security",
            },
            predecessor_checkpoint={
                "checkpoint_id": "dail-head:2742",
                "chain_id": CANONICAL_CHAIN_ID,
                "sequence": 2742,
                "event_hash": SHA_A,
            },
            next_action={
                "action": "submit candidate for independent review",
                "owner_ref": "ct.agent.execution-builder",
                "authority_class": "D2",
                "requires_human_approval": False,
            },
            producer_id="ct.agent.execution-builder",
            receipt_id="factory-continuation:1",
            created_at=NOW_ISO,
        )
        self.assertEqual(receipt["continuation_state"], "READY_FOR_GOVERNED_CONTINUATION")
        self.assertEqual(receipt["source_digests"]["git:crownthrive-support@head"], SHA_A)
        self.assertEqual(receipt["artifact_digests"]["artifact:dail-adapter.py"], SHA_B)
        self.assertEqual(len(receipt["content_sha256"]), 64)
        self.assertFalse(receipt["self_certification"])
        self.assertFalse(receipt["production_authority_granted"])

        held = build_factory_continuation_receipt(
            factory_id="ct.factory.software",
            run_id="factory-run-2",
            stage="verify",
            source_digests={"git:crownthrive-support@head": SHA_A},
            artifact_digests={"artifact:dail-adapter.py": SHA_B},
            test_state={
                "status": "PASS",
                "receipt_ref": "tests:run:2",
                "receipt_sha256": SHA_C,
                "verifier_id": "ct.verifier.tests",
            },
            security_state={
                "status": "HOLD",
                "receipt_ref": "security:review:2",
                "receipt_sha256": SHA_B,
                "verifier_id": "ct.verifier.security",
            },
            predecessor_checkpoint={
                "checkpoint_id": "dail-head:2742",
                "chain_id": CANONICAL_CHAIN_ID,
                "sequence": 2742,
                "event_hash": SHA_A,
            },
            next_action={
                "action": "resolve security hold",
                "owner_ref": "ct.role.security",
                "authority_class": "D2",
                "requires_human_approval": False,
            },
            producer_id="ct.agent.execution-builder",
            created_at=NOW_ISO,
        )
        self.assertEqual(held["continuation_state"], "HOLD")

    def test_factory_rejects_non_exact_digest_and_unguarded_d3_next_action(self) -> None:
        common = {
            "factory_id": "ct.factory.software",
            "run_id": "factory-run-3",
            "stage": "verify",
            "source_digests": {"git:head": SHA_A},
            "artifact_digests": {"artifact:module": SHA_B},
            "test_state": {
                "status": "PASS",
                "receipt_ref": "tests:3",
                "receipt_sha256": SHA_C,
                "verifier_id": "ct.verifier.tests",
            },
            "security_state": {
                "status": "PASS",
                "receipt_ref": "security:3",
                "receipt_sha256": SHA_B,
                "verifier_id": "ct.verifier.security",
            },
            "predecessor_checkpoint": {
                "checkpoint_id": "head:1",
                "chain_id": CANONICAL_CHAIN_ID,
                "sequence": 1,
                "event_hash": SHA_A,
            },
            "next_action": {
                "action": "perform reserved action",
                "owner_ref": "ct.role.founder",
                "authority_class": "D3",
                "requires_human_approval": False,
            },
            "producer_id": "ct.agent.execution-builder",
            "created_at": NOW_ISO,
        }
        with self.assertRaisesRegex(DailError, "human-reserved"):
            build_factory_continuation_receipt(**common)
        common["next_action"] = {
            **common["next_action"],
            "authority_class": "D2",
        }
        common["source_digests"] = {"git:head": "not-a-digest"}
        with self.assertRaisesRegex(DailError, "SHA-256"):
            build_factory_continuation_receipt(**common)
        common["source_digests"] = {"git:head": SHA_A}
        common["test_state"] = {
            **common["test_state"],
            "verifier_id": "ct.agent.execution-builder",
        }
        with self.assertRaisesRegex(DailError, "cannot independently verify"):
            build_factory_continuation_receipt(**common)


if __name__ == "__main__":
    unittest.main()
