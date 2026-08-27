from __future__ import annotations

import datetime as dt
import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "penta_rg.py"
SPEC = importlib.util.spec_from_file_location("penta_rg", MODULE_PATH)
assert SPEC and SPEC.loader
penta_rg = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = penta_rg
SPEC.loader.exec_module(penta_rg)


class PentaRGTests(unittest.TestCase):
    def policy(self):
        return {
            "schema": penta_rg.POLICY_SCHEMA,
            "mode": "FULL_AUTONOMOUS_GOVERNED",
            "authority": {
                "d2": {"mode": "bounded_autonomous"},
                "d3": {
                    "founder_lease": {
                        "enabled": True,
                        "starts_at": "2026-08-27T00:00:00Z",
                        "expires_at": "2026-09-10T23:59:59Z",
                    }
                },
            },
            "archive": {
                "generic_title_prefixes": ["create "],
                "generic_workflow_paths": [".github/workflows/static.yml"],
            },
            "required_paths": [],
            "required_topology_nodes": [],
            "required_topology_edges": [],
            "vercel": {"required_files": []},
        }

    def test_founder_lease_is_time_bounded(self):
        policy = self.policy()
        active = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        expired = dt.datetime(2026, 9, 11, tzinfo=dt.timezone.utc)
        self.assertTrue(penta_rg.founder_lease_active(policy, active))
        self.assertFalse(penta_rg.founder_lease_active(policy, expired))
        self.assertTrue(penta_rg.authority_allowed(policy, "D2", active))
        self.assertFalse(penta_rg.authority_allowed(policy, "D3", expired))

    def test_full_sha_pins_pass_and_floating_refs_block(self):
        good = "steps:\n  - uses: actions/checkout@" + "a" * 40 + "\n"
        bad = "steps:\n  - uses: actions/checkout@v4\n"
        self.assertEqual([], penta_rg.scan_workflow_text("good.yml", good))
        findings = penta_rg.scan_workflow_text("bad.yml", bad)
        self.assertEqual("workflow_action_not_full_sha_pinned", findings[0].code)
        self.assertEqual("BLOCK", findings[0].severity)

    def test_pull_request_target_untrusted_checkout_is_blocked(self):
        text = """
on:
  pull_request_target:
permissions:
  contents: write
steps:
  - run: echo '${{ github.event.pull_request.head.sha }}'
"""
        codes = {f.code for f in penta_rg.scan_workflow_text("unsafe.yml", text)}
        self.assertIn("untrusted_pr_target_checkout_with_write_authority", codes)

    def test_generic_starter_classification_is_exact(self):
        policy = self.policy()
        self.assertTrue(penta_rg.starter_pr_match("Create static.yml", [".github/workflows/static.yml"], policy))
        self.assertFalse(penta_rg.starter_pr_match("Fix production static route", [".github/workflows/static.yml"], policy))
        self.assertFalse(penta_rg.starter_pr_match("Create static.yml", [".github/workflows/static.yml", "README.md"], policy))

    def test_duplicate_group_uses_changed_file_fingerprint(self):
        groups = penta_rg.duplicate_groups([
            {"number": 1, "files": ["a", "b"]},
            {"number": 2, "files": ["b", "a"]},
            {"number": 3, "files": ["c"]},
        ])
        self.assertEqual([[1, 2]], groups)

    def test_action_required_never_becomes_pass(self):
        state, route = penta_rg.classify_run_conclusion("action_required")
        self.assertEqual("HOLD", state)
        self.assertEqual("provider_approval_or_actor_policy", route)

    def test_request_budget_fails_closed(self):
        budget = penta_rg.RequestBudget(1)
        budget.consume()
        with self.assertRaises(penta_rg.ProviderDeferred):
            budget.consume()

    def test_local_audit_detects_missing_required_path(self):
        policy = self.policy()
        policy["required_paths"] = ["missing.txt"]
        topology = {"schema": penta_rg.TOPOLOGY_SCHEMA, "nodes": [], "edges": []}
        with tempfile.TemporaryDirectory() as tmp:
            result = penta_rg.local_audit(Path(tmp), policy, topology)
        self.assertEqual("HOLD", result["status"])
        self.assertIn("required_path_missing", {f["code"] for f in result["findings"]})
        self.assertFalse(result["pass_manufactured"])

    def test_local_audit_passes_minimal_valid_contract(self):
        policy = self.policy()
        topology = {"schema": penta_rg.TOPOLOGY_SCHEMA, "nodes": [], "edges": []}
        with tempfile.TemporaryDirectory() as tmp:
            result = penta_rg.local_audit(Path(tmp), policy, topology)
        self.assertEqual("PASS", result["status"])
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
