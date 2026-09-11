#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
DOMAINS={"persistent_identity","persistent_state","deterministic_functions","queues","leases","recovery","evidence","authority_enforcement","health_check","model_dependency","degraded_without_model","replaceable_model","restart_behavior"}
CONSTITUENCIES={"penta.constituency.affected","penta.constituency.house-of-families","penta.constituency.independent-establishments","penta.constituency.senate-of-systems","penta.constituency.workforce"}
ZIP_SHA="9088509ff0da6f5b5590f4151559ba6652092acc479e9e388fb6bcd80a4b2f77"
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def sha(b): return hashlib.sha256(b).hexdigest()
def validate(root):
 k=load(root/".crownthrive/releases/cos-1.8.0-rc.1.kernel.json");m=load(root/".crownthrive/releases/cos-1.8.0-rc.1.manifest.json")
 r=k["release"];b=k["constitution_binding"];c=k["constituency_compact"];s=k["pentagovernance_survival_contract"];rc=k["ratification_case"]
 checks={
 "release_id":r["release_id"]=="ct.cos.release.1.8.0-rc.1",
 "exact_constitution":b["constitution"]["complete_edition_sha256"]==ZIP_SHA,
 "thirteen_domains":set(s["domains"])==DOMAINS,
 "five_constituencies":{x["constituency_id"] for x in c["constituencies"]}==CONSTITUENCIES,
 "human_floor_protected":all(x["machine_votes_may_satisfy_human_floor"] is False for x in c["constituencies"]),
 "no_self_certification":"PentaGovernance" in s["certification"]["certifier_must_be_distinct_from"] and s["certification"]["status"]!="VERIFIED",
 "separation":c["founder_assent_is_separate"] and c["institutional_enactment_is_separate"] and c["independent_certification_is_separate"],
 "fail_closed":all([not r["constitutional_effectiveness"],not r["production_eligible"],not r["authority_created"],not rc["constitutional_effectiveness"],not rc["production_eligible"],not rc["authority_created"]]),
 "provider_default_deny":k["penta_release_exact_subject_contract"]["provider_mutation_default"]=="DENY",
 "three_dail_same_subject":k["three_dail_contract"]["same_exact_subject_required"] is True}
 errors=[];rows=[]
 for row in m["files"]:
  p=root/row["path"]
  if not p.is_file(): errors.append("missing:"+row["path"]);continue
  data=p.read_bytes();d=sha(data)
  if d!=row["sha256"]: errors.append("digest:"+row["path"])
  if len(data)!=row["size"]: errors.append("size:"+row["path"])
  rows.append({"path":row["path"],"sha256":d,"size":len(data)})
 checks["artifact_digest"]=sha(json.dumps(rows,sort_keys=True,separators=(",",":")).encode())==m["artifact_digest_sha256"]
 errors += [n for n,v in checks.items() if not v];passed=not errors
 return {"decision":"PASS_COS_1_8_PREBINDING_KERNEL" if passed else "FAIL_COS_1_8_KERNEL","pass":passed,"checks":checks,"errors":sorted(set(errors)),"constitutional_effectiveness":False,"production_eligible":False,"authority_created":False}
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--root",default=".");a=ap.parse_args();res=validate(Path(a.root).resolve());print(json.dumps(res,indent=2,sort_keys=True));raise SystemExit(0 if res["pass"] else 1)
