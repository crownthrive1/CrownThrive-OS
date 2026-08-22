import importlib.util, json, pathlib, sys, unittest
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mid',HERE/'master_ip_diligence.py'); M=importlib.util.module_from_spec(spec); sys.modules[spec.name]=M; spec.loader.exec_module(M)
B=json.loads((HERE/'master-ip-diligence-v2.bundle.json').read_text())
class Tests(unittest.TestCase):
 def event(self,t,revenue=None): return {'evidence_type':t,'external_party':True,'verified':True,'independent_verifier_class':'AGENT_D','exact_evidence_ref':'private-ref','evidence_digest':'sha256:'+'a'*64,'recognized_revenue':revenue,'creates_price':False,'creates_checkout':False,'customer_entitlement_created':False}
 def test_bundle_valid(self): self.assertEqual(M.validate_bundle(B),[])
 def test_gate_holds_for_evidence(self): self.assertEqual(M.diligence_gate(B)['status'],'HOLD')
 def test_no_authority(self):
  r=M.diligence_gate(B); self.assertFalse(r['sovereign_vote_created']); self.assertFalse(r['certification_effect']); self.assertFalse(r['appraisal_effect']); self.assertFalse(r['commercial_activation_effect'])
 def test_cost(self): self.assertAlmostEqual(M.cost_approach(100,200,50,.1),315)
 def test_dcf(self): self.assertGreater(M.income_dcf([100,100],.1,.5,0),80)
 def test_royalty(self): self.assertGreater(M.relief_from_royalty([1000,1000],.05,.2,.1),60)
 def test_market_comparable(self): self.assertEqual(M.market_comparable([1,9,5]),5)
 def test_missing_input_holds(self):
  with self.assertRaises(M.Hold): M.cost_approach(None,1,1,.1)
 def test_unverified_commercial_excluded(self): self.assertEqual(M.commercial_proof([{'evidence_type':'PAYMENT','external_party':True,'recognized_revenue':1}])['stage'],'P0_HYPOTHESIS')
 def test_paid_pilot(self): self.assertEqual(M.commercial_proof([self.event('PILOT'),self.event('PAYMENT',1)])['stage'],'P3_PAID_PILOT')
 def test_commerce_effects_false(self):
  r=M.commercial_proof([self.event('PAYMENT',1)]); self.assertFalse(r['price_created']); self.assertFalse(r['checkout_created']); self.assertFalse(r['entitlement_created'])
 def test_sbom_versions(self):
  r=M.sbom_candidate(HERE); self.assertEqual(r['cyclonedx']['specVersion'],'1.7'); self.assertEqual(r['spdx']['spdxVersion'],'3.0.1'); self.assertEqual(r['spdx']['certificationEffect'],'NONE')
 def test_agent_non_voting(self): self.assertTrue(B['agent']['non_voting']); self.assertFalse(B['agent']['D3_allowed'])
 def test_zero_claims(self): self.assertEqual(B['registries']['inventions']['patentability_conclusions'],0); self.assertEqual(B['registries']['chain_of_title']['verified_title_count'],0); self.assertEqual(B['registries']['valuation']['valued_asset_count'],0); self.assertEqual(B['registries']['commercial_proof']['paid_customers'],0)
if __name__=='__main__': unittest.main()
