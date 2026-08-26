#!/usr/bin/env python3
"""Qualify the exact Batch 005 Lane A cohort under unchanged Gate 004 standards."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import build_substantive_rebuild_wave1 as wave1
import execute_docs_rebuild_quad_lane_batch as q1
import qualify_wave7_substantive_gate_004 as gate4
BATCH=ROOT/'developers/manifests/docs-rebuild-bulk-quad-lane-batch-005.v1.json'
GATES=[ROOT/'developers/manifests/docs-wave7-adluxe-substantive-gate-001.v1.json',ROOT/'developers/manifests/docs-wave7-adluxe-substantive-gate-002.v1.json',ROOT/'developers/manifests/docs-wave7-melanin-magic-substantive-gate-003.v1.json',ROOT/'developers/manifests/docs-wave7-substantive-gate-004.v1.json']
EXPECTED=['HC-0521','HC-0716']
def load(p:Path)->dict[str,Any]: return json.loads(p.read_text(encoding='utf-8'))
def prior()->set[str]:
    out=set(q1.prior_ids())
    for p in GATES: out.update(str(x) for x in load(p)['qualified_inventory_ids'])
    if len(out)!=76: raise ValueError(f'expected 76 prior qualified, found {len(out)}')
    return out

def build()->dict[str,Any]:
    receipt=load(BATCH); admitted=list(receipt['lane_inventory_ids']['A'])
    if admitted!=EXPECTED: raise ValueError(f'Batch 005 Lane A drift: {admitted}')
    if receipt['official_counts_after_batch']!={'machine_qualified_p0':76,'pending_p0':373}: raise ValueError('unexpected Batch 005 baseline')
    rows={str(r['inventory_id']):r for r in wave1.aggregate_candidate_rows()}; before=prior()
    if before & set(EXPECTED): raise ValueError('Gate 005 overlaps prior qualified records')
    results=[]; selected=[]
    for rid in EXPECTED:
        row=rows[rid]; reasons=[]; flags=list(row.get('flags',[]))
        if row.get('priority')!='P0': reasons.append('not_p0')
        if row.get('disposition_candidate')!='merged_successor': reasons.append('not_merged_successor_candidate')
        if flags: reasons.append('candidate_flags_not_empty')
        if row.get('missing_target_routes'): reasons.append('missing_target_routes')
        if q1.is_high_risk(row): reasons.append('high_risk_semantics')
        successor,observations=gate4.best_successor(row)
        if successor is None: reasons.append('no_substantive_intent_matched_current_successor')
        accepted=not reasons
        if accepted: selected.append(rid)
        results.append({'inventory_id':rid,'article_id':row.get('article_id'),'legacy_section':row.get('legacy_section'),'legacy_subcategory':row.get('legacy_subcategory'),'legacy_title':row.get('legacy_title'),'current_state_candidate':row.get('current_state_candidate'),'target_routes':row.get('target_routes',[]),'candidate_flags':flags,'accepted_successor':successor,'route_observations':observations,'machine_substantive_qualified':accepted,'qualification_state':'QUALIFIED_CURRENT_SUCCESSOR' if accepted else 'HELD','hold_reasons':sorted(set(reasons)),'historical_body_recovered':False,'terminal_disposition_accepted':False,'parent_review_required_for_terminal_disposition':True})
    held=[x for x in EXPECTED if x not in set(selected)]
    d={'schema_version':'1.0.0','gate_id':'ct.docs.rebuild.wave7.substantive-gate-005.v1','source_execution_receipt':BATCH.relative_to(ROOT).as_posix(),'records_evaluated':len(EXPECTED),'records_machine_qualified':len(selected),'qualified_inventory_ids':selected,'held_inventory_ids':held,'results':results,'counting':{'machine_qualified_before':76,'pending_p0_before':373,'machine_qualified_delta':len(selected),'pending_p0_delta':-len(selected),'machine_qualified_after':76+len(selected),'pending_p0_after':373-len(selected)},'guardrails':{'exact_lane_a_identity_required':True,'zero_candidate_flags_required':True,'high_risk_semantics_prohibited':True,'substantive_route_minimum_body_characters':12000,'substantive_route_minimum_internal_links':4,'strong_intent_evidence_required':True,'held_records_count_as_qualified':False,'historical_body_recovery_claimed':False,'terminal_disposition_self_authorized':False,'authority_activation_created':False,'provider_write_expansion_created':False,'phase_3_entry':'blocked_pending_phase_2_99_hard_exit'}}
    d['gate_sha256']=gate4.canonical_hash(d); return d

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path); a=p.parse_args(); d=build()
    print('PASS_WAVE7_SUBSTANTIVE_GATE_005'); print('qualified_inventory_ids='+','.join(d['qualified_inventory_ids'])); print('held_inventory_ids='+','.join(d['held_inventory_ids'])); print(f"records_machine_qualified={d['records_machine_qualified']}"); print(f"machine_qualified_after={d['counting']['machine_qualified_after']}"); print(f"pending_p0_after={d['counting']['pending_p0_after']}"); print('historical_body_recovery_claimed=false'); print('terminal_disposition_self_authorized=false'); print('gate_sha256='+d['gate_sha256'])
    if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print('output='+str(a.output))
if __name__=='__main__': main()
