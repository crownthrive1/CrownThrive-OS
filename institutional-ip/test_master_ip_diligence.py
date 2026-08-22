import copy, importlib.util, json, pathlib, sys, unittest
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mid',HERE/'master_ip_diligence.py'); M=importlib.util.module_from_spec(spec); sys.modules[spec.name]=M; spec.loader.exec_module(M)
B=json.loads((HERE/'master-ip-diligence-v3.bundle.json').read_text())
D='sha256:'+'a'*64
H='b'*40
class Tests(unittest.TestCase):
 def event(self,t,revenue=None): return {'evidence_type':t,'external_party':True,'verified':True,'independent_verifier_class':'AGENT_D','exact_evidence_ref':'private-ref','evidence_digest':D,'recognized_revenue':revenue,'creates_price':False,'creates_checkout':False,'customer_entitlement_created':False}
 def envelope(self): return {'authority':'D1','non_voting':True,'sovereign_voter':False,'source_head':H,'evidence_digest':D,'body_in_public_envelope':False,'provider_write_requested':False,'database_write_requested':False}
 def framework(self): return {'packet_id':'ct.packet.x.v1','framework_id':'ct.framework.x','lifecycle_state':'RESEARCH_CANDIDATE','source_repository':'crownthrive1/x','source_head':H,'artifact_digest':D,'ip_classification':'PUBLIC_STANDARD_CANDIDATE','title_state':'HOLD','release_state':'HOLD','commercial_state':'CANDIDATE','operational':False,'voting':False,'authority':'D1'}
 def offer(self): return {'commerce_authority':'THRIVEEVERGREEN','offer_id':'ct.offer.x','asset_id':'ct.ip.x','title_state':'VERIFIED_CHAIN_OF_TITLE','chlom_rights_state':'PASS','ip_publication_state':'PUBLIC_SAFE_ACCEPTED','release_state':'PASS','commercial_proof_stage':'P3_PAID_PILOT','commercial_proof_required':True,'minimum_commercial_stage':'P3_PAID_PILOT','exact_offer_digest':D,'create_price':False,'create_checkout':False,'create_entitlement':False,'create_ecac':False}
 def test_bundle_valid(self): self.assertEqual(M.validate_bundle(B),[])
 def test_gate_holds(self): self.assertEqual(M.diligence_gate(B)['status'],'HOLD')
 def test_cost(self): self.assertAlmostEqual(M.cost_approach(100,200,50,.1),315)
 def test_dcf(self): self.assertGreater(M.income_dcf([100,100],.1,.5,0),80)
 def test_royalty(self): self.assertGreater(M.relief_from_royalty([1000,1000],.05,.2,.1),60)
 def test_market(self): self.assertEqual(M.market_comparable([1,9,5]),5)
 def test_missing_input(self):
  with self.assertRaises(M.Hold): M.cost_approach(None,1,1,.1)
 def test_paid_pilot(self): self.assertEqual(M.commercial_proof([self.event('PILOT'),self.event('PAYMENT',1)])['stage'],'P3_PAID_PILOT')
 def test_unverified_excluded(self): self.assertEqual(M.commercial_proof([{'evidence_type':'PAYMENT','external_party':True,'recognized_revenue':1}])['stage'],'P0_HYPOTHESIS')
 def test_evidence_accept(self): self.assertEqual(M.validate_evidence_envelope(self.envelope()).status,'PASS_CANDIDATE')
 def test_evidence_d3_hold(self): x=self.envelope(); x['authority']='D3'; self.assertEqual(M.validate_evidence_envelope(x).code,'D3_OR_UNKNOWN_AUTHORITY')
 def test_evidence_secret_hold(self): x=self.envelope(); x['api_key']='x'; self.assertEqual(M.validate_evidence_envelope(x).code,'PROTECTED_FIELD_PROHIBITED')
 def test_framework_intake(self): self.assertEqual(M.framework_factory_intake(self.framework()).code,'FRAMEWORK_ASSET_CANDIDATE_PREPARED')
 def test_framework_active_hold(self): x=self.framework(); x['operational']=True; self.assertEqual(M.framework_factory_intake(x).code,'ACTIVE_OR_VOTING_PACKET_NOT_AUTO_INGESTIBLE')
 def test_chlom_pass_reference(self): self.assertEqual(M.chlom_rights_bridge({'rights_authority':'CHLOM','rights_decision':'PASS','decision_digest':D,'body_in_public_envelope':False}).status,'PASS_CANDIDATE')
 def test_chlom_not_authority(self): self.assertEqual(M.chlom_rights_bridge({'rights_authority':'OTHER','rights_decision':'PASS','decision_digest':D,'body_in_public_envelope':False}).code,'CHLOM_AUTHORITY_REQUIRED')
 def test_thriveevergreen_candidate(self): self.assertEqual(M.thriveevergreen_gate(self.offer()).code,'ELIGIBLE_FOR_THRIVEEVERGREEN_REVIEW')
 def test_title_hold(self): x=self.offer(); x['title_state']='HOLD'; self.assertEqual(M.thriveevergreen_gate(x).code,'CHAIN_OF_TITLE_NOT_VERIFIED')
 def test_commercial_threshold(self): x=self.offer(); x['commercial_proof_stage']='P2_DESIGN_PARTNER_OR_LOI'; self.assertEqual(M.thriveevergreen_gate(x).code,'COMMERCIAL_PROOF_THRESHOLD_NOT_MET')
 def test_no_ecac(self): x=self.offer(); x['create_ecac']=True; self.assertEqual(M.thriveevergreen_gate(x).code,'ACTIVATION_SIDE_EFFECT_PROHIBITED')
 def test_federation_accept(self): self.assertEqual(M.repository_federation_evidence({'non_voting':True,'sovereign_voter':False,'sync_agents_requested':False,'oidc_verified':True,'source_head':H,'contract_digest':D}).status,'PASS_CANDIDATE')
 def test_federation_oidc_hold(self): self.assertEqual(M.repository_federation_evidence({'non_voting':True,'sovereign_voter':False,'sync_agents_requested':False,'oidc_verified':False,'source_head':H,'contract_digest':D}).code,'OIDC_REQUIRED')
 def test_agent_controls(self): self.assertTrue(B['agent']['non_voting']); self.assertFalse(B['agent']['D3_allowed']); self.assertFalse(B['agent']['provider_or_database_write'])
 def test_zero_claims(self): self.assertEqual(B['five_systems']['invention_registry']['patentability_conclusions'],0); self.assertEqual(B['five_systems']['chain_of_title']['verified_title_count'],0); self.assertEqual(B['five_systems']['valuation']['valued_asset_count'],0); self.assertEqual(B['five_systems']['commercial_proof']['paid_customers'],0)
if __name__=='__main__': unittest.main()
