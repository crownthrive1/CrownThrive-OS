#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Mapping
ROOT=Path(__file__).resolve().parents[1]
REGISTRY_PATH=ROOT/'contracts/chlom/economics/penta-protocol-registry.v1.json'
RUNTIME_CONTROL_PATH=ROOT/'config/penta_runtime_control.json'
REQUIRED_FLOW=('OracleCookie','CHLOM','PentaMeter','PentaGas','PentaMarket','SmartTreasury','PentaPay','PentaCost','DAIL','PentaRelease')
class ProtocolValidationError(RuntimeError): pass
def _load(path:Path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError) as exc:raise ProtocolValidationError(f'invalid or missing protocol artifact: {path}: {exc}') from exc
def load_registry():return _load(REGISTRY_PATH)
def validate_suite():
    r=load_registry(); errors=[]; defs=r.get('protocols',{})
    if r.get('state')!='ACTIVE':errors.append('registry is not ACTIVE')
    if r.get('default_enforcement')!='fail_closed':errors.append('registry is not fail_closed')
    if tuple(r.get('ordered_economic_flow',()))!=REQUIRED_FLOW:errors.append('ordered flow mismatch')
    runtime=_load(RUNTIME_CONTROL_PATH).get('pentas',{})
    for name in REQUIRED_FLOW:
        spec=defs.get(name)
        if not isinstance(spec,dict):errors.append(f'{name}: missing registry entry');continue
        if spec.get('state')!='active':errors.append(f'{name}: registry not active')
        try:c=_load(ROOT/spec['contract'])
        except (ProtocolValidationError,KeyError) as exc:errors.append(f'{name}: {exc}');continue
        if c.get('name')!=name or c.get('protocol_id')!=spec.get('id'):errors.append(f'{name}: contract identity mismatch')
        if c.get('state')!='ACTIVE' or c.get('enforcement')!='fail_closed':errors.append(f'{name}: contract not active/fail_closed')
        if c.get('provider_mutation_policy')!='authoritative_readback_required':errors.append(f'{name}: readback policy mismatch')
        for dep in c.get('depends_on',[]):
            if dep not in defs:errors.append(f'{name}: unknown dependency {dep}')
        if runtime.get(name,{}).get('state')!='active':errors.append(f'{name}: runtime not active')
    a=r.get('activation',{})
    if a.get('external_money_movement')!='gated':errors.append('money movement must remain gated')
    if a.get('provider_mutation')!='authoritative_readback_required':errors.append('provider mutation must require readback')
    return {'schema':'ct.penta.protocol-validation-result.v1','ok':not errors,'required_protocol_count':len(REQUIRED_FLOW),'active_protocols':[n for n in REQUIRED_FLOW if defs.get(n,{}).get('state')=='active'],'errors':errors}
def _decimal(v,field):
    try:d=Decimal(str(v))
    except (InvalidOperation,ValueError,TypeError) as exc:raise ProtocolValidationError(f'{field} invalid') from exc
    if not d.is_finite() or d<0:raise ProtocolValidationError(f'{field} must be finite and non-negative')
    return d
def evaluate(p:Mapping[str,Any]):
    v=validate_suite()
    if not v['ok']:raise ProtocolValidationError('; '.join(v['errors']))
    missing=[k for k in ('cookie_id','node_did','workload_id','release_id','operation') if not p.get(k)]
    if missing:raise ProtocolValidationError('missing required fields: '+', '.join(missing))
    meter=_decimal(p.get('meter_units'),'meter_units'); gas=(meter*_decimal(p.get('gas_per_unit'),'gas_per_unit')).quantize(Decimal('0.000001'),rounding=ROUND_HALF_EVEN); price=(gas*_decimal(p.get('rate_per_gas'),'rate_per_gas')).quantize(Decimal('0.000001'),rounding=ROUND_HALF_EVEN)
    core={'cookie_id':p['cookie_id'],'node_did':p['node_did'],'workload_id':p['workload_id'],'release_id':p['release_id'],'operation':p['operation'],'meter_units':str(meter),'gas_units':str(gas),'atomic_price':str(price),'rate_card_version':p.get('rate_card_version','not_available')}
    evidence='sha256:'+hashlib.sha256(json.dumps(core,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    settlement=p.get('provider_authorized') is True and p.get('provider_readback') is True; dail=settlement and bool(p.get('previous_hash')); release=dail and p.get('dail_readback') is True and p.get('governance_pass') is True
    return {'schema':'ct.penta.protocol-evaluation.v1','protocol_state':'ACTIVE','evidence_hash':evidence,'meter':{'units':str(meter)},'gas':{'units':str(gas)},'pay':{'atomic_price':str(price),'currency':p.get('currency','USD'),'execution':'authorized' if settlement else 'gated'},'cost':{'aggregate_actual':str(price),'status':'computed'},'dail':{'append':'ready' if dail else 'gated','readback':'verified' if p.get('dail_readback') is True else 'not_available'},'release':{'decision':'PASS' if release else 'HOLD','provider_side_effects_performed':False},'hard_boundaries':{'money_movement_performed':False,'provider_mutation_performed':False,'authoritative_readback_required':True}}
def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True);sub.add_parser('status');sub.add_parser('validate');ep=sub.add_parser('evaluate');ep.add_argument('--payload',required=True);a=ap.parse_args()
    try:
        if a.cmd in {'status','validate'}:out=validate_suite();out['activation']=load_registry().get('activation',{}) if a.cmd=='status' else out.get('activation')
        else:
            raw=Path(a.payload[1:]).read_text() if a.payload.startswith('@') else a.payload;out=evaluate(json.loads(raw))
    except (ProtocolValidationError,json.JSONDecodeError,OSError) as exc:print(json.dumps({'ok':False,'error':str(exc)}));return 2
    print(json.dumps(out,indent=2,sort_keys=True));return 0 if out.get('ok',True) else 1
if __name__=='__main__':raise SystemExit(main())
