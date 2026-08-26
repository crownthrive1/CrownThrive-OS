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

    def test_registered_member_can_pass_registry_signal_gate(self):
        snapshot = {"members": [{
            "machine_key": "penta.mail", "maturity": "certified", "execution_eligible_by_registry": True,
            "implementation_signals": ["runtime/penta_mail.py"],
        }]}
        gate = prs.gate_member(snapshot, "penta.mail")
        self.assertTrue(gate["eligible"])
        self.assertIn("downstream", gate["reason"])


if __name__ == "__main__":
    unittest.main()
