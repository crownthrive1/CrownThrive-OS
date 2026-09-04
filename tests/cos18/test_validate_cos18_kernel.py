from __future__ import annotations
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
S=importlib.util.spec_from_file_location("v",ROOT/"scripts/cos18/validate_cos18_kernel.py");V=importlib.util.module_from_spec(S);assert S.loader;S.loader.exec_module(V)
K=json.loads((ROOT/".crownthrive/releases/cos-1.8.0-rc.1.kernel.json").read_text())
class Tests(unittest.TestCase):
 def test_01_kernel(self): self.assertTrue(V.validate(ROOT)["pass"])
 def test_02_domains(self): self.assertEqual(set(K["pentagovernance_survival_contract"]["domains"]),V.DOMAINS)
 def test_03_constituencies(self): self.assertEqual({x["constituency_id"] for x in K["constituency_compact"]["constituencies"]},V.CONSTITUENCIES)
 def test_04_human_floor(self): self.assertTrue(all(not x["machine_votes_may_satisfy_human_floor"] for x in K["constituency_compact"]["constituencies"]))
 def test_05_founder_separate(self): self.assertTrue(K["constituency_compact"]["founder_assent_is_separate"])
 def test_06_institution_separate(self): self.assertTrue(K["constituency_compact"]["institutional_enactment_is_separate"])
 def test_07_independent_separate(self): self.assertTrue(K["constituency_compact"]["independent_certification_is_separate"])
 def test_08_no_self_certification(self): self.assertIn("PentaGovernance",K["pentagovernance_survival_contract"]["certification"]["certifier_must_be_distinct_from"])
 def test_09_default_deny(self): self.assertEqual(K["penta_release_exact_subject_contract"]["provider_mutation_default"],"DENY")
 def test_10_no_authority(self): self.assertFalse(K["release"]["authority_created"])
 def test_11_not_effective(self): self.assertFalse(K["release"]["constitutional_effectiveness"])
 def test_12_not_production(self): self.assertFalse(K["release"]["production_eligible"])
if __name__=="__main__":unittest.main()
