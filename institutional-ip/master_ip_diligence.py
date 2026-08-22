#!/usr/bin/env python3
"""Public-safe Master IP Diligence and integration gate engine v3.

No function in this file grants rights, determines inventorship/patentability, creates an
appraisal, activates commerce, writes a provider/database, creates a sovereign vote, or
executes D3. Protected or private evidence bodies remain outside public envelopes.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from statistics import median
from typing import Any, Sequence
import argparse, hashlib, json, math, pathlib, re

DIGEST=re.compile(r'^(?:sha256:)?[0-9a-f]{64}$')
SHA40=re.compile(r'^[0-9a-f]{40}$')
VERIFIERS={'AGENT_B','AGENT_D','AGENT_S','FINANCE_OPERATOR','EXTERNAL_PROFESSIONAL'}
EXTERNAL_TYPES={'INTERVIEW','PROBLEM_CONFIRMATION','DESIGN_PARTNER','WAITLIST','LOI','PILOT','PAID_INVOICE','PAYMENT','USAGE','RENEWAL','RETENTION','EXPANSION','REFERRAL','CASE_STUDY','CHURN','REFUND','DISPUTE'}
PROHIBITED_KEYS={'password','secret','api_key','access_token','refresh_token','private_key','fingerprint_value','private_evidence_body','vault_location','private_runtime_entrypoint','weights','calibration','defensive_rules','private_eval_corpus'}
STAGE_ORDER={'P0_HYPOTHESIS':0,'P1_DISCOVERY_INTERVIEWS':1,'P2_DESIGN_PARTNER_OR_LOI':2,'P3_PAID_PILOT':3,'P4_RETAINED_OR_RENEWED':4,'P5_RECURRING_AND_EXPANDING':5}

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

def walk(v):
    if isinstance(v,dict):
        for k,x in v.items(): yield str(k),x; yield from walk(x)
    elif isinstance(v,list):
        for x in v: yield from walk(x)
def public_safe(v): return not any(k.lower() in PROHIBITED_KEYS for k,_ in walk(v))
def exact_digest(v): return isinstance(v,str) and DIGEST.fullmatch(v) is not None
def exact_head(v): return isinstance(v,str) and SHA40.fullmatch(v) is not None

def verified_external(event):
    return isinstance(event,dict) and event.get('external_party') is True and event.get('evidence_type') in EXTERNAL_TYPES and event.get('verified') is True and event.get('independent_verifier_class') in VERIFIERS and isinstance(event.get('exact_evidence_ref'),str) and len(event['exact_evidence_ref'])>=4 and exact_digest(event.get('evidence_digest')) and event.get('creates_price') is False and event.get('creates_checkout') is False and event.get('customer_entitlement_created') is False

def commercial_proof(records):
    external=[x for x in records if verified_external(x)]; count=lambda t:sum(1 for x in external if x.get('evidence_type')==t)
    stage='P0_HYPOTHESIS'; interviews=count('INTERVIEW'); confirmations=count('PROBLEM_CONFIRMATION'); design=count('DESIGN_PARTNER'); lois=count('LOI'); pilots=count('PILOT'); payments=count('PAYMENT')+count('PAID_INVOICE'); renew=count('RENEWAL'); retain=count('RETENTION'); expand=count('EXPANSION'); revenue=sum(float(x.get('recognized_revenue') or 0) for x in external if x.get('evidence_type') in {'PAYMENT','PAID_INVOICE'})
    if interviews>=3 and confirmations>=1: stage='P1_DISCOVERY_INTERVIEWS'
    if design>=1 or lois>=1: stage='P2_DESIGN_PARTNER_OR_LOI'
    if pilots>=1 and payments>=1 and revenue>0: stage='P3_PAID_PILOT'
    if stage=='P3_PAID_PILOT' and (renew>=1 or retain>=1): stage='P4_RETAINED_OR_RENEWED'
    if stage=='P4_RETAINED_OR_RENEWED' and renew>=1 and expand>=1: stage='P5_RECURRING_AND_EXPANDING'
    return {'stage':stage,'verified_external_event_count':len(external),'recognized_revenue':revenue,'excluded_record_count':len(records)-len(external),'price_created':False,'checkout_created':False,'entitlement_created':False}

@dataclass(frozen=True)
class GateResult:
    status:str
    code:str
    reasons:tuple[str,...]=()
    sovereign_vote_created:bool=False
    rights_granted:bool=False
    ecac_created:bool=False
    provider_write_allowed:bool=False
    database_write_allowed:bool=False
    operational_state_changed:bool=False

def hold(code,*reasons): return GateResult('HOLD',code,tuple(reasons))
def pass_candidate(code,*reasons): return GateResult('PASS_CANDIDATE',code,tuple(reasons))

def validate_evidence_envelope(e):
    if not isinstance(e,dict): return hold('INVALID_SHAPE')
    if not public_safe(e): return hold('PROTECTED_FIELD_PROHIBITED')
    if e.get('authority') not in {'D0','D1','D2'}: return hold('D3_OR_UNKNOWN_AUTHORITY')
    if e.get('non_voting') is not True or e.get('sovereign_voter') is True: return hold('IDENTITY_VOTING_COLLISION')
    if not exact_head(e.get('source_head')): return hold('EXACT_SOURCE_HEAD_REQUIRED')
    if not exact_digest(e.get('evidence_digest')): return hold('EVIDENCE_DIGEST_REQUIRED')
    if e.get('body_in_public_envelope') is not False: return hold('PRIVATE_BODY_PUBLICATION_PROHIBITED')
    if e.get('provider_write_requested') is True or e.get('database_write_requested') is True: return hold('WRITE_REQUEST_PROHIBITED')
    return pass_candidate('EVIDENCE_REFERENCE_ACCEPTED_FOR_CANDIDATE_INGEST')

def framework_factory_intake(packet):
    if not isinstance(packet,dict): return hold('INVALID_FRAMEWORK_PACKET')
    if not public_safe(packet): return hold('PROTECTED_FIELD_PROHIBITED')
    required=['packet_id','framework_id','lifecycle_state','source_repository','source_head','artifact_digest','ip_classification','title_state','release_state','commercial_state']
    missing=[k for k in required if k not in packet]
    if missing: return hold('FRAMEWORK_INTAKE_FIELD_MISSING',*missing)
    if not exact_head(packet['source_head']) or not exact_digest(packet['artifact_digest']): return hold('EXACT_BINDING_REQUIRED')
    if packet.get('operational') is True or packet.get('voting') is True: return hold('ACTIVE_OR_VOTING_PACKET_NOT_AUTO_INGESTIBLE')
    if packet.get('authority') not in {'D0','D1','D2'}: return hold('D3_OR_UNKNOWN_AUTHORITY')
    if packet.get('ip_classification') not in {'PUBLIC_STANDARD_CANDIDATE','PUBLIC_DOCTRINE_CANDIDATE','COPYRIGHT_LICENSED_CANDIDATE','TRADE_SECRET_CANDIDATE_CONTROLLED','PATENT_CANDIDATE_HOLD','RESTRICTED_INSTITUTIONAL'}: return hold('IP_CLASSIFICATION_REQUIRED')
    return pass_candidate('FRAMEWORK_ASSET_CANDIDATE_PREPARED','no title, patentability, value, certification or commerce authority created')

def chlom_rights_bridge(event):
    if not isinstance(event,dict) or not public_safe(event): return hold('INVALID_OR_PROTECTED_CHLOM_EVENT')
    if event.get('rights_authority')!='CHLOM': return hold('CHLOM_AUTHORITY_REQUIRED')
    if event.get('rights_decision') not in {'PASS','HOLD','FAIL'}: return hold('RIGHTS_DECISION_REQUIRED')
    if not exact_digest(event.get('decision_digest')): return hold('RIGHTS_DECISION_DIGEST_REQUIRED')
    if event.get('body_in_public_envelope') is not False: return hold('PRIVATE_RIGHTS_BODY_PROHIBITED')
    if event.get('rights_decision')=='PASS': return pass_candidate('CHLOM_RIGHTS_REFERENCE_ACCEPTED','rights remain granted only by CHLOM')
    return hold('CHLOM_RIGHTS_'+event['rights_decision'])

def thriveevergreen_gate(candidate):
    if not isinstance(candidate,dict) or not public_safe(candidate): return hold('INVALID_OR_PROTECTED_COMMERCE_CANDIDATE')
    if candidate.get('commerce_authority')!='THRIVEEVERGREEN': return hold('THRIVEEVERGREEN_AUTHORITY_REQUIRED')
    required={'offer_id','asset_id','title_state','chlom_rights_state','ip_publication_state','release_state','commercial_proof_stage','commercial_proof_required','minimum_commercial_stage','exact_offer_digest'}
    missing=sorted(required-set(candidate))
    if missing: return hold('COMMERCE_GATE_FIELD_MISSING',*missing)
    if not exact_digest(candidate['exact_offer_digest']): return hold('EXACT_OFFER_DIGEST_REQUIRED')
    if candidate.get('title_state')!='VERIFIED_CHAIN_OF_TITLE': return hold('CHAIN_OF_TITLE_NOT_VERIFIED')
    if candidate.get('chlom_rights_state')!='PASS': return hold('CHLOM_RIGHTS_NOT_PASS')
    if candidate.get('ip_publication_state') not in {'PUBLIC_SAFE_ACCEPTED','PRIVATE_MANAGED_SERVICE_ACCEPTED','COPYRIGHT_LICENSED_ACCEPTED'}: return hold('IP_PUBLICATION_NOT_ACCEPTED')
    if candidate.get('release_state') not in {'PASS','ACCEPTED_EXCEPTION','NOT_APPLICABLE'}: return hold('RELEASE_EVIDENCE_NOT_ACCEPTED')
    if candidate.get('commercial_proof_required') is True:
        stage=candidate.get('commercial_proof_stage'); minimum=candidate.get('minimum_commercial_stage')
        if stage not in STAGE_ORDER or minimum not in STAGE_ORDER or STAGE_ORDER[stage]<STAGE_ORDER[minimum]: return hold('COMMERCIAL_PROOF_THRESHOLD_NOT_MET')
    if any(candidate.get(k) is True for k in ('create_price','create_checkout','create_entitlement','create_ecac')): return hold('ACTIVATION_SIDE_EFFECT_PROHIBITED')
    return pass_candidate('ELIGIBLE_FOR_THRIVEEVERGREEN_REVIEW','not ECAC; no price, checkout or entitlement created')

def repository_federation_evidence(event):
    if not isinstance(event,dict) or not public_safe(event): return hold('INVALID_OR_PROTECTED_FEDERATION_EVENT')
    if event.get('non_voting') is not True or event.get('sovereign_voter') is True: return hold('FEDERATION_IDENTITY_VOTING_COLLISION')
    if event.get('sync_agents_requested') is True: return hold('SYNC_AGENTS_NOT_AUTHORIZED')
    if event.get('oidc_verified') is not True: return hold('OIDC_REQUIRED')
    if not exact_head(event.get('source_head')) or not exact_digest(event.get('contract_digest')): return hold('EXACT_FEDERATION_BINDING_REQUIRED')
    return pass_candidate('FEDERATION_EVIDENCE_REFERENCE_ACCEPTED','not certification or sovereign receipt')

def validate_bundle(bundle):
    errors=[]; agent=bundle.get('agent',{}); fs=bundle.get('five_systems',{}); offers=bundle.get('commercial_offers',{}); release=bundle.get('release_evidence',{}); wiring=bundle.get('wiring',{})
    if bundle.get('lifecycle')!='PREPARED_NOT_ACTIVATED': errors.append('lifecycle_drift')
    if bundle.get('sovereign_vote_created') is not False or bundle.get('commercial_activation') is not False: errors.append('authority_or_commercial_drift')
    if bundle.get('database_migration_applied') is not False or bundle.get('mintlify_navigation_applied') is not False: errors.append('provider_or_docs_activation_drift')
    if agent.get('non_voting') is not True or agent.get('D3_allowed') is not False or agent.get('may_independently_verify_C_originated_work') is not False: errors.append('agent_authority_drift')
    if fs.get('invention_registry',{}).get('asset_count')!=20 or fs.get('invention_registry',{}).get('patentability_conclusions')!=0: errors.append('invention_projection_drift')
    if fs.get('chain_of_title',{}).get('verified_title_count')!=0 or fs.get('chain_of_title',{}).get('commercialization_authority_created') is not False: errors.append('title_overclaim')
    if fs.get('valuation',{}).get('valued_asset_count')!=0 or fs.get('valuation',{}).get('portfolio_value') is not None: errors.append('valuation_overclaim')
    if fs.get('commercial_proof',{}).get('paid_customers')!=0 or fs.get('commercial_proof',{}).get('recognized_revenue')!=0: errors.append('commercial_proof_overclaim')
    if offers.get('checkout') is not False or offers.get('customer_entitlement') is not False or offers.get('stripe_product_or_price') is not None or any(x.get('price') is not None for x in offers.get('offers',[])): errors.append('commerce_activation_drift')
    if release.get('activation_effect') is not False or release.get('certification_effect') is not False or release.get('appraisal_effect') is not False: errors.append('release_authority_drift')
    for name,x in wiring.items():
        if x.get('state') not in {'CANDIDATE_NOT_BOUND','INTAKE_PREPARED_BINDING_PENDING','CANDIDATE_NOT_DEPLOYED'}: errors.append('wiring_state_drift:'+name)
    if not public_safe(bundle): errors.append('protected_field_in_public_bundle')
    return errors

def diligence_gate(bundle):
    errors=validate_bundle(bundle); fs=bundle['five_systems']; blockers=list(errors)
    if fs['invention_registry']['asset_count']>fs['invention_registry']['patentability_conclusions']: blockers.append('inventions_on_documentary_hold')
    if fs['chain_of_title']['hold_count']: blockers.append('chain_of_title_unverified')
    if fs['valuation']['valued_asset_count']<fs['valuation']['asset_count']: blockers.append('valuation_inputs_missing')
    if fs['commercial_proof']['stage'] not in {'P3_PAID_PILOT','P4_RETAINED_OR_RENEWED','P5_RECURRING_AND_EXPANDING'}: blockers.append('commercial_proof_below_paid_pilot')
    release=bundle['release_evidence']
    if release['vulnerability']['current_result'] not in {'PASS_NO_KNOWN_VULNERABILITIES','ACCEPTED_EXCEPTION'}: blockers.append('vulnerability_scan_not_accepted')
    if release['provenance']['signed'] is not True: blockers.append('provenance_unsigned')
    if release['provenance']['independently_verified'] is not True: blockers.append('provenance_not_independently_verified')
    if bundle['publication']['accepted_issue_131_disposition'] is not True: blockers.append('issue_131_not_accepted')
    return {'status':'HOLD' if blockers else 'PASS_FOR_INDEPENDENT_DILIGENCE','blockers':sorted(set(blockers)),'legal_conclusion':False,'appraisal_effect':False,'certification_effect':False,'sovereign_vote_created':False,'provider_or_database_write_effect':False,'commercial_activation_effect':False}

def file_sbom(root:pathlib.Path):
    fs=[p for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.zip'}]
    return [{'type':'file','name':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in fs]

def main():
    p=argparse.ArgumentParser(); p.add_argument('bundle'); p.add_argument('--gate',action='store_true'); a=p.parse_args(); bundle=json.loads(pathlib.Path(a.bundle).read_text()); result=diligence_gate(bundle) if a.gate else {'status':'PASS' if not validate_bundle(bundle) else 'FAIL','errors':validate_bundle(bundle)}; print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result['status']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
