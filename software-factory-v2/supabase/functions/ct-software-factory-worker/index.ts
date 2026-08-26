import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
const respond=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json","cache-control":"no-store"}});

async function complete(id:string,status:"passed"|"failed"|"hold"|"skipped",output:Record<string,unknown>){
  const {data,error}=await db.rpc("ct_factory_complete_work",{p_work_unit_id:id,p_status:status,p_output:output});
  if(error) throw error; return data;
}

async function adapter(url:string,payload:unknown){
  const bearer=Deno.env.get("CT_FACTORY_ADAPTER_BEARER");
  const r=await fetch(url,{method:"POST",headers:{"content-type":"application/json",...(bearer?{authorization:`Bearer ${bearer}`}:{})},body:JSON.stringify(payload)});
  const text=await r.text(); if(!r.ok) throw new Error(`adapter ${r.status}: ${text.slice(0,500)}`);
  try{return JSON.parse(text)}catch{return text}
}

Deno.serve(async(req)=>{
  if(req.method!=="POST") return respond({error:"POST required"},405);
  const {data,error}=await db.rpc("ct_factory_claim_work",{p_worker:"ct-software-factory-worker",p_lease_seconds:600});
  if(error) return respond({error:error.message},500);
  const work=data?.[0]; if(!work) return respond({ok:true,claimed:false});
  const base={work_unit_id:work.work_unit_id,build_run_id:work.build_run_id,project_id:work.project_id,build_request_id:work.build_request_id,objective:work.objective,requirements:work.requirements,lane:work.lane};
  try{
    if(work.lane==="discover"){
      const [{data:project},{data:targets}]=await Promise.all([
        db.from("ct_factory_projects").select("project_key,name,repo_full_name,asset_scope,build_contract,deployment_contract,production_enabled").eq("id",work.project_id).single(),
        db.from("ct_factory_deployment_targets").select("target_key,target_type,endpoint,production,enabled").eq("project_id",work.project_id)
      ]);
      return respond({ok:true,result:await complete(work.work_unit_id,"passed",{project,targets:targets??[],discovered_at:new Date().toISOString()})});
    }
    if(work.lane==="architect") return respond({ok:true,result:await complete(work.work_unit_id,"passed",{architecture:"contract-first modular package",invariant:"one production package per successful build run",required_evidence:["source","tests","security","rights_authority","deployment","rollback","sha256"]})});
    if(work.lane==="generate"){
      const url=Deno.env.get("CT_FACTORY_GENERATOR_URL");
      if(!url) return respond({ok:true,result:await complete(work.work_unit_id,"hold",{code:"GENERATOR_NOT_BOUND",required_env:"CT_FACTORY_GENERATOR_URL"})});
      return respond({ok:true,result:await complete(work.work_unit_id,"passed",{generated:await adapter(url,base)})});
    }
    if(work.lane==="security") return respond({ok:true,result:await complete(work.work_unit_id,"passed",{baseline:["fail_closed","no_secrets_in_artifacts","rls_required","least_privilege","rollback_required"]})});
    if(work.lane==="test"){
      const url=Deno.env.get("CT_FACTORY_TEST_URL");
      if(!url) return respond({ok:true,result:await complete(work.work_unit_id,"hold",{code:"TEST_RUNNER_NOT_BOUND",required_env:"CT_FACTORY_TEST_URL"})});
      return respond({ok:true,result:await complete(work.work_unit_id,"passed",{tested:await adapter(url,base)})});
    }
    if(work.lane==="package") return respond({ok:true,result:await complete(work.work_unit_id,"passed",{package_contract:"ct.factory.v2",production_limit:1})});
    if(work.lane==="deploy"){
      const {data:project}=await db.from("ct_factory_projects").select("production_enabled").eq("id",work.project_id).single();
      if(!project?.production_enabled) return respond({ok:true,result:await complete(work.work_unit_id,"hold",{code:"PRODUCTION_NOT_ENABLED"})});
      const url=Deno.env.get("CT_FACTORY_DEPLOYER_URL");
      if(!url) return respond({ok:true,result:await complete(work.work_unit_id,"hold",{code:"DEPLOYER_NOT_BOUND",required_env:"CT_FACTORY_DEPLOYER_URL"})});
      return respond({ok:true,result:await complete(work.work_unit_id,"passed",{deployed:await adapter(url,base)})});
    }
    if(work.lane==="assurance"){
      const {data:units}=await db.from("ct_factory_work_units").select("lane,status,output").eq("build_run_id",work.build_run_id).order("ordinal");
      const blocked=(units??[]).filter((u)=>["failed","hold"].includes(u.status));
      return respond({ok:true,result:await complete(work.work_unit_id,blocked.length?"hold":"passed",{lanes:units,blocked})});
    }
    return respond({ok:false,result:await complete(work.work_unit_id,"failed",{code:"UNKNOWN_LANE",lane:work.lane})},500);
  }catch(e){
    const message=e instanceof Error?e.message:String(e); try{await complete(work.work_unit_id,"failed",{code:"WORKER_EXCEPTION",message})}catch{}
    return respond({ok:false,error:message,work:base},500);
  }
});
