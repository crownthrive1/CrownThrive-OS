import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('penta_protocols',ROOT/'runtime/penta_protocols.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_suite_complete_active_fail_closed():
    r=m.validate_suite();assert r['ok'],r['errors'];assert r['required_protocol_count']==10;assert set(r['active_protocols'])==set(m.REQUIRED_FLOW)
def test_financial_side_effects_gated():
    r=m.load_registry();assert r['protocols']['SmartTreasury']['side_effect_mode']=='gated';assert r['protocols']['PentaPay']['side_effect_mode']=='gated';assert r['protocols']['DAIL']['side_effect_mode']=='append_only_gated';assert r['activation']['external_money_movement']=='gated'
def test_preflight_computes_without_mutation():
    r=m.evaluate({'cookie_id':'c','node_did':'did:ct:test','workload_id':'w','release_id':'r','operation':'build','meter_units':'10','gas_per_unit':'2.5','rate_per_gas':'0.04'});assert r['gas']['units']=='25.000000';assert r['pay']['atomic_price']=='1.000000';assert r['pay']['execution']=='gated';assert r['release']['decision']=='HOLD';assert not r['hard_boundaries']['money_movement_performed']
def test_release_pass_requires_readbacks():
    r=m.evaluate({'cookie_id':'c','node_did':'did:ct:test','workload_id':'w','release_id':'r','operation':'deploy','meter_units':'4','gas_per_unit':'1','rate_per_gas':'0.25','provider_authorized':True,'provider_readback':True,'previous_hash':'sha256:x','dail_readback':True,'governance_pass':True});assert r['release']['decision']=='PASS';assert not r['release']['provider_side_effects_performed']
