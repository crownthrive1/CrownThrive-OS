from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "penta_os_readiness_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("penta_os_readiness_diagnostic", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def healthy_snapshot() -> dict:
    sha = "a" * 40
    return {
        "observed_at": "2026-09-02T18:30:00Z",
        "source": {
            "main_sha": sha,
            "deployment_sha": sha,
            "registry_version": "1.5.0",
            "registry_count": 215,
            "registry_blob_sha": "b" * 40,
        },
        "pr": {
            "policy_key": "ct.penta.pr-terminalization-policy.v2",
            "provider_sync_stale": False,
            "unclassified_v2": 0,
            "overdue": 0,
        },
        "identity": {
            "registry_count": 472,
            "projection_drift": False,
            "source_sha256": "c" * 64,
        },
        "dnd": {
            "canonical_identity": "penta.dnd",
            "runtime_present": True,
            "pm_execution_eligible": False,
            "active_scope_kinds": 49,
            "authority_created": False,
        },
        "gates": {
            "penta_security": "PASS",
            "chlom": "PASS",
            "cie": "N/A",
            "penta_certifier": "PASS",
        },
    }


class DiagnosticTests(unittest.TestCase):
    def test_aligned_snapshot_is_ready_for_independent_review(self) -> None:
        result = MODULE.evaluate(healthy_snapshot())
        self.assertEqual(result["disposition"], "READY_FOR_INDEPENDENT_REVIEW")
        self.assertEqual(result["score"], 100)
        self.assertFalse(result["authority_created"])
        self.assertEqual(result["independent_certification"], "NOT_PERFORMED")

    def test_deployment_mismatch_is_hold(self) -> None:
        snapshot = healthy_snapshot()
        snapshot["source"]["deployment_sha"] = "d" * 40
        result = MODULE.evaluate(snapshot)
        self.assertEqual(result["disposition"], "HOLD_REMEDIATION_REQUIRED")
        self.assertIn("production deployment does not match protected main", result["remediation"])

    def test_pr_backlog_is_hold(self) -> None:
        snapshot = healthy_snapshot()
        snapshot["pr"]["unclassified_v2"] = 3
        result = MODULE.evaluate(snapshot)
        self.assertIn("pr.unclassified_v2=3 requires remediation", result["remediation"])

    def test_dnd_authority_expansion_is_hold(self) -> None:
        snapshot = healthy_snapshot()
        snapshot["dnd"]["authority_created"] = True
        snapshot["dnd"]["pm_execution_eligible"] = True
        result = MODULE.evaluate(snapshot)
        self.assertEqual(result["domains"][3]["state"], "HOLD")

    def test_missing_gate_is_unknown(self) -> None:
        snapshot = healthy_snapshot()
        del snapshot["gates"]["penta_certifier"]
        result = MODULE.evaluate(snapshot)
        self.assertEqual(result["disposition"], "UNKNOWN_EVIDENCE_INCOMPLETE")
        self.assertIn("gate penta_certifier is UNKNOWN", result["remediation"])

    def test_secret_like_keys_are_redacted_before_hash_and_report(self) -> None:
        snapshot = healthy_snapshot()
        snapshot["provider"] = {"api_key": "do-not-emit", "nested": {"access_token": "hidden"}}
        redacted = MODULE.redact(snapshot)
        rendered = json.dumps(redacted)
        self.assertNotIn("do-not-emit", rendered)
        self.assertNotIn("hidden", rendered)
        self.assertEqual(redacted["provider"]["api_key"], "[REDACTED]")

    def test_service_migration_uses_current_price_band_column(self) -> None:
        migration = (
            ROOT
            / "supabase"
            / "migrations"
            / "20260902183500_penta_os_readiness_diagnostic_service_v1.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("default_band_key", migration)
        self.assertNotIn("v_existing.default_band <>", migration)
        self.assertIn("penta.deep.v1", migration)

    def test_cli_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.json"
            json_path = tmp_path / "result.json"
            markdown_path = tmp_path / "result.md"
            input_path.write_text(json.dumps(healthy_snapshot()), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(input_path),
                    "--json-output",
                    str(json_path),
                    "--markdown-output",
                    str(markdown_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(json_path.read_text())["score"], 100)
            self.assertIn("not certification", markdown_path.read_text().lower())


if __name__ == "__main__":
    unittest.main()
