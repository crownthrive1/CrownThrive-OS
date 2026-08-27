import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "runtime" / "penta_d3_approval.py"
MIGRATION = ROOT / "supabase" / "migrations" / "20260827170000_d3_founder_production_approval_window_v1.sql"

sys.path.insert(0, str(ROOT / "runtime"))
from penta_d3_approval import BASE_RELEASE_GATES, EFFECT_GATES, evaluate  # noqa: E402


VERSION = "crownthrive-os@97f9d9b993e8d80f29b0ec73f290aef44960f3ab"
CONTENT_SHA = "a" * 64
EVALUATED_AT = datetime(2026, 8, 27, 17, 0, tzinfo=timezone.utc)


def gate(key: str, *, verified_by: str = "ct.penta.agent.vergence") -> dict:
    value = {
        "state": "PASS",
        "evidence_ref": f"dail://evidence/{key}",
        "evidence_sha256": "b" * 64,
        "exact_version_ref": VERSION,
        "content_sha256": CONTENT_SHA,
        "verified_by": verified_by,
        "verified_at": "2026-08-27T16:59:00Z",
    }
    if key == "rollback_readback":
        value.update(
            {
                "rollback_tested": True,
                "baseline_sha256": "c" * 64,
                "post_rollback_sha256": "c" * 64,
            }
        )
    return value


def base_bundle(*, effects: list[str] | None = None) -> dict:
    requested_effects = effects or []
    required = set(BASE_RELEASE_GATES)
    for effect in requested_effects:
        required.update(EFFECT_GATES[effect])
    return {
        "window": {
            "window_id": "ct.d3.founder-production-window.20260827.v1",
            "founder_ref": "ct.person.founder.kavonte-jones-sr",
            "risk_class": "D3",
            "approval_effect": "human_approval_predicate_only",
            "starts_at": "2026-08-27T01:23:52.144189Z",
            "expires_at": "2026-09-10T01:23:52.144189Z",
            "nonrenewing": True,
            "exact_candidate_required": True,
            "independent_evidence_required": True,
            "independent_evidence_substitution_allowed": False,
            "revoked": False,
        },
        "candidate": {
            "subject_ref": "ct.release.crownthrive-os.d3-test",
            "risk_class": "D3",
            "environment": "production",
            "action_class": "commercial_release",
            "exact_version_ref": VERSION,
            "content_sha256": CONTENT_SHA,
            "producer_ref": "ct.penta.agent.build",
            "requested_effects": requested_effects,
        },
        "gates": {key: gate(key) for key in required},
    }


class D3ApprovalEvaluatorTests(unittest.TestCase):
    def test_complete_exact_candidate_is_release_eligible(self):
        result = evaluate(base_bundle(), now=EVALUATED_AT)
        self.assertEqual(result["human_approval_state"], "APPROVED_BY_WINDOW")
        self.assertEqual(result["decision"], "RELEASE_ELIGIBLE")
        self.assertFalse(result["release_authority_created"])

    def test_missing_nonhuman_gate_holds_without_erasing_founder_approval(self):
        bundle = base_bundle()
        bundle["gates"].pop("security")
        result = evaluate(bundle, now=EVALUATED_AT)
        self.assertEqual(result["human_approval_state"], "APPROVED_BY_WINDOW")
        self.assertEqual(result["decision"], "HOLD")
        self.assertTrue(any(c["check"] == "gate.security" and c["status"] == "FAIL" for c in result["checks"]))

    def test_expired_window_cannot_satisfy_human_approval(self):
        result = evaluate(base_bundle(), now=datetime(2026, 9, 10, 1, 23, 53, tzinfo=timezone.utc))
        self.assertEqual(result["human_approval_state"], "NOT_APPROVED")
        self.assertEqual(result["decision"], "HOLD")

    def test_revoked_window_cannot_satisfy_human_approval(self):
        bundle = base_bundle()
        bundle["window"]["revoked"] = True
        result = evaluate(bundle, now=EVALUATED_AT)
        self.assertEqual(result["human_approval_state"], "NOT_APPROVED")

    def test_provider_write_requires_provider_certification(self):
        bundle = base_bundle(effects=["provider_write"])
        bundle["gates"].pop("provider_write_certification")
        result = evaluate(bundle, now=EVALUATED_AT)
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("provider_write_certification", result["required_gates"])

    def test_independent_verifier_must_differ_from_producer(self):
        bundle = base_bundle()
        bundle["gates"]["independent_verification"] = gate(
            "independent_verification", verified_by="ct.penta.agent.build"
        )
        result = evaluate(bundle, now=EVALUATED_AT)
        self.assertEqual(result["decision"], "HOLD")
        self.assertTrue(
            any(c["check"] == "gate.independent_separation" and c["status"] == "FAIL" for c in result["checks"])
        )

    def test_gate_snapshot_mismatch_holds(self):
        bundle = base_bundle()
        bundle["gates"]["technical_tests"]["content_sha256"] = "d" * 64
        result = evaluate(bundle, now=EVALUATED_AT)
        self.assertEqual(result["decision"], "HOLD")

    def test_cli_returns_nonzero_for_incomplete_release(self):
        bundle = base_bundle()
        bundle["gates"].pop("rollback_readback")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bundle.json"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('"decision": "HOLD"', completed.stdout)

    def test_migration_contains_immutable_exact_scope_controls(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        required_fragments = [
            "d3_founder_approval_windows_v1",
            "d3_founder_approval_receipts_v1",
            "d3_founder_approval_revocations_v1",
            "consume_d3_founder_approval_v1",
            "apply_d3_founder_approval_window_v1",
            "enforce_d3_release_contract_v1",
            "independent_evidence_substitution_allowed is false",
            "expires_at = starts_at + interval '14 days'",
            "force row level security",
            "reject_row_mutation_v1",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, sql.lower())


if __name__ == "__main__":
    unittest.main()
