from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reference.chlom_runtime import CHLOMReferenceEngine
from reference.chlom_runtime.model import (
    KernelContractError,
    VerifiedAuthorityContext,
)

POLICY = ROOT / "reference" / "chlom_runtime" / "policies" / "core.v0.json"
FIXTURE = Path(__file__).with_name("conformance.v1.json")


def _set_path(value: dict, dotted: str, replacement) -> None:
    current = value
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = replacement


def _remove_path(value: dict, dotted: str) -> None:
    current = value
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = current[part]
    current.pop(parts[-1], None)


class KernelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.engine = CHLOMReferenceEngine(self.bundle["rules"])

    def materialize(self, case: dict) -> dict:
        request = copy.deepcopy(self.fixture["base_request"])
        for dotted in case.get("remove", []):
            _remove_path(request, dotted)
        for dotted, replacement in case.get("set", {}).items():
            _set_path(request, dotted, replacement)
        return request

    def test_conformance_cases(self):
        for case in self.fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                self.engine = CHLOMReferenceEngine(self.bundle["rules"])
                request = self.materialize(case)
                mode = case.get("mode", "single")
                expected_error = case.get("expected_error")

                if mode == "retry_same":
                    first = self.engine.evaluate(copy.deepcopy(request))
                    second = self.engine.evaluate(copy.deepcopy(request))
                    self.assertEqual(first.effect, case["expected_effect"])
                    self.assertEqual(first.decision_id, second.decision_id)
                    self.assertEqual(first.event_id, second.event_id)
                    self.assertEqual(
                        len(self.engine.ledger.events), case["expected_ledger_events"]
                    )
                    continue

                if mode == "reuse_key_with_patch":
                    self.engine.evaluate(copy.deepcopy(request))
                    conflicting = copy.deepcopy(request)
                    for dotted, replacement in case["conflicting_set"].items():
                        _set_path(conflicting, dotted, replacement)
                    with self.assertRaisesRegex(KernelContractError, expected_error):
                        self.engine.evaluate(conflicting)
                    continue

                if expected_error:
                    with self.assertRaisesRegex(KernelContractError, expected_error):
                        self.engine.evaluate(request)
                    continue

                decision = self.engine.evaluate(request)
                self.assertEqual(decision.effect, case["expected_effect"])
                if "expected_reason" in case:
                    self.assertIn(case["expected_reason"], decision.reasons)
                self.assertEqual(
                    decision.contract_id, "ct.contract.chlom.kernel.decision.v1"
                )
                self.assertEqual(
                    decision.request_contract_id, "ct.contract.chlom.kernel.request.v1"
                )
                self.assertEqual(decision.prototype_state, "phase_2_99_semantic_oracle")
                self.assertTrue(self.engine.ledger.verify())

    def test_self_asserted_roles_and_approval_labels_do_not_create_authority(self):
        request = copy.deepcopy(self.fixture["base_request"])
        request.update(
            {
                "request_id": "ct.request.kernel.authority-self-assertion",
                "correlation_id": "ct.correlation.kernel.authority-self-assertion",
                "idempotency_key": "ct.idempotency.kernel.authority-self-assertion",
                "action": "issue_license",
            }
        )
        request["actor"]["roles"] = ["rights_steward"]
        request["resource"].update(
            {
                "resource_id": "ct.resource.kernel.license-offer",
                "resource_type": "license_offer",
                "classification": "internal",
            }
        )
        request["approval_evidence"] = ["rights_authority"]
        decision = self.engine.evaluate(request)
        self.assertNotEqual(decision.effect, "allow")
        self.assertFalse(decision.authority_context_verified)

    def test_verified_authority_requires_identity_org_relationship_delegation_and_approval(self):
        request = copy.deepcopy(self.fixture["base_request"])
        request.update(
            {
                "request_id": "ct.request.kernel.verified-authority",
                "correlation_id": "ct.correlation.kernel.verified-authority",
                "idempotency_key": "ct.idempotency.kernel.verified-authority",
                "action": "issue_license",
            }
        )
        request["actor"]["roles"] = ["rights_steward"]
        request["resource"].update(
            {
                "resource_id": "ct.resource.kernel.verified-license-offer",
                "resource_type": "license_offer",
                "classification": "internal",
            }
        )
        request["approval_evidence"] = ["rights_authority"]

        incomplete = VerifiedAuthorityContext(
            actor_id="ct.actor.test",
            organization_id="ct.org.crownthrive-llc",
            roles=("rights_steward",),
            relationships=tuple(),
            delegations=tuple(),
            approvals=("rights_authority",),
            evidence_refs=("ct.evidence.ref.authority-test",),
        )
        held = self.engine.evaluate(copy.deepcopy(request), verified_authority=incomplete)
        self.assertEqual(held.effect, "hold")
        self.assertIn("verified_relationship_and_delegation_required", held.reasons)

        request["request_id"] = "ct.request.kernel.verified-authority.complete"
        request["correlation_id"] = "ct.correlation.kernel.verified-authority.complete"
        request["idempotency_key"] = "ct.idempotency.kernel.verified-authority.complete"
        complete = VerifiedAuthorityContext(
            actor_id="ct.actor.test",
            organization_id="ct.org.crownthrive-llc",
            roles=("rights_steward",),
            relationships=("ct.relationship.ref.rights-steward",),
            delegations=("ct.delegation.ref.rights-issue",),
            approvals=("rights_authority",),
            evidence_refs=("ct.evidence.ref.authority-test",),
        )
        allowed = self.engine.evaluate(copy.deepcopy(request), verified_authority=complete)
        self.assertEqual(allowed.effect, "allow")
        self.assertTrue(allowed.authority_context_verified)
        self.assertEqual(allowed.relationship_refs, complete.relationships)
        self.assertEqual(allowed.delegation_refs, complete.delegations)
        self.assertEqual(allowed.verified_approvals, complete.approvals)

    def test_idempotent_allow_is_bound_to_verified_authority_context(self):
        request = copy.deepcopy(self.fixture["base_request"])
        request.update(
            {
                "request_id": "ct.request.kernel.authority-bound-idempotency",
                "correlation_id": "ct.correlation.kernel.authority-bound-idempotency",
                "idempotency_key": "ct.idempotency.kernel.authority-bound-idempotency",
                "action": "issue_license",
            }
        )
        request["actor"]["roles"] = ["rights_steward"]
        request["resource"].update(
            {
                "resource_id": "ct.resource.kernel.authority-bound-license-offer",
                "resource_type": "license_offer",
                "classification": "internal",
            }
        )
        request["approval_evidence"] = ["rights_authority"]

        complete = VerifiedAuthorityContext(
            actor_id="ct.actor.test",
            organization_id="ct.org.crownthrive-llc",
            roles=("rights_steward",),
            relationships=("ct.relationship.ref.rights-steward",),
            delegations=("ct.delegation.ref.rights-issue",),
            approvals=("rights_authority",),
            evidence_refs=("ct.evidence.ref.authority-test",),
        )
        first = self.engine.evaluate(copy.deepcopy(request), verified_authority=complete)
        replay = self.engine.evaluate(copy.deepcopy(request), verified_authority=complete)
        self.assertEqual(first.effect, "allow")
        self.assertEqual(first.decision_id, replay.decision_id)
        self.assertEqual(first.event_id, replay.event_id)
        self.assertEqual(len(self.engine.ledger.events), 1)

        with self.assertRaisesRegex(
            KernelContractError,
            "idempotency_key_reused_with_different_authority_context",
        ):
            self.engine.evaluate(copy.deepcopy(request), verified_authority=None)

        changed = VerifiedAuthorityContext(
            actor_id="ct.actor.test",
            organization_id="ct.org.crownthrive-llc",
            roles=("rights_steward",),
            relationships=("ct.relationship.ref.rights-steward",),
            delegations=tuple(),
            approvals=("rights_authority",),
            evidence_refs=("ct.evidence.ref.authority-test",),
        )
        with self.assertRaisesRegex(
            KernelContractError,
            "idempotency_key_reused_with_different_authority_context",
        ):
            self.engine.evaluate(copy.deepcopy(request), verified_authority=changed)
        self.assertEqual(len(self.engine.ledger.events), 1)

    def test_restricted_or_free_form_authority_evidence_is_not_persisted_verbatim(self):
        request = copy.deepcopy(self.fixture["base_request"])
        request["request_id"] = "ct.request.kernel.evidence-sanitize"
        request["correlation_id"] = "ct.correlation.kernel.evidence-sanitize"
        request["idempotency_key"] = "ct.idempotency.kernel.evidence-sanitize"
        marker = "ct.restricted.fixture.material-must-not-be-persisted-verbatim"
        request["authority_evidence"] = [marker]
        decision = self.engine.evaluate(request)
        persisted = self.engine.ledger.events[-1]["payload"]["authority_evidence"]
        self.assertNotIn(marker, persisted)
        self.assertEqual(persisted, list(decision.authority_evidence))
        self.assertTrue(persisted[0].startswith("ct.evidence.digest.sha256."))


if __name__ == "__main__":
    unittest.main()
