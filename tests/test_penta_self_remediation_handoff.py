from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.penta_pm_remediation_assign import desired_owners, owner_slug
from scripts.penta_self_remediation_handoff import normalize_finding, remediation_key


class PentaSelfRemediationHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "remediation_assignment": {
                "always_required": ["PentaBuild", "PentaTest", "PentaCertify", "PentaPR"],
                "lane_owners": {
                    "workflow": ["PentaFlows", "PentaActions", "PentaRunners"],
                    "general": ["PentaFactory", "PentaVergence"],
                },
                "high_risk_owners": ["PentaSecure", "PentaBound", "PentaCertify"],
                "blocked_state_owners": ["PentaVergence", "PentaBalancer", "PentaRoute"],
                "reassignment_states": ["blocked", "failed", "stalled", "degraded"],
            }
        }

    def test_normalizes_finding_and_defaults_critical_to_d2(self) -> None:
        finding = normalize_finding(
            {
                "finding_id": "find-123",
                "severity": "critical",
                "lane": "workflow",
                "symptom": "workflow cannot complete",
                "required_pentas": ["PentaHeal", "PentaHeal"],
            }
        )
        self.assertEqual(finding["finding_id"], "find-123")
        self.assertEqual(finding["risk"], "D2")
        self.assertEqual(finding["lane"], "workflow")
        self.assertEqual(finding["required_pentas"], ["PentaHeal"])
        self.assertEqual(finding["source"], "PentaSELF")
        self.assertEqual(finding["pr_authority"], "PentaPR")
        self.assertEqual(finding["pm_authority"], "PentaPM")

    def test_unknown_lane_fails_safe_to_general(self) -> None:
        finding = normalize_finding(
            {"finding_id": "abc", "symptom": "unknown corridor", "lane": "invented"}
        )
        self.assertEqual(finding["lane"], "general")

    def test_explicit_d3_is_preserved(self) -> None:
        finding = normalize_finding(
            {"finding_id": "abc", "symptom": "human reserved", "risk": "D3"}
        )
        self.assertEqual(finding["risk"], "D3")

    def test_remediation_key_is_stable_and_bounded(self) -> None:
        source = "Finding / With Unsafe Characters !!! " * 10
        self.assertEqual(remediation_key(source), remediation_key(source))
        self.assertLessEqual(len(remediation_key(source)), 56)
        self.assertRegex(remediation_key(source), r"^[a-z0-9._-]+$")

    def test_pentapm_routes_complete_workflow_owner_set(self) -> None:
        owners = desired_owners(
            {
                "finding_id": "find-1",
                "lane": "workflow",
                "risk": "D2",
                "state": "open",
                "required_pentas": ["PentaHeal"],
            },
            self.policy,
        )
        for owner in (
            "PentaBuild",
            "PentaTest",
            "PentaCertify",
            "PentaPR",
            "PentaFlows",
            "PentaActions",
            "PentaRunners",
            "PentaSecure",
            "PentaBound",
            "PentaHeal",
        ):
            self.assertIn(owner, owners)

    def test_blocked_state_adds_recovery_owners(self) -> None:
        owners = desired_owners(
            {"finding_id": "find-2", "lane": "general", "risk": "D1", "state": "blocked"},
            self.policy,
        )
        self.assertIn("PentaVergence", owners)
        self.assertIn("PentaBalancer", owners)
        self.assertIn("PentaRoute", owners)

    def test_owner_slug_is_deterministic(self) -> None:
        self.assertEqual(owner_slug("Penta Build / Recovery"), "penta-build-recovery")


if __name__ == "__main__":
    unittest.main()
