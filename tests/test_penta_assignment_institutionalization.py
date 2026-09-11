from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PentaAssignmentInstitutionalizationTests(unittest.TestCase):
    def text(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_contracts_are_valid_json(self) -> None:
        assignment = json.loads(self.text("contracts/penta/assignment-fulfillment-v1.schema.json"))
        institution = json.loads(self.text("contracts/penta/institutionalization-v1.schema.json"))
        self.assertEqual(assignment["properties"]["contract"]["const"], "ct.penta.assignment-fulfillment.v1")
        self.assertEqual(institution["properties"]["contract"]["const"], "ct.penta.institutionalization.v1")

    def test_all_constitutional_families_have_obligations(self) -> None:
        core = self.text("supabase/migrations/20260830211500_penta_assignment_institutionalization_core_v1.sql")
        families = {
            "AUTOMATION_AGENTIC",
            "BUILD_RELEASE",
            "COMMERCE_ECONOMY",
            "COMMUNICATIONS_SERVICE",
            "GOVERNANCE_LEGAL",
            "INTELLIGENCE_RESEARCH",
            "KNOWLEDGE_DATA",
            "MEDIA_CREATIVE",
            "OBSERVABILITY_ORGANIC",
            "RESILIENCE_CONTINUITY",
            "ROUTING_INTEROP",
            "SECURITY_TRUST",
            "SYSTEM_ARCHITECTURE",
            "TRANSPORT_PRIMITIVES",
            "WORKFORCE_PEOPLE",
        }
        for family in families:
            self.assertIn(f"('{family}'", core)
        self.assertEqual(len(families), 15)

    def test_institutional_gate_requires_full_evidence(self) -> None:
        runtime = self.text("supabase/migrations/20260830211700_penta_assignment_institutionalization_runtime_v1.sql")
        for predicate in (
            "i.evidence_readback",
            "i.decision_readback",
            "i.execution_readback",
            "i.activation_readback",
            "i.pentadocs_state='READBACK_PASS'",
            "i.provider_projection_state='READBACK_PASS'",
            "i.os_projection_state='READBACK_PASS'",
            "i.chain_state='PASS'",
            "i.certification_state in ('ACTIVE','NOT_REQUIRED')",
        ):
            self.assertIn(predicate, runtime)
        self.assertIn("verify_dail_chain_v3", runtime)
        self.assertIn("originator_cannot_self_certify", runtime)

    def test_edge_provider_has_no_deadline_only_terminalization(self) -> None:
        edge = self.text("supabase/functions/penta-pr-terminal-provider/index.ts")
        self.assertIn('const VERSION = "4.0.0"', edge)
        self.assertIn("institutionalGate", edge)
        self.assertIn('penta_assignment_pr_terminal_gate_v1', edge)
        self.assertIn("deadline_only_terminalization: false", edge)
        self.assertIn("retroactive_close: false", edge)
        self.assertIn("retroactive_merge: false", edge)
        self.assertNotIn("hard_deadline_expired", edge)

    def test_workflow_is_classification_only(self) -> None:
        workflow = self.text(".github/workflows/penta-pr-lifecycle-reusable.yml")
        wrapper = self.text("scripts/penta_pr_lifecycle_v4.py")
        self.assertIn("penta_pr_lifecycle_v4.py", workflow)
        self.assertIn("classification, labels, comments, and evidence projection only", workflow)
        self.assertIn("legacy.pentapr", wrapper)
        self.assertNotIn("legacy.pentamerge", wrapper)
        self.assertNotIn("legacy.pentacloser", wrapper)
        self.assertNotIn("attempt_merge", wrapper)

    def test_existing_native_clock_is_reused(self) -> None:
        security = self.text("supabase/migrations/20260830211800_penta_assignment_security_registry_v1.sql")
        self.assertIn("penta_assignment_fulfillment_tick_v1", security)
        self.assertIn("new_clock_created',false", security)
        self.assertIn("ct-penta-self-v1", security)
        self.assertNotIn("cron.schedule", security)

    def test_public_mutation_roles_are_revoked(self) -> None:
        security = self.text("supabase/migrations/20260830211800_penta_assignment_security_registry_v1.sql")
        self.assertIn("revoke execute on function", security.lower())
        self.assertIn("from public, anon, authenticated", security.lower())
        self.assertIn("grant execute on function", security.lower())
        self.assertIn("to service_role", security.lower())


if __name__ == "__main__":
    unittest.main()
