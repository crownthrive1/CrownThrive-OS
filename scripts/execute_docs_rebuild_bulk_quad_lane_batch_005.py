#!/usr/bin/env python3
"""Execute Wave 7 bulk quad-lane Batch 005 at 16 records per lane.

This increases throughput from 4x4 to 4x16 without changing any admission,
risk, qualification, recovery, or terminal-disposition standard. Batch execution
is evidence only; qualification remains a separate gate.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_substantive_rebuild_wave1 as wave1
import execute_docs_rebuild_quad_lane_batch as q1

BATCHES=[ROOT/f'developers/manifests/docs-rebuild-quad-lane-batch-{n:03d}.v1.json' for n in range(1,5)]
GATES=[
 ROOT/'developers/manifests/docs-wave7-adluxe-substantive-gate-001.v1.json',
 ROOT/'developers/manifests/docs-wave7-adluxe-substantive-gate-002.v1.json',
 ROOT/'developers/manifests/docs-wave7-melanin-magic-substantive-gate-003.v1.json',
 ROOT/'developers/manifests/docs-wave7-substantive-gate-004.v1.json',
]
PER_LANE=16


def load(path:Path)->dict[str,Any]: return json.loads(path.read_text(encoding='utf-8'))

def touched()->set[str]:
    out=set()
    for path in BATCHES:
        receipt=load(path)
        for ids in receipt['lane_inventory_ids'].values(): out.update(str(x) for x in ids)
    if len(out)!=64: raise ValueError(f'expected 64 unique identities touched in Batches 001-004, found {len(out)}')
    return out

def qualified()->set[str]:
    out=set(q1.prior_ids())
    for path in GATES: out.update(str(x) for x in load(path)['qualified_inventory_ids'])
    if len(out)!=76: raise ValueError(f'expected 76 machine-qualified records before Batch 005, found {len(out)}')
    return out

def build()->dict[str,Any]:
    rows=wave1.aggregate_candidate_rows()
    if len(rows)!=795: raise ValueError('source universe must remain 795')
    q=qualified(); old=touched()
    pending=[r for r in rows if r.get('priority')=='P0' and str(r['inventory_id']) not in q]
    pending.sort(key=lambda r:str(r['inventory_id']))
    if len(pending)!=373: raise ValueError(f'expected 373 pending P0 records, found {len(pending)}')

    original=q1.BATCH_SIZE_PER_LANE
    q1.BATCH_SIZE_PER_LANE=PER_LANE
    try:
        used=set(old); lanes={}
        for lane,chooser in [('A',q1.lane_a_candidates),('B',q1.lane_b_candidates),('C',q1.lane_c_candidates),('D',q1.lane_d_candidates)]:
            selected=chooser(pending,used)
            if len(selected)!=PER_LANE: raise ValueError(f'lane {lane} selected {len(selected)} not {PER_LANE}')
            ids={str(r['inventory_id']) for r in selected}
            if ids & used: raise ValueError(f'lane {lane} overlaps an existing operation lease')
            used|=ids; lanes[lane]=selected
    finally:
        q1.BATCH_SIZE_PER_LANE=original

    current={str(r['inventory_id']) for values in lanes.values() for r in values}
    if len(current)!=64: raise ValueError('Batch 005 must touch exactly 64 new unique identities')
    if current & old: raise ValueError('Batch 005 reuses a prior touched identity')
    if current & q: raise ValueError('Batch 005 touches an already-qualified identity')
    if any(r.get('flags') for r in lanes['A']): raise ValueError('Lane A requires zero flags')
    if any(q1.is_high_risk(r) for r in lanes['A']): raise ValueError('Lane A contains high-risk semantics')

    payload={
      'schema_version':'1.0.0','execution_id':'ct.docs.rebuild.wave7.bulk-quad-lane.batch-005',
      'source_universe_count':795,'p0_candidate_estate':449,
      'machine_qualified_before_batch':76,'remaining_p0_before_batch':373,
      'previous_batches_touched_count':64,'previous_batches_touched_ids':sorted(old),
      'parallel_lane_count':4,'records_per_lane':PER_LANE,'unique_records_touched':64,
      'lanes':lanes,
      'counting':{'machine_qualified_delta':0,'remaining_p0_delta':0,'official_machine_qualified_after_batch':76,'official_remaining_p0_after_batch':373,'reason':'bulk execution creates governed work receipts only; qualification requires a separate substantive gate'},
      'guardrails':{'batch_001_004_identity_reuse':False,'already_qualified_identity_reuse':False,'unique_operation_leases':True,'lane_a_requires_zero_flags':True,'lane_a_high_risk_semantics_prohibited':True,'quality_thresholds_unchanged':True,'historical_body_recovery_fabricated':False,'terminal_disposition_self_authorized':False,'specialist_authority_promoted':False,'parent_review_required':True,'phase_3_entry':'blocked_pending_phase_2_99_hard_exit'}
    }
    payload['execution_sha256']=q1.canonical_hash(payload)
    return payload

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path); a=p.parse_args(); d=build()
    print('PASS_DOCS_REBUILD_BULK_QUAD_LANE_BATCH_005')
    for lane in 'ABCD': print(f'lane_{lane}_inventory_ids='+','.join(r['inventory_id'] for r in d['lanes'][lane]))
    print('unique_records_touched=64'); print('official_machine_qualified_after_batch=76'); print('official_remaining_p0_after_batch=373'); print('terminal_disposition_self_authorized=false'); print('execution_sha256='+d['execution_sha256'])
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print('output='+str(a.output))
if __name__=='__main__': main()
