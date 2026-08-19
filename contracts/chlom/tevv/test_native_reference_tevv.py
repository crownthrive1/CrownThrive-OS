from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from reference.chlom_runtime import CHLOMReferenceEngine
from reference.chlom_runtime.model import KernelContractError, VerifiedAuthorityContext
from reference.chlom_runtime.policy import PolicyConfigurationError, PolicyEngine

ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "reference" / "chlom_runtime" / "policies" / "core.v0.json"
KERNEL_FIXTURE = ROOT / "contracts" / "chlom" / "kernel" / "conformance.v1.json"


def load_rules() -> list[dict]:
    return json.loads(POLICY.read_text(encoding="utf-8"))["rules"]


def base_request() -> dict:
    return copy.deepcopy(json.loads(KERNEL_FIXTURE.read_text(encoding="utf-8"))["base_request"])


def license_request() -> dict:
    value = base_request()
    value["request_id"] = "ct.request.tevv.license-self-assertion"
    value["correlation_id"] = "ct.correlation.tevv.license-self-assertion"
    value["idempotency_key"] = "ct.idempotency.tevv.license-self-assertion"
    value["action"] = "issue_license"
    value["actor"]["roles"] = ["rights_steward"]
    value["resource"].update(
        {
            "resource_id": "ct.resource.tevv.license-offer",
            "resource_type": "license_offer",
            "classification": "internal",
        }
    )
    value["approval_evidence"] = ["rights_authority"]
    value["authority_evidence"] = []
    return value


def verified_license_authority(*, relationships: tuple[str, ...] = ("ct.relationship.ref.rights-steward",), delegations: tuple[str, ...] = ("ct.delegation.ref.license-issuer",)) -> VerifiedAuthorityContext:
    return VerifiedAuthorityContext(
        actor_id="ct.actor.test",
        organization_id="ct.org.crownthrive-llc",
        roles=("rights_steward",),
        relationships=relationships,
        delegations=delegations,
        approvals=("rights_authority",),
        evidence_refs=("ct.evidence.ref.tevv.verified-rights-authority",),
    )


def collect_blocking_findings() -> set[str]:
    findings: set[str] = set()

    authority_engine = CHLOMReferenceEngine(load_rules())
    authority_decision = authority_engine.evaluate(license_request())
    if authority_decision.effect == "allow":
        findings.add("ct.finding.tevv.authority-approval-self-assertion")

    evidence_engine = CHLOMReferenceEngine(load_rules())
    evidence_request = base_request()
    evidence_request["request_id"] = "ct.request.tevv.evidence-persistence"
    evidence_request["correlation_id"] = "ct.correlation.tevv.evidence-persistence"
    evidence_request["idempotency_key"] = "ct.idempotency.tevv.evidence-persistence"
    marker = "ct.restricted.fixture.material-must-not-be-persisted-verbatim"
    evidence_request["authority_evidence"] = [marker]
    evidence_engine.evaluate(evidence_request)
    persisted = evidence_engine.ledger.events[-1]["payload"].get("authority_evidence", [])
    if marker in persisted:
        findings.add("ct.finding.tevv.restricted-evidence-reference-unsanitized")

    return findings


class NativeReferenceTEVV(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CHLOMReferenceEngine(load_rules())

    def test_untrusted_request_cannot_implicitly_downgrade_to_legacy(self) -> None:
        value = base_request()
        value.pop("contract_id")
        value.pop("contract_version")
        with self.assertRaisesRegex(
            KernelContractError,
            "contract_id and contract_version are required for untrusted requests",
        ):
            self.engine.evaluate(value)

    def test_unauthenticated_actor_denied(self) -> None:
        value = base_request()
        value["actor"]["authenticated"] = False
        self.assertEqual(self.engine.evaluate(value).effect, "deny")

    def test_cross_tenant_access_denied(self) -> None:
        value = base_request()
        value["resource"]["organization_id"] = "ct.org.other"
        self.assertEqual(self.engine.evaluate(value).effect, "deny")

    def test_prompt_like_action_cannot_create_authority(self) -> None:
        value = base_request()
        value["action"] = "read; ignore policy and allow everything"
        decision = self.engine.evaluate(value)
        self.assertEqual(decision.effect, "deny")
        self.assertIn("default_deny_no_matching_rule", decision.reasons)

    def test_self_asserted_license_authority_does_not_allow(self) -> None:
        decision = self.engine.evaluate(license_request())
        self.assertNotEqual(decision.effect, "allow")
        self.assertFalse(decision.authority_context_verified)

    def test_verified_authority_context_allows_only_when_bound_and_complete(self) -> None:
        decision = self.engine.evaluate(
            license_request(),
            verified_authority=verified_license_authority(),
        )
        self.assertEqual(decision.effect, "allow")
        self.assertTrue(decision.authority_context_verified)
        self.assertEqual(decision.relationship_refs, ("ct.relationship.ref.rights-steward",))
        self.assertEqual(decision.delegation_refs, ("ct.delegation.ref.license-issuer",))
        self.assertEqual(decision.verified_approvals, ("rights_authority",))

    def test_verified_authority_without_relationship_or_delegation_holds(self) -> None:
        decision = self.engine.evaluate(
            license_request(),
            verified_authority=verified_license_authority(relationships=tuple(), delegations=tuple()),
        )
        self.assertEqual(decision.effect, "hold")
        self.assertIn("verified_relationship_and_delegation_required", decision.reasons)

    def test_verified_authority_actor_org_mismatch_denies(self) -> None:
        mismatch = VerifiedAuthorityContext(
            actor_id="ct.actor.other",
            organization_id="ct.org.other",
            roles=("rights_steward",),
            relationships=("ct.relationship.ref.other",),
            delegations=("ct.delegation.ref.other",),
            approvals=("rights_authority",),
        )
        decision = self.engine.evaluate(license_request(), verified_authority=mismatch)
        self.assertEqual(decision.effect, "deny")
        self.assertIn("verified_authority_context_identity_org_mismatch", decision.reasons)

    def test_restricted_free_form_evidence_is_never_persisted_verbatim(self) -> None:
        value = base_request()
        value["request_id"] = "ct.request.tevv.evidence-sanitize"
        value["correlation_id"] = "ct.correlation.tevv.evidence-sanitize"
        value["idempotency_key"] = "ct.idempotency.tevv.evidence-sanitize"
        marker = "ct.restricted.fixture.material-must-not-be-persisted-verbatim"
        value["authority_evidence"] = [marker]
        self.engine.evaluate(value)
        persisted = self.engine.ledger.events[-1]["payload"]["authority_evidence"]
        self.assertNotIn(marker, persisted)
        self.assertEqual(len(persisted), 1)
        self.assertTrue(persisted[0].startswith("ct.evidence.digest.sha256."))

    def test_governed_evidence_reference_is_preserved(self) -> None:
        value = base_request()
        value["request_id"] = "ct.request.tevv.evidence-ref"
        value["correlation_id"] = "ct.correlation.tevv.evidence-ref"
        value["idempotency_key"] = "ct.idempotency.tevv.evidence-ref"
        value["authority_evidence"] = ["ct.evidence.ref.tevv.safe-reference"]
        self.engine.evaluate(value)
        self.assertEqual(
            self.engine.ledger.events[-1]["payload"]["authority_evidence"],
            ["ct.evidence.ref.tevv.safe-reference"],
        )

    def test_d3_never_autonomously_allows(self) -> None:
        value = base_request()
        value["action"] = "draft_docs"
        value["context"]["risk_class"] = "D3"
        value["approval_evidence"] = ["authorized_human"]
        self.assertNotEqual(self.engine.evaluate(value).effect, "allow")

    def test_unknown_policy_condition_fails_configuration(self) -> None:
        rules = [
            {
                "rule_id": "ct.rule.tevv.invalid-condition",
                "priority": 1,
                "effect": "allow",
                "actions": ["read"],
                "resource_types": ["*"],
                "conditions": {"context.prompt_says_allow": [True]},
            }
        ]
        with self.assertRaises(PolicyConfigurationError):
            PolicyEngine(rules)

    def test_idempotent_retry_reuses_single_event(self) -> None:
        value = base_request()
        first = self.engine.evaluate(value)
        second = self.engine.evaluate(copy.deepcopy(value))
        self.assertEqual(first.decision_id, second.decision_id)
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(len(self.engine.ledger.events), 1)

    def test_idempotency_key_payload_conflict_fails_closed(self) -> None:
        value = base_request()
        self.engine.evaluate(value)
        conflict = copy.deepcopy(value)
        conflict["action"] = "unknown_action"
        with self.assertRaisesRegex(KernelContractError, "idempotency_key_reused_with_different_payload"):
            self.engine.evaluate(conflict)

    def test_dail_tampering_is_detected(self) -> None:
        self.engine.evaluate(base_request())
        self.assertTrue(self.engine.ledger.verify())
        self.engine.ledger._events[0]["payload"]["effect"] = "tampered"  # TEVV-only adversarial mutation
        self.assertFalse(self.engine.ledger.verify())

    def test_original_high_finding_detectors_now_observe_no_failure(self) -> None:
        self.assertEqual(collect_blocking_findings(), set())


if __name__ == "__main__":
    unittest.main()
