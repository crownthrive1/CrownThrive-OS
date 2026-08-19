from __future__ import annotations

import json
import unittest
from pathlib import Path

from reference.chlom_runtime import CHLOMReferenceEngine


POLICY = Path(__file__).resolve().parents[1] / "policies" / "core.v0.json"


def request(**overrides):
    value = {
        "request_id": "req_test",
        "action": "read",
        "actor": {
            "actor_id": "ct.actor.test",
            "organization_id": "ct.org.crownthrive-llc",
            "authenticated": True,
            "roles": ["documentation_steward"],
        },
        "resource": {
            "resource_id": "ct.resource.test",
            "resource_type": "documentation",
            "organization_id": "ct.org.crownthrive-llc",
            "classification": "public",
            "status": "current",
            "hold_state": "none",
        },
        "context": {"environment": "test", "purpose": "support", "risk_class": "D1"},
        "approval_evidence": [],
        "docs_impact": {"outcome": "docs_no_change", "reason": "test_only"},
    }
    for key, item in overrides.items():
        value[key] = item
    return value


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        bundle = json.loads(POLICY.read_text(encoding="utf-8"))
        self.engine = CHLOMReferenceEngine(bundle["rules"])

    def test_public_read_allows(self):
        self.assertEqual(self.engine.evaluate(request()).effect, "allow")

    def test_default_deny(self):
        data = request(action="unknown_action")
        decision = self.engine.evaluate(data)
        self.assertEqual(decision.effect, "deny")
        self.assertIn("default_deny_no_matching_rule", decision.reasons)

    def test_restricted_publication_denies(self):
        data = request(action="publish")
        data["resource"].update({"resource_type": "evidence", "classification": "restricted"})
        self.assertEqual(self.engine.evaluate(data).effect, "deny")

    def test_d3_holds(self):
        data = request(action="draft_docs")
        data["context"]["risk_class"] = "D3"
        decision = self.engine.evaluate(data)
        self.assertEqual(decision.effect, "hold")
        self.assertIn("d3_reserved_authority", decision.reasons)

    def test_license_requires_rights_approval(self):
        data = request(action="issue_license")
        data["actor"]["roles"] = ["rights_steward"]
        data["resource"].update({"resource_type": "license_offer", "classification": "internal"})
        decision = self.engine.evaluate(data)
        self.assertEqual(decision.effect, "hold")
        self.assertIn("rights_authority", decision.required_approvals)
        data["approval_evidence"] = ["rights_authority"]
        self.assertEqual(self.engine.evaluate(data).effect, "allow")

    def test_cross_org_denied_and_dail_chain_valid(self):
        data = request()
        data["resource"]["organization_id"] = "ct.org.other"
        self.assertEqual(self.engine.evaluate(data).effect, "deny")
        self.engine.evaluate(request())
        self.assertTrue(self.engine.ledger.verify())


if __name__ == "__main__":
    unittest.main()
