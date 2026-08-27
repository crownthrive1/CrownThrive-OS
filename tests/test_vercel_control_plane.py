from __future__ import annotations

import importlib.util
import unittest
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_vercel_control_plane.py"
SPEC = importlib.util.spec_from_file_location("validate_vercel_control_plane", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class VercelControlPlaneTests(unittest.TestCase):
    def test_repository_control_plane_contract(self):
        root = Path(__file__).resolve().parents[1]
        result = module.validate(root)
        self.assertEqual("PASS", result["state"])
        self.assertFalse(result["provider_deployment_claimed"])
        self.assertTrue(result["provider_readback_required"])


if __name__ == "__main__":
    unittest.main()
