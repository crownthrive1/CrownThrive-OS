#!/usr/bin/env python3
"""Build/validate CrownThrive machine-trigger assets, plugins, Vault bindings and factory intake."""

from __future__ import annotations
import argparse, copy, hashlib, json, tempfile
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"developers/manifests/machine-trigger-asset-fabric.v1.json"

def cb(v:Any)->bytes:
    return (json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def hj(v:Any)->str: return hashlib.sha256(cb(v)).hexdigest()
def load(p:Path)->dict: return json.loads(p.read_text(encoding="utf-8"))
def rows(d:dict)->list[dict]:
    f=d["fields"]
    return [dict(zip(f,x)) for x in d["triggers"]]
def asset_id(tid:str)->str: return f"ct.trigger.{tid}.v1"
def derivatives(tid:str)->dict:
    return {
      "algorithm":f"ct.algorithm.trigger.{tid}.v1",
      "skill":f"ct.skill.trigger.{tid}.v1",
      "prompt":f"ct.prompt.trigger.{tid}.v1",
      "script":f"ct.script.trigger.{tid}.v1",
    }

def validate(d:dict)->None:
    if d.get("fabric")!="ct.fabric.machine-trigger-assets.v1": raise AssertionError("fabric_id")
    expected=d.get("sha256"); c=copy.deepcopy(d); c.pop("sha256",None)
    if expected!=hj(c): raise AssertionError("manifest_sha256")
    r=rows(d)
    if len(r)!=32 or len({x["id"] for x in r})!=32: raise AssertionError("trigger_identity")
    if d["estate"]!={"authoritative_assets":100800,"trigger_bundles":32,"derivative_candidates":128,"authoritative_delta":0,"generation":"UNASSIGNED_PENDING_GOVERNED_FACTORY_INTAKE"}:
        raise AssertionError("estate_boundary")
    defs=d["defaults"]
    for k,v in {"authority":"D2","vote":False,"quorum":False,"self_approval":False,"provider_write":False,"production_activation":False,"economic_activation":False,"inherit_pass":False,"unknown_permission":False}.items():
        if defs.get(k)!=v: raise AssertionError(f"default:{k}")
    rules=d["rules"]
    if not rules["machine_not_sovereign"] or not rules["d3_human_reserved"] or not rules["d_required"] or not rules["ecac_required"] or not rules["provider_evidence_only"]:
        raise AssertionError("governance_rules")
    if rules["scheduled_phase3"] or rules["scheduled_commerce"] or rules["public_secrets"] or rules["public_vault_locator"]:
        raise AssertionError("unsafe_default")
    if len(d["plugins"])!=5 or len({p[0] for p in d["plugins"]})!=5: raise AssertionError("plugin_suite")
    for p in d["plugins"]:
        if not p[0].startswith("ct.plugin."): raise AssertionError("plugin_id")
    v=d["vault"]
    if v["binding_count"]!=32 or v["state"]!="PENDING_RUNTIME_BINDING" or not v["opaque_only"] or v["raw_secret_return"] or not v["exact_sha_readback"] or not v["restore_required"]:
        raise AssertionError("vault_boundary")
    plugin_ids={p[0] for p in d["plugins"]}
    for x in r:
        if x["plugin"] not in plugin_ids: raise AssertionError(f"plugin_binding:{x['id']}")
        if x["vault"] not in v["profiles"]: raise AssertionError(f"vault_profile:{x['id']}")
        if x["group"]=="commerce" and not rules["ecac_required"]: raise AssertionError("commerce_ecac")
        if x["id"].startswith("continuity.vault.") and rules["public_vault_locator"]: raise AssertionError("vault_locator")
    p3=next(x for x in r if x["id"]=="phase3.bootstrap.candidate")
    needed={"p299_verdict_GO","bootstrap_permitted_true","authority_quorum_verified","backup_rollback_receipt_verified"}
    if not needed.issubset(set(p3["preconditions"])): raise AssertionError("bootstrap_preconditions")
    pub=next(x for x in r if x["id"]=="commerce.publish.bounded")
    if "valid_non_superseded_ECAC" not in set(pub["preconditions"]): raise AssertionError("ecac_bypass")

def package(d:dict,x:dict)->dict:
    p={
      "v":"1.0.0","package_id":f"ct.trigger-package.{x['id']}.v1","fabric":d["fabric"],
      "asset_id":asset_id(x["id"]),"trigger":x["id"],"group":x["group"],"state":"candidate_hold",
      "authority":"D2","vote":False,"self_approval":False,"plugin":x["plugin"],"vault_profile":x["vault"],
      "event":x["event"],"target":x["target"],"preconditions":x["preconditions"],"independent_gate":x["independent"],
      "derivatives":derivatives(x["id"]),"bindings":d["bind"],"authoritative_delta":0,"generation":d["estate"]["generation"]
    }
    p["sha256"]=hj(p); return p

def build(d:dict,out:Path)->dict:
    validate(d); out.mkdir(parents=True,exist_ok=True)
    ps=[]
    for x in sorted(rows(d),key=lambda z:z["id"]):
        p=package(d,x); (out/(x["id"].replace(".","-")+".json")).write_bytes(cb(p)); ps.append(p)
    plugins=[]
    for pid,purpose in d["plugins"]:
        p={"v":"1.0.0","plugin_id":pid,"purpose":purpose,"state":"candidate_hold","authority":"D2","vote":False,"self_approval":False,"provider_write_default":False,"production_activation_default":False,"economic_activation_default":False}
        p["sha256"]=hj(p); plugins.append(p)
    (out/"plugins.json").write_bytes(cb({"plugins":plugins,"count":len(plugins)}))
    vb={"binding_id":d["vault"]["id"],"state":d["vault"]["state"],"opaque_only":True,"raw_secret_return":False,
        "bindings":[{"asset_id":asset_id(x["id"]),"profile":x["vault"],"runtime_reference":None,"state":"PENDING_RUNTIME_BINDING"} for x in rows(d)]}
    vb["sha256"]=hj(vb); (out/"vault-bindings.json").write_bytes(cb(vb))
    s={"fabric":d["fabric"],"trigger_bundles":len(ps),"derivative_candidates":len(ps)*4,"plugins":len(plugins),"vault_bindings":len(vb["bindings"]),"authoritative_delta":0,"state":{"candidate_hold":len(ps)}}
    s["sha256"]=hj(s); (out/"summary.json").write_bytes(cb(s)); return s

def negative(d:dict)->dict[str,bool]:
    out={}
    bad=copy.deepcopy(d); bad["defaults"]["authority"]="D3"; c=copy.deepcopy(bad); c.pop("sha256",None); bad["sha256"]=hj(c)
    try: validate(bad)
    except AssertionError: out["d3_rejected"]=True
    else: out["d3_rejected"]=False
    bad=copy.deepcopy(d); bad["defaults"]["provider_write"]=True; c=copy.deepcopy(bad); c.pop("sha256",None); bad["sha256"]=hj(c)
    try: validate(bad)
    except AssertionError: out["provider_write_rejected"]=True
    else: out["provider_write_rejected"]=False
    bad=copy.deepcopy(d)
    for x in bad["triggers"]:
        if x[0]=="commerce.publish.bounded": x[7]=[p for p in x[7] if p!="valid_non_superseded_ECAC"]
    c=copy.deepcopy(bad); c.pop("sha256",None); bad["sha256"]=hj(c)
    try: validate(bad)
    except AssertionError: out["ecac_bypass_rejected"]=True
    else: out["ecac_bypass_rejected"]=False
    bad=copy.deepcopy(d); bad["rules"]["public_vault_locator"]=True; c=copy.deepcopy(bad); c.pop("sha256",None); bad["sha256"]=hj(c)
    try: validate(bad)
    except AssertionError: out["vault_locator_rejected"]=True
    else: out["vault_locator_rejected"]=False
    return out

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--manifest",type=Path,default=MANIFEST); ap.add_argument("--output",type=Path,default=Path("build/machine-trigger-assets")); ap.add_argument("--validate-only",action="store_true"); a=ap.parse_args()
    d=load(a.manifest); validate(d); n=negative(d)
    if not all(n.values()): raise AssertionError(n)
    if a.validate_only:
        print(json.dumps({"result":"PASS_MACHINE_TRIGGER_ASSET_FABRIC","negative":n},indent=2,sort_keys=True)); return 0
    with tempfile.TemporaryDirectory() as tmp:
        x=build(d,Path(tmp)/"a"); y=build(d,Path(tmp)/"b")
        if x!=y: raise AssertionError("deterministic_summary")
        if {p.name:p.read_bytes() for p in (Path(tmp)/"a").glob("*.json")}!={p.name:p.read_bytes() for p in (Path(tmp)/"b").glob("*.json")}: raise AssertionError("deterministic_packages")
    s=build(d,a.output); print(json.dumps({"result":"PASS_MACHINE_TRIGGER_ASSET_FABRIC","summary":s,"negative":n},indent=2,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
