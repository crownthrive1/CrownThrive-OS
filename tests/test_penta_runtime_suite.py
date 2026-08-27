import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penta_runtime_suite", ROOT / "runtime" / "penta_runtime_suite.py")
prs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prs
SPEC.loader.exec_module(prs)


class PentaRuntimeSuiteTests(unittest.TestCase):
    def test_collect_members_and_fail_closed_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "data" / "penta").mkdir(parents=True)
            (root / "data" / "penta" / "systems.registry.json").write_text(json.dumps({
                "systems": [{"machine_key": "penta.mail", "canonical_name": "PentaMail", "maturity": "specified", "risk_ceiling": "D2"}]
            }), encoding="utf-8")
            members = prs.collect_members(root)
            self.assertIn("penta.mail", members)
            snapshot = {"members": [{
                "machine_key": "penta.mail", "maturity": "specified", "execution_eligible_by_registry": False,
                "implementation_signals": ["runtime/penta_mail.py"],
            }]}
            gate = prs.gate_member(snapshot, "penta.mail")
            self.assertFalse(gate["eligible"])
            self.assertEqual(gate["disposition"], "hold_fail_closed")

    def test_duplicate_machine_keys_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "data" / "penta"
            data.mkdir(parents=True)
            payload = {"systems": [{"machine_key": "penta.mail", "canonical_name": "PentaMail", "maturity": "specified"}]}
            (data / "a.json").write_text(json.dumps(payload), encoding="utf-8")
            (data / "b.json").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(prs.PentaRuntimeSuiteError):
                prs.collect_members(root)

    def test_derived_os_v1_census_is_not_reingested(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "data" / "penta"
            data.mkdir(parents=True)
            payload = {"systems": [{"machine_key": "penta.mail", "canonical_name": "PentaMail", "maturity": "specified"}]}
            (data / "systems.registry.json").write_text(json.dumps(payload), encoding="utf-8")
            (data / "os-v1.discoveries.json").write_text(json.dumps(payload), encoding="utf-8")
            (data / "os-v1.registry.json").write_text(json.dumps(payload), encoding="utf-8")
            members = prs.collect_members(root)
            self.assertEqual(set(members), {"penta.mail"})
            self.assertEqual(
                members["penta.mail"]["source"],
                "data/penta/systems.registry.json",
            )

    def test_live_snapshot_preserves_catalog_and_provider_boundaries(self):
        snapshot = prs.build_snapshot(ROOT)
        self.assertEqual(snapshot["promotion_count"], 5)
        self.assertFalse(snapshot["provider_states_promoted"])
        mail = snapshot["pentamail"]
        self.assertEqual(mail["catalog_maturity"], "specified")
        self.assertEqual(mail["effective_maturity"], "production")
        self.assertEqual(mail["provider_state"], "SEPARATELY_GATED_NOT_PROMOTED_BY_RUNTIME_SUITE")

    def test_registered_member_can_pass_registry_signal_gate(self):
        snapshot = {"members": [{
            "machine_key": "penta.mail", "maturity": "certified", "execution_eligible_by_registry": True,
            "implementation_signals": ["runtime/penta_mail.py"],
        }]}
        gate = prs.gate_member(snapshot, "penta.mail")
        self.assertTrue(gate["eligible"])
        self.assertIn("downstream", gate["reason"])

    def test_generated_bytecode_is_not_an_implementation_signal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "runtime" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "penta_mail.cpython-312.pyc").write_bytes(b"generated")
            self.assertEqual(prs.implementation_signals(root, "penta.mail"), [])


if __name__ == "__main__":
    unittest.main()
