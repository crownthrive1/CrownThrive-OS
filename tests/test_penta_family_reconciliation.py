#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'runtime' / 'penta_deterministic_memory.py'
SPEC = importlib.util.spec_from_file_location('penta_deterministic_memory_reconcile', MODULE_PATH)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)

EXPECTED = {
    'penta.bc': 'SYSTEM_ARCHITECTURE',
    'penta.brainmemoryruntime': 'OBSERVABILITY_ORGANIC',
    'penta.clean': 'RESILIENCE_CONTINUITY',
    'penta.flush': 'RESILIENCE_CONTINUITY',
    'penta.harvestor': 'INTELLIGENCE_RESEARCH_IMPACT',
    'penta.hydrate': 'RESILIENCE_CONTINUITY',
    'penta.memorycensus': 'KNOWLEDGE_SEMANTICS_DATA',
    'penta.memoryconfig': 'SYSTEM_ARCHITECTURE',
    'penta.memoryrollback': 'RESILIENCE_CONTINUITY',
    'penta.memoryschema': 'KNOWLEDGE_SEMANTICS_DATA',
    'penta.notifs': 'COMMUNICATIONS_SERVICE',
    'penta.overseer': 'OBSERVABILITY_ORGANIC',
    'penta.prioritize': 'AUTOMATION_AGENTIC',
    'penta.relay': 'ROUTING_INTEROPERABILITY',
}


class PentaFamilyReconciliationTests(unittest.TestCase):
    def test_exact_governed_census_assignments(self):
        census = json.loads((ROOT / mod.NAMESPACE_CENSUS_PATH).read_text(encoding='utf-8'))
        rows = {
            row['canonical_machine_key']: row
            for row in census['records']
            if isinstance(row, dict) and row.get('canonical_machine_key') in EXPECTED
        }
        self.assertEqual(set(EXPECTED), set(rows))
        for machine_key, family_key in EXPECTED.items():
            row = rows[machine_key]
            self.assertEqual(family_key, mod.normalized_family(row.get('family_id') or row.get('family_slug')))
            self.assertFalse(row.get('execution_eligible_by_registry', False))

    def test_manifest_resolves_all_governed_assignments_without_maturity_promotion(self):
        manifest = mod.build_manifest(ROOT)
        rows = {row['machine_key']: row for row in manifest['assignments']}
        for machine_key, family_key in EXPECTED.items():
            self.assertIn(machine_key, rows)
            self.assertEqual(family_key, rows[machine_key]['family_key'])
            if rows[machine_key]['maturity'] not in mod.HOT_MATURITY:
                self.assertFalse(rows[machine_key]['write_enabled'])
                self.assertEqual('COLD_RESERVED', rows[machine_key]['activation_state'])

    def test_census_has_no_unclassified_canonical_penta(self):
        census = json.loads((ROOT / mod.NAMESPACE_CENSUS_PATH).read_text(encoding='utf-8'))
        unresolved = sorted({
            row['canonical_machine_key']
            for row in census['records']
            if isinstance(row, dict)
            and isinstance(row.get('canonical_machine_key'), str)
            and row['canonical_machine_key'].startswith('penta.')
            and not (row.get('family_id') or row.get('family_slug'))
        })
        self.assertEqual([], unresolved)


if __name__ == '__main__':
    unittest.main(verbosity=2)
