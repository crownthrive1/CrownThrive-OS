#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'penta_deterministic_memory.v1.json'
SQL = ROOT / 'supabase' / 'migrations' / '20260831094500_penta_deterministic_memory_v1.sql'
MODULE_PATH = ROOT / 'runtime' / 'penta_deterministic_memory.py'
SPEC = importlib.util.spec_from_file_location('penta_deterministic_memory_aliases', MODULE_PATH)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class PentaProviderFamilyAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(CONFIG.read_text(encoding='utf-8'))
        cls.sql = SQL.read_text(encoding='utf-8')
        cls.lower = cls.sql.lower()

    def test_repository_mesh_uses_nine_canonical_families(self):
        expected = {
            'OBSERVABILITY_ORGANIC',
            'KNOWLEDGE_SEMANTICS_DATA',
            'SECURITY_TRUST',
            'ROUTING_INTEROPERABILITY',
            'RESILIENCE_CONTINUITY',
            'INTELLIGENCE_RESEARCH',
            'AUTOMATION_AGENTIC',
            'SYSTEM_ARCHITECTURE',
            'BUILD_RELEASE',
        }
        self.assertEqual(expected, set(self.config['brain_mesh']['support_families']))

    def test_live_provider_aliases_are_explicit_and_bounded(self):
        self.assertEqual(
            {
                'KNOWLEDGE_SEMANTICS_DATA': 'KNOWLEDGE_DATA',
                'ROUTING_INTEROPERABILITY': 'ROUTING_INTEROP',
            },
            self.config['brain_mesh']['production_family_aliases'],
        )
        self.assertIn("when 'knowledge_data' then 'knowledge_semantics_data'", self.lower)
        self.assertIn("when 'routing_interop' then 'routing_interoperability'", self.lower)

    def test_manifest_assigns_canonical_brain_mesh_roles(self):
        manifest = mod.build_manifest(ROOT)
        by_family = {}
        for row in manifest['assignments']:
            if row['brain_mesh_role']:
                by_family.setdefault(row['family_key'], set()).add(row['brain_mesh_role'])
        self.assertIn('verified_context_read', by_family['KNOWLEDGE_SEMANTICS_DATA'])
        self.assertIn('governed_addressability', by_family['ROUTING_INTEROPERABILITY'])

    def test_sql_keeps_authoritative_provider_keys_at_fk_boundaries(self):
        required = "('OBSERVABILITY_ORGANIC'),('KNOWLEDGE_DATA'),('SECURITY_TRUST'),('ROUTING_INTEROP')"
        self.assertIn(required, self.sql)
        self.assertIn("('penta.brain','KNOWLEDGE_DATA','verified_context_read'", self.sql)
        self.assertIn("('penta.brain','ROUTING_INTEROP','governed_addressability'", self.sql)
        self.assertIn("'canonical_family_key',penta_runtime.penta_memory_canonical_family_key_v1(excluded.family_key)", self.sql)


if __name__ == '__main__':
    unittest.main(verbosity=2)
