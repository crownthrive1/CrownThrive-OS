#!/usr/bin/env python3
"""CHLOM Agent Wallet v2: fail-closed policy, intent, ECAC, receipt and outbox runtime."""
from __future__ import annotations
import argparse, datetime as dt, fcntl, hashlib, json, os, pathlib, re, subprocess, tempfile

POLICY_SCHEMA="ct.chlom-agent-wallet-policy.v2"
INTENT_SCHEMA="ct.protocol.chlom-agent-wallet.intent.v1"
AUTH_SCHEMA="ct.protocol.chlom-agent-wallet.authorization.v1"
RECEIPT_SCHEMA="ct.protocol.chlom-agent-wallet.receipt.v1"
EVENT_SCHEMA="ct.event.chlom-agent-wallet.v1"
RISK={"D0":0,"D1":1,"D2":2,"D3":3}
OPS={"OBSERVE","SIMULATE_TRANSFER","TRANSFER_ERC20"}
ADDR=re.compile(r"^0x[a-fA-F0-9]{40}$")
ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")


def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def digest(v): return hashlib.sha256(canonical(v)).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")
def load(path):
    with open(path,encoding="utf-8") as f: v=json.load(f)
    if not isinstance(v,dict): raise ValueError("JSON root must be object")
    return v

def parse_time(v):
    if v.endswith("Z"): v=v[:-1]+"+00:00"
    t=dt.datetime.fromisoformat(v)
    if t.tzinfo is None: raise ValueError("timezone required")
    return t.astimezone(dt.timezone.utc)

def add(reasons, condition, code):
    if not condition: reasons.append(code)

def atomic(path,value):
    path=pathlib.Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix="."+path.name+".",dir=path.parent,text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(value,f,sort_keys=True,separators=(",",":")); f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp,0o600); os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def validate_policy(p):
    r=[]; a=p.get("authority",{}); e=p.get("execution",{}); c=p.get("continuity_boundary",{}); b=c.get("current_certified_boundary",{}); caps=p.get("capabilities",{}); chain=p.get("primary_chain",{}); asset=p.get("primary_asset",{}); custody=p.get("custody",{})
    add(r,p.get("schema")==POLICY_SCHEMA,"POLICY_SCHEMA_MISMATCH")
    add(r,p.get("environment")=="production","POLICY_ENVIRONMENT_NOT_PRODUCTION")
    add(r,chain.get("namespace")=="eip155" and chain.get("chain_id")==8453 and str(chain.get("name","")).lower()=="base","BASE_MAINNET_REQUIRED")
    add(r,asset.get("symbol")=="USDC" and asset.get("decimals")==6 and str(asset.get("contract","")).lower()=="0x833589fcd6edb6e08f4c7c32d4f71b54bda02913","NATIVE_BASE_USDC_REQUIRED")
    add(r,a.get("exact_ecac_required") is True,"EXACT_ECAC_NOT_REQUIRED")
    add(r,a.get("provider_success_manufactures_authority") is False,"PROVIDER_SUCCESS_AUTHORITY_UNSAFE")
    add(r,a.get("authority_ceiling") in RISK,"AUTHORITY_CEILING_INVALID")
    add(r,a.get("d3_human_reserved") is True,"D3_NOT_HUMAN_RESERVED")
    add(r,int(e.get("max_unattended_value_minor",-1))==0,"UNATTENDED_VALUE_MUST_BE_ZERO")
    for k in ("transaction_simulation_required","read_after_write_required","idempotency_required","rollback_or_compensation_required"):
        add(r,e.get(k) is True,k.upper()+"_MUST_BE_TRUE")
    for k in ("private_key_input_allowed","signer_material_export_allowed"):
        add(r,e.get(k) is False,k.upper()+"_MUST_BE_FALSE")
    add(r,c.get("profile_id")=="ct.pack.chlom-wallet.continuity-interfaces.v2","CONTINUITY_PROFILE_MISMATCH")
    add(r,c.get("state")=="PRODUCTION_PRIVATE_CONTROL_PLANE_CERTIFIED","CONTINUITY_STATE_MISMATCH")
    for k in ("provider_write","money_movement","rights_grant","chain_broadcast","credential_material_returned","destructive_recovery","authority_manufacture","ai_final_authority"):
        add(r,b.get(k) is False,"CERTIFIED_BOUNDARY_"+k.upper()+"_MUST_BE_FALSE")
    for k in ("provider_write","money_movement","chain_broadcast"):
        if b.get(k) is False: add(r,caps.get(k) is False,("POLICY_EXCEEDS_CERTIFIED_MONEY_BOUNDARY" if k=="money_movement" else "POLICY_EXCEEDS_CERTIFIED_"+k.upper()+"_BOUNDARY"))
    for k in ("private_key_export_allowed","mnemonic_export_allowed","supabase_private_key_storage_allowed"):
        add(r,custody.get(k) is False,k.upper()+"_MUST_BE_FALSE")
    return sorted(set(r))

def validate_intent(p,i):
    r=[]; op=i.get("operation"); risk=i.get("risk_class"); amount=i.get("amount_minor"); dest=i.get("destination"); pc=p["primary_chain"]; pa=p["primary_asset"]
    add(r,i.get("schema")==INTENT_SCHEMA,"INTENT_SCHEMA_MISMATCH")
    for k in ("intent_id","idempotency_key"): add(r,isinstance(i.get(k),str) and bool(ID.fullmatch(i.get(k,""))),k.upper()+"_INVALID")
    add(r,op in OPS,"OPERATION_INVALID"); add(r,risk in RISK,"RISK_CLASS_INVALID")
    if risk in RISK and p["authority"]["authority_ceiling"] in RISK: add(r,RISK[risk]<=RISK[p["authority"]["authority_ceiling"]],"AUTHORITY_CEILING_EXCEEDED")
    if risk=="D3": r.append("D3_HUMAN_RESERVED")
    add(r,i.get("chain",{}).get("namespace")==pc["namespace"] and i.get("chain",{}).get("chain_id")==pc["chain_id"],"INTENT_CHAIN_MISMATCH")
    ia=i.get("asset",{}); add(r,ia.get("symbol")==pa["symbol"] and str(ia.get("contract","")).lower()==pa["contract"].lower() and ia.get("decimals")==pa["decimals"],"INTENT_ASSET_MISMATCH")
    add(r,isinstance(amount,int) and not isinstance(amount,bool) and amount>=0,"AMOUNT_MINOR_INVALID")
    if op in {"SIMULATE_TRANSFER","TRANSFER_ERC20"}:
        add(r,isinstance(dest,str) and bool(ADDR.fullmatch(dest or "")),"DESTINATION_INVALID")
        allowed={str(x).lower() for x in p["allowlists"]["destination_addresses"]}
        if isinstance(dest,str) and ADDR.fullmatch(dest): add(r,dest.lower() in allowed,"DESTINATION_NOT_ALLOWLISTED")
        add(r,isinstance(amount,int) and amount>0,"TRANSFER_AMOUNT_MUST_BE_POSITIVE"); add(r,bool(i.get("compensation_ref")),"COMPENSATION_REF_REQUIRED")
    elif op=="OBSERVE": add(r,amount==0,"OBSERVE_AMOUNT_MUST_BE_ZERO"); add(r,dest in (None,""),"OBSERVE_DESTINATION_MUST_BE_EMPTY")
    if risk=="D2" and isinstance(amount,int): add(r,amount<=int(p["limits"]["max_d2_value_minor"]),"D2_VALUE_LIMIT_EXCEEDED")
    try:
        created=parse_time(i.get("created_at","")); expires=parse_time(i.get("expires_at","")); add(r,expires>created,"INTENT_EXPIRY_INVALID"); add(r,expires>dt.datetime.now(dt.timezone.utc),"INTENT_EXPIRED")
    except Exception: r.append("INTENT_TIMESTAMP_INVALID")
    return sorted(set(r))

def validate_auth(p,i,a):
    if i.get("operation")!="TRANSFER_ERC20": return []
    if not a: return ["EXACT_ECAC_AUTHORIZATION_REQUIRED"]
    r=[]; scope=a.get("scope",{})
    add(r,a.get("schema")==AUTH_SCHEMA,"AUTH_SCHEMA_MISMATCH"); add(r,a.get("decision")=="ECAC","AUTH_DECISION_NOT_ECAC")
    add(r,a.get("intent_sha256")==digest(i),"AUTH_INTENT_HASH_MISMATCH"); add(r,a.get("policy_sha256")==digest(p),"AUTH_POLICY_HASH_MISMATCH")
    add(r,scope.get("money_movement") is True,"AUTH_SCOPE_MONEY_MOVEMENT_NOT_GRANTED"); add(r,scope.get("chain_broadcast") is True,"AUTH_SCOPE_CHAIN_BROADCAST_NOT_GRANTED"); add(r,scope.get("signer_key_material_release") is False,"AUTH_SIGNER_KEY_RELEASE_UNSAFE")
    try:
        issued=parse_time(a.get("issued_at","")); expires=parse_time(a.get("expires_at","")); n=dt.datetime.now(dt.timezone.utc); add(r,issued<=n<expires,"AUTHORIZATION_NOT_CURRENT")
    except Exception: r.append("AUTHORIZATION_TIMESTAMP_INVALID")
    return sorted(set(r))

def evaluate(p,i,a=None):
    r=validate_policy(p)+validate_intent(p,i)+validate_auth(p,i,a); op=i.get("operation"); caps=p.get("capabilities",{})
    if op=="TRANSFER_ERC20":
        if caps.get("money_movement") is not True: r.append("POLICY_MONEY_MOVEMENT_DISABLED")
        if caps.get("chain_broadcast") is not True: r.append("POLICY_CHAIN_BROADCAST_DISABLED")
    if op=="SIMULATE_TRANSFER" and caps.get("simulation") is not True: r.append("POLICY_SIMULATION_DISABLED")
    r=sorted(set(r)); decision="HOLD" if r else ("ECAC" if op=="TRANSFER_ERC20" else "PASS")
    return {"schema":"ct.protocol.chlom-agent-wallet.decision.v1","decision":decision,"operation":op,"intent_id":i.get("intent_id"),"intent_sha256":digest(i),"policy_id":p.get("policy_id"),"policy_sha256":digest(p),"continuity_profile_id":p.get("continuity_boundary",{}).get("profile_id"),"capabilities":caps,"reasons":r,"evaluated_at":now()}

def adapter(path,verb,payload):
    if not path or not os.path.isabs(path) or not os.path.isfile(path) or not os.access(path,os.X_OK): raise RuntimeError("adapter must be an absolute executable file")
    x=subprocess.run([path,verb],input=canonical(payload),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
    if x.returncode: raise RuntimeError("adapter failed; stderr_sha256="+hashlib.sha256(x.stderr).hexdigest())
    v=json.loads(x.stdout); add([],isinstance(v,dict),"ADAPTER_RESPONSE_INVALID")
    if not isinstance(v,dict): raise RuntimeError("adapter response must be object")
    return v

def append_event(path,receipt):
    path=pathlib.Path(path); path.parent.mkdir(parents=True,exist_ok=True); lock=path.with_suffix(path.suffix+".lock")
    with open(lock,"a+") as lf:
        fcntl.flock(lf.fileno(),fcntl.LOCK_EX); previous="0"*64
        if path.exists():
            lines=[x for x in path.read_bytes().splitlines() if x.strip()]
            if lines: previous=json.loads(lines[-1])["event_sha256"]
        ev={"schema":EVENT_SCHEMA,"event_id":"evt:"+receipt["receipt_id"],"event_type":"CHLOM_AGENT_WALLET_"+receipt["status"],"source":"chlom-agent-wallet","subject":receipt["intent_id"],"occurred_at":now(),"receipt_sha256":receipt["receipt_sha256"],"previous_event_sha256":previous,"delivery":{"mode":"append_only_outbox","dail_eligible":True,"remote_delivery_claimed":False,"penta_routes":["PentaStatus","PentaCertify","PentaTriage","CHLOM"]}}
        ev["event_sha256"]=digest(ev)
        with open(path,"ab") as f: f.write(canonical(ev)+b"\n"); f.flush(); os.fsync(f.fileno())
        os.chmod(path,0o600); return ev

def execute(p,i,a,state,evidence,adapter_path=None):
    state=pathlib.Path(state); evidence=pathlib.Path(evidence); state.mkdir(parents=True,exist_ok=True); evidence.mkdir(parents=True,exist_ok=True); os.chmod(state,0o700); os.chmod(evidence,0o700)
    d=evaluate(p,i,a); iid=str(i.get("intent_id") or "invalid"); safe=re.sub(r"[^A-Za-z0-9._:-]","_",iid)[:128]; key=str(i.get("idempotency_key") or "invalid"); ledger_path=state/"idempotency.json"
    with open(state/"execution.lock","a+") as lf:
        fcntl.flock(lf.fileno(),fcntl.LOCK_EX); ledger=load(ledger_path) if ledger_path.exists() else {}
        if key in ledger:
            prior=load(evidence/ledger[key]["receipt_file"]); prior["idempotent_replay"]=True; return prior,0 if prior["status"] in {"OBSERVED","SIMULATED","CONFIRMED"} else 3
        status="HOLD"; ex={"adapter_invoked":False}; code=3
        if d["decision"] in {"PASS","ECAC"}:
            if i["operation"]=="OBSERVE": status="OBSERVED"; code=0
            elif i["operation"]=="SIMULATE_TRANSFER":
                if adapter_path:
                    sim=adapter(adapter_path,"simulate",{"intent":i,"policy_sha256":digest(p)}); ex={"adapter_invoked":True,"simulation":sim}; status="SIMULATED" if sim.get("ok") is True else "HOLD"; code=0 if status=="SIMULATED" else 3
                else: d["reasons"].append("EXECUTION_ADAPTER_NOT_CONFIGURED")
            elif i["operation"]=="TRANSFER_ERC20":
                if not adapter_path: d["reasons"].append("EXECUTION_ADAPTER_NOT_CONFIGURED")
                else:
                    sim=adapter(adapter_path,"simulate",{"intent":i,"policy_sha256":digest(p)})
                    if sim.get("ok") is not True: d["reasons"].append("SIMULATION_FAILED")
                    else:
                        sent=adapter(adapter_path,"broadcast",{"intent":i,"authorization":a,"simulation":sim}); tx=sent.get("tx_hash","")
                        if not re.fullmatch(r"0x[a-fA-F0-9]{64}",tx): raise RuntimeError("invalid tx_hash")
                        rb=adapter(adapter_path,"readback",{"intent":i,"tx_hash":tx}); ex={"adapter_invoked":True,"simulation":sim,"broadcast":sent,"read_after_write":rb}; status="CONFIRMED" if rb.get("confirmed") is True else "BROADCAST_UNCONFIRMED"; code=0 if status=="CONFIRMED" else 4
        d["reasons"]=sorted(set(d["reasons"])); receipt={"schema":RECEIPT_SCHEMA,"receipt_id":f"rcpt:{safe}:{digest(i)[:16]}","intent_id":iid,"idempotency_key":key,"status":status,"decision":d,"authorization_id":a.get("authorization_id") if a else None,"execution":ex,"signer_material_exported":False,"created_at":now(),"idempotent_replay":False}; receipt["receipt_sha256"]=digest(receipt); name=f"{safe}.{receipt['receipt_sha256'][:16]}.receipt.json"
        atomic(evidence/name,receipt); ledger[key]={"receipt_file":name,"receipt_sha256":receipt["receipt_sha256"],"status":status}; atomic(ledger_path,ledger); ev=append_event(state/"outbox/events.ndjson",receipt); receipt["event_sha256"]=ev["event_sha256"]; atomic(evidence/name,receipt); return receipt,code

def preflight(p,chain,asset,amount,dest):
    r=validate_policy(p)
    if chain.lower()!=p["primary_chain"]["name"]: r.append("CHAIN_NOT_ALLOWLISTED")
    if asset.upper()!=p["primary_asset"]["symbol"]: r.append("ASSET_NOT_ALLOWLISTED")
    if amount<0:r.append("NEGATIVE_AMOUNT")
    if amount>int(p["execution"]["max_unattended_value_minor"]):r.append("UNATTENDED_LIMIT_EXCEEDED")
    if dest and not ADDR.fullmatch(dest):r.append("DESTINATION_INVALID")
    if dest and ADDR.fullmatch(dest) and dest.lower() not in {x.lower() for x in p["allowlists"]["destination_addresses"]}:r.append("DESTINATION_NOT_ALLOWLISTED")
    if amount>0:
        if not p["capabilities"]["money_movement"]:r.append("POLICY_MONEY_MOVEMENT_DISABLED")
        if not p["capabilities"]["chain_broadcast"]:r.append("POLICY_CHAIN_BROADCAST_DISABLED")
    r=sorted(set(r)); return {"schema":"ct.chlom-agent-wallet-preflight.v2","decision":"PASS" if not r else "HOLD","chain":chain.lower(),"asset":asset.upper(),"amount_minor":amount,"destination":dest or None,"capabilities":p["capabilities"],"exact_ecac_required":p["authority"]["exact_ecac_required"],"max_unattended_value_minor":p["execution"]["max_unattended_value_minor"],"continuity_profile_id":p["continuity_boundary"]["profile_id"],"reasons":r}

legacy_preflight=preflight

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    q=sub.add_parser("validate-policy");q.add_argument("--policy",required=True)
    q=sub.add_parser("preflight");q.add_argument("--policy",required=True);q.add_argument("--chain",default="base");q.add_argument("--asset",default="USDC");q.add_argument("--amount-minor",type=int,default=0);q.add_argument("--destination",default="")
    for name in ("evaluate","execute"):
        q=sub.add_parser(name);q.add_argument("--policy",required=True);q.add_argument("--intent",required=True);q.add_argument("--authorization")
        if name=="execute":q.add_argument("--state-dir",required=True);q.add_argument("--evidence-dir",required=True);q.add_argument("--adapter")
    x=ap.parse_args()
    try:
        p=load(x.policy)
        if x.cmd=="validate-policy":
            r=validate_policy(p); out={"schema":"ct.chlom-agent-wallet-policy-validation.v1","decision":"PASS" if not r else "HOLD","policy_id":p.get("policy_id"),"policy_sha256":digest(p),"reasons":r}; code=0 if not r else 3
        elif x.cmd=="preflight": out=preflight(p,x.chain,x.asset,x.amount_minor,x.destination); code=0 if out["decision"]=="PASS" else 3
        else:
            i=load(x.intent); a=load(x.authorization) if x.authorization else None
            if x.cmd=="evaluate": out=evaluate(p,i,a); code=0 if out["decision"] in {"PASS","ECAC"} else 3
            else: out,code=execute(p,i,a,x.state_dir,x.evidence_dir,x.adapter)
    except Exception as exc:
        out={"schema":"ct.chlom-agent-wallet-error.v1","decision":"HOLD","reason":"PROTOCOL_ENGINE_ERROR","error_type":type(exc).__name__,"error_sha256":hashlib.sha256(str(exc).encode()).hexdigest()}; code=70
    print(json.dumps(out,sort_keys=True,separators=(",",":"))); raise SystemExit(code)

if __name__=="__main__": main()
