from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from reference.chlom_runtime.evidence_contract import (
    build_chain,
    export_bundle,
    reconstruct_decision_lineage,
    validate_evidence_reference,
    verify_chain,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "reference/chlom_runtime/fixtures/dail_evidence_contract.v1.json"


class EvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.events = build_chain(cls.fixture["event_inputs"])

    def test_evidence_references_are_public_safe(self) -> None:
        for ref in self.fixture["evidence_references"]:
            self.assertEqual(validate_evidence_reference(ref), [])
            self.assertFalse(ref["content_included"])
        restricted = next(
            item for item in self.fixture["evidence_references"] if item["classification"] == "RESTRICTED"
        )
        self.assertFalse(restricted["public_projection_allowed"])

    def test_chain_correlation_and_causation(self) -> None:
        ok, errors = verify_chain(self.events)
        self.assertTrue(ok, errors)
        self.assertEqual(len(self.events), self.fixture["expectations"]["event_count"])
        correlations = {event["correlation_id"] for event in self.events}
        self.assertEqual(len(correlations), 1)
        prior: set[str] = set()
        for event in self.events:
            if event["causation_id"] is not None:
                self.assertIn(event["causation_id"], prior)
            prior.add(event["event_id"])

    def test_tamper_detection(self) -> None:
        tampered = deepcopy(self.events)
        tampered[1]["reason_code"] = "tampered_reason"
        ok, errors = verify_chain(tampered)
        self.assertFalse(ok)
        self.assertTrue(any("event_hash_mismatch" in item for item in errors))

    def test_conflicting_source_fails_closed_to_hold(self) -> None:
        conflict = next(event for event in self.events if event["event_type"] == "source_conflict_opened")
        self.assertEqual(conflict["state"], "hold")
        self.assertEqual(conflict["docs_impact"], "docs_delta_opened")
        self.assertIn("ct.evidence.ref.restricted-001", conflict["evidence_refs"])

    def test_correction_preserves_prior_history(self) -> None:
        lineage = reconstruct_decision_lineage(self.events, "ct.decision.fixture-001")
        self.assertTrue(lineage["chain_verified"], lineage["chain_errors"])
        self.assertIn("ct.dail.event.case-002-decision", lineage["event_ids"])
        self.assertEqual(
            lineage["superseded_by"]["ct.dail.event.case-002-decision"],
            "ct.dail.event.case-003-conflict",
        )
        self.assertEqual(
            lineage["superseded_by"]["ct.dail.event.case-003-conflict"],
            "ct.dail.event.case-004-correction",
        )

    def test_export_bundle_is_portable_and_reconstructable(self) -> None:
        bundle = export_bundle(self.events)
        self.assertEqual(bundle["schema_id"], "ct.export.chlom.dail-bundle.v1")
        self.assertEqual(bundle["event_count"], len(self.events))
        self.assertEqual(bundle["events"], self.events)
        ok, errors = verify_chain(bundle["events"])
        self.assertTrue(ok, errors)
        self.assertEqual(bundle["last_event_hash"], self.events[-1]["event_hash"])
        self.assertEqual(len(bundle["bundle_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
