#!/usr/bin/env python3
"""CrownThrive public-safe Master IP Diligence engine v2.

This module implements public validation and scenario logic for five connected systems:
invention records, chain of title, valuation readiness, supply-chain evidence and
commercial proof. It does not determine legal inventorship, ownership, patentability,
appraisal value, market validation, certification or sovereign authority.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from statistics import median
from typing import Any, Sequence
import argparse, hashlib, json, math, pathlib, re, uuid

DIGEST=re.compile(r'^(?:sha256:)?[0-9a-f]{64}$')
VERIFIERS={'AGENT_B','AGENT_D','AGENT_S','FINANCE_OPERATOR','EXTERNAL_PROFESSIONAL'}
EXTERNAL_TYPES={'INTERVIEW','PROBLEM_CONFIRMATION','DESIGN_PARTNER','WAITLIST','LOI','PILOT','PAID_INVOICE','PAYMENT','USAGE','RENEWAL','RETENTION','EXPANSION','REFERRAL','CASE_STUDY','CHURN','REFUND','DISPUTE'}
PROHIBITED_KEYS={'password','secret','api_key','access_token','refresh_token','private_key','fingerprint_value','private_evidence_body','vault_location','private_runtime_entrypoint','weights','calibration','defensive_rules','private_eval_corpus'}

class Hold(ValueError): pass

def require(ok:bool,msg:str):
    if not ok: raise Hold(msg)
def number(name,v,minimum=None,maximum=None):
    require(v is not None and not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v),name+':INPUT_REQUIRED')
    if minimum is not None: require(v>=minimum,name+':BELOW_MINIMUM')
    if maximum is not None: require(v<=maximum,name+':ABOVE_MAXIMUM')
    return float(v)
def present_value(amount,discount_rate,year): return number('amount',amount)/((1+number('discount_rate',discount_rate,0,1))**int(number('year',year,1)))
def cost_approach(direct_costs,labor_costs,overhead,obsolescence_factor): return (number('direct_costs',direct_costs,0)+number('labor_costs',labor_costs,0)+number('overhead',overhead,0))*(1-number('obsolescence_factor',obsolescence_factor,0,1))
def income_dcf(cash_flows:Sequence[float],discount_rate,success_probability=1.0,terminal_value=0.0):
    require(bool(cash_flows),'cash_flows:INPUT_REQUIRED'); r=number('discount_rate',discount_rate,0,1); p=number('success_probability',success_probability,0,1); tv=number('terminal_value',terminal_value,0)
    return sum(present_value(number(f'cash_flow_{i}',x),r,i)*p for i,x in enumerate(cash_flows,1))+present_value(tv,r,len(cash_flows))*p
def relief_from_royalty(revenues,royalty_rate,tax_rate,discount_rate):
    require(bool(revenues),'revenues:INPUT_REQUIRED'); rr=number('royalty_rate',royalty_rate,0,1); tr=number('tax_rate',tax_rate,0,1); dr=number('discount_rate',discount_rate,0,1)
    return sum(present_value(number(f'revenue_{i}',x,0)*rr*(1-tr),dr,i) for i,x in enumerate(revenues,1))
def market_comparable(values):
    vals=sorted(number(f'comparable_{i}',v,0) for i,v in enumerate(values,1)); require(len(vals)>=3,'three_comparables_required'); return median(vals)

def verified_external(event):
    return isinstance(event,dict) and event.get('external_party') is True and event.get('evidence_type') in EXTERNAL_TYPES and event.get('verified') is True and event.get('independent_verifier_class') in VERIFIERS and isinstance(event.get('exact_evidence_ref'),str) and len(event['exact_evidence_ref'])>=4 and DIGEST.fullmatch(str(event.get('evidence_digest',''))) is not None and event.get('creates_price') is False and event.get('creates_checkout') is False and event.get('customer_entitlement_created') is False

def commercial_proof(records):
    external=[x for x in records if verified_external(x)]; count=lambda t:sum(1 for x in external if x.get('evidence_type')==t)
    stage='P0_HYPOTHESIS'; interviews=count('INTERVIEW'); confirmations=count('PROBLEM_CONFIRMATION'); design=count('DESIGN_PARTNER'); lois=count('LOI'); pilots=count('PILOT'); payments=count('PAYMENT')+count('PAID_INVOICE'); renew=count('RENEWAL'); retain=count('RETENTION'); expand=count('EXPANSION'); revenue=sum(float(x.get('recognized_revenue') or 0) for x in external if x.get('evidence_type') in {'PAYMENT','PAID_INVOICE'})
    if interviews>=3 and confirmations>=1: stage='P1_DISCOVERY_INTERVIEWS'
    if design>=1 or lois>=1: stage='P2_DESIGN_PARTNER_OR_LOI'
    if pilots>=1 and payments>=1 and revenue>0: stage='P3_PAID_PILOT'
    if stage=='P3_PAID_PILOT' and (renew>=1 or retain>=1): stage='P4_RETAINED_OR_RENEWED'
    if stage=='P4_RETAINED_OR_RENEWED' and renew>=1 and expand>=1: stage='P5_RECURRING_AND_EXPANDING'
    return {'stage':stage,'verified_external_event_count':len(external),'recognized_revenue':revenue,'excluded_record_count':len(records)-len(external),'price_created':False,'checkout_created':False,'entitlement_created':False}

def walk(v):
    if isinstance(v,dict):
        for k,x in v.items(): yield str(k),x; yield from walk(x)
    elif isinstance(v,list):
        for x in v: yield from walk(x)
def public_safe(v): return not any(k.lower() in PROHIBITED_KEYS for k,_ in walk(v))

def validate_bundle(bundle):
    errors=[]; agent=bundle.get('agent',{}); regs=bundle.get('registries',{}); offers=bundle.get('commercial_offers',{}); release=bundle.get('release_evidence',{})
    if bundle.get('lifecycle')!='PREPARED_NOT_ACTIVATED': errors.append('lifecycle_drift')
    if bundle.get('sovereign_vote_created') is not False or bundle.get('commercial_activation') is not False: errors.append('authority_or_commercial_drift')
    if agent.get('non_voting') is not True or agent.get('D3_allowed') is not False or agent.get('may_independently_verify_C_originated_work') is not False: errors.append('agent_authority_drift')
    if regs.get('inventions',{}).get('record_count')!=20 or regs.get('inventions',{}).get('patentability_conclusions')!=0: errors.append('invention_projection_drift')
    if regs.get('chain_of_title',{}).get('verified_title_count')!=0 or regs.get('chain_of_title',{}).get('commercialization_authority_created') is not False: errors.append('title_overclaim')
    if regs.get('valuation',{}).get('valued_asset_count')!=0 or regs.get('valuation',{}).get('portfolio_value') is not None: errors.append('valuation_overclaim')
    if regs.get('commercial_proof',{}).get('paid_customers')!=0 or regs.get('commercial_proof',{}).get('recognized_revenue')!=0: errors.append('commercial_proof_overclaim')
    if offers.get('checkout') is not False or offers.get('customer_entitlement') is not False or offers.get('stripe_product_or_price') is not None or any(x.get('price') is not None for x in offers.get('offers',[])): errors.append('commerce_activation_drift')
    if release.get('activation_effect') is not False or release.get('certification_effect') is not False or release.get('appraisal_effect') is not False: errors.append('release_authority_drift')
    if not public_safe(bundle): errors.append('protected_field_in_public_bundle')
    return errors

def diligence_gate(bundle):
    errors=validate_bundle(bundle); regs=bundle['registries']; blockers=list(errors)
    if regs['inventions']['record_count']>regs['inventions']['patentability_conclusions']: blockers.append('inventions_on_documentary_hold')
    if regs['chain_of_title']['hold_count']: blockers.append('chain_of_title_unverified')
    if regs['valuation']['valued_asset_count']<regs['valuation']['asset_count']: blockers.append('valuation_inputs_missing')
    if regs['commercial_proof']['stage'] not in {'P3_PAID_PILOT','P4_RETAINED_OR_RENEWED','P5_RECURRING_AND_EXPANDING'}: blockers.append('commercial_proof_below_paid_pilot')
    release=bundle['release_evidence']
    if release['vulnerability']['current_result'] not in {'PASS_NO_KNOWN_VULNERABILITIES','ACCEPTED_EXCEPTION'}: blockers.append('vulnerability_scan_not_accepted')
    if release['provenance']['signed'] is not True: blockers.append('provenance_unsigned')
    if release['provenance']['independently_verified'] is not True: blockers.append('provenance_not_independently_verified')
    return {'status':'HOLD' if blockers else 'PASS_FOR_INDEPENDENT_DILIGENCE','blockers':sorted(set(blockers)),'legal_conclusion':False,'appraisal_effect':False,'certification_effect':False,'sovereign_vote_created':False,'provider_or_database_write_effect':False,'commercial_activation_effect':False}

def sbom_candidate(root:pathlib.Path):
    fs=[p for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.zip'}]
    comps=[]
    for p in fs:
        comps.append({'type':'file','name':p.relative_to(root).as_posix(),'hashes':[{'alg':'SHA-256','content':hashlib.sha256(p.read_bytes()).hexdigest()}]})
    cdx={'$schema':'https://cyclonedx.org/schema/bom-1.7.schema.json','bomFormat':'CycloneDX','specVersion':'1.7','serialNumber':f'urn:uuid:{uuid.uuid4()}','version':1,'components':comps}
    spdx={'@context':'https://spdx.org/rdf/3.0.1/spdx-context.jsonld','type':'SpdxDocument','spdxVersion':'3.0.1','profileConformance':['core','software'],'certificationEffect':'NONE','element':[{'type':'software_File','spdxId':f'spdx:File-{i}','name':c['name'],'verifiedUsing':[{'type':'Hash','algorithm':'sha256','hashValue':c['hashes'][0]['content']}]} for i,c in enumerate(comps,1)]}
    return {'cyclonedx':cdx,'spdx':spdx}

def main():
    p=argparse.ArgumentParser(); p.add_argument('bundle'); p.add_argument('--gate',action='store_true'); a=p.parse_args(); bundle=json.loads(pathlib.Path(a.bundle).read_text()); result=diligence_gate(bundle) if a.gate else {'status':'PASS' if not validate_bundle(bundle) else 'FAIL','errors':validate_bundle(bundle)}; print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result['status']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
