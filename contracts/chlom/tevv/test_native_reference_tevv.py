from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from reference.chlom_runtime import CHLOMReferenceEngine
from reference.chlom_runtime.model import KernelContractError
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
    if evidence_engine.ledger.events[-1]["payload"].get("authority_evidence") == [marker]:
        findings.add("ct.finding.tevv.restricted-evidence-reference-unsanitized")

    return findings


class NativeReferenceTEVV(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CHLOMReferenceEngine(load_rules())

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

    def test_detector_preserves_open_high_findings(self) -> None:
        self.assertEqual(
            collect_blocking_findings(),
            {
                "ct.finding.tevv.authority-approval-self-assertion",
                "ct.finding.tevv.restricted-evidence-reference-unsanitized",
            },
        )


if __name__ == "__main__":
    unittest.main()
