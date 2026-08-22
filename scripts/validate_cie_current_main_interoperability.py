#!/usr/bin/env python3
"""Validate the current-main CIE interoperability parent packet."""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
M=ROOT/'developers/manifests/cie-current-main-interoperability.v1.json'
CONTRACT=ROOT/'developers/contracts/cie-interoperability-envelope.v1.json'
CHLOM=ROOT/'developers/contracts/cie-chlom-pallet.v1.json'
NEXT=ROOT/'developers/contracts/cie-convergent-handoff.v1.json'
DOC=ROOT/'doctrine/cultural-imprint-engine.mdx'
EXPECTED_MAIN='c7f14b73cff09f00a8f94f15a8587289de18ff7b'
EXPECTED_PUBLIC='e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2'
EXPECTED_INTEROP='36e17747f9dd29a3d9689b93d06fca0a432b4419cee717246a5c6f974b013636'
def fail(m): raise SystemExit('ERROR: '+m)
def load(p):
 v=json.loads(p.read_text())
 if not isinstance(v,dict): fail(f'object required: {p}')
 return v
def main():
 for p in (M,CONTRACT,CHLOM,NEXT,DOC):
  if not p.is_file(): fail(f'missing {p.relative_to(ROOT)}')
 m=load(M)
 f=m.get('framework',{}); child=m.get('child_candidate',{}); ip=m.get('ip_publication',{}); comm=m.get('commercial',{}); gov=m.get('governance',{})
 if m.get('canonical_main_observed')!=EXPECTED_MAIN: fail('canonical main anchor drift')
 if m.get('packet_author_may_self_approve') is not False: fail('C self-approval drift')
 for key in ('operationally_enabled','runtime_integration_allowed','vote_eligible'):
  if f.get(key) is not False: fail(f'framework {key} must remain false')
 if f.get('parent_certification_agent')!='ct.relay.agent-d' or f.get('parent_certification_state')!='pending': fail('Agent D parent certification boundary drift')
 if child.get('governance_state')!='provisioned_unlinked' or child.get('operationally_enabled') is not False or child.get('vote_eligible') is not False: fail('child lifecycle drift')
 if m.get('interoperability',{}).get('cie_public_contract_digest')!=EXPECTED_PUBLIC: fail('public contract digest drift')
 if hashlib.sha256(CONTRACT.read_bytes()).hexdigest()!=EXPECTED_INTEROP: fail('interoperability contract byte digest drift')
 ch=load(CHLOM)
 if ch.get('rights_authority_effect') is not False or ch.get('sovereign_vote_effect') is not False: fail('CHLOM authority drift')
 nx=load(NEXT)
 if nx.get('state')!='RESEARCH_CANDIDATE' or nx.get('implementation_allowed') is not False or nx.get('operational_activation_allowed') is not False: fail('Convergent handoff lock drift')
 if ip.get('public_safe_contracts_only') is not True or any(ip.get(k) is not False for k in ('protected_calibration_public','private_eval_corpus_public','private_runtime_topology_public','credentials_or_fingerprints_public')): fail('IP disclosure boundary drift')
 for k in ('exact_price_authorized','stripe_product_or_price_activation','checkout_enabled','certification_status_active','customer_entitlement_active'):
  if comm.get(k) is not False: fail(f'commercial fail-closed drift: {k}')
 if gov.get('minimum_approvals')!=4 or gov.get('agent_d_mandatory') is not True or gov.get('deny_or_block_stops') is not True: fail('sovereign governance drift')
 if gov.get('sovereign_voters')!=['A','B','C','D','S']: fail('sovereign voter pool drift')
 text='\n'.join(p.read_text() for p in (M,CONTRACT,CHLOM,NEXT,DOC))
 for token in ('sealed_bundle_secret_name','runtime_entrypoint','handler_ref','private_fingerprint_id','private_fingerprint_commitment','SUPABASE_SERVICE_ROLE_KEY','OPENAI_API_KEY'):
  if token in text: fail(f'private topology/secret token prohibited: {token}')
 for pattern in (r'\bgh[pousr]_[A-Za-z0-9]{20,}\b',r'\bgithub_pat_[A-Za-z0-9_]{20,}\b',r'\bsb_secret_[A-Za-z0-9_-]{16,}\b',r'\bsk-[A-Za-z0-9]{20,}\b'):
  if re.search(pattern,text): fail('credential-shaped value detected')
 print('CIE current-main interoperability validator PASS; runtime disabled; child provisioned_unlinked; next framework research-only; commercial candidate-only.')
 return 0
if __name__=='__main__': raise SystemExit(main())
