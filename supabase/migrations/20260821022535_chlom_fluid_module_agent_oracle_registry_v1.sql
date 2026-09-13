create table if not exists chlom_runtime.module_capabilities (
  capability_id text primary key,
  module_id text not null references chlom_runtime.modules(module_id) on delete cascade,
  canonical_name text not null,
  capability_kind text not null check (capability_kind in ('api','mcp','event','pallet','agent','policy','oracle','storage','chain','ui','sdk','workflow','other')),
  semantic_version text not null default '0.1.0',
  risk_class text not null default 'D0' check (risk_class in ('D0','D1','D2','D3')),
  capability_state text not null default 'specified' check (capability_state in ('source_recovered','specified','prototype','test','staged','production','suspended','superseded','retired')),
  interface_ref text,
  input_schema jsonb not null default '{}'::jsonb,
  output_schema jsonb not null default '{}'::jsonb,
  public_safe boolean not null default false,
  hot_swappable boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chlom_runtime.platform_bindings (
  binding_id text primary key,
  module_id text not null references chlom_runtime.modules(module_id) on delete restrict,
  platform_id text not null,
  binding_type text not null check (binding_type in ('native','adapter','consumer','producer','verification','commerce','governance','evidence','planned')),
  binding_state text not null default 'specified' check (binding_state in ('specified','prototype','controlled_test','staged','production','hold','retired')),
  environment text not null default 'test' check (environment in ('local','development','test','staging','production')),
  feature_flag text,
  evidence_ref text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(module_id,platform_id,binding_type,environment)
);

create table if not exists chlom_runtime.agent_templates (
  agent_id text primary key,
  parent_agent_id text references chlom_runtime.agent_templates(agent_id) on delete set null,
  canonical_name text not null,
  agent_class text not null check (agent_class in ('orchestrator','planner','builder','researcher','reviewer','verifier','security','rights','sre','red_team','documentation','recovery','kernel','identity','dail','dla','lex','dispute','ace','aie','zkx','oracle','chain','commerce','developer','tevv','formal_methods','continuity','other')),
  autonomy_class text not null default 'A1' check (autonomy_class in ('A0','A1','A2','A3','A4')),
  authority_ceiling text not null default 'D1' check (authority_ceiling in ('D0','D1','D2','D3')),
  lifecycle_state text not null default 'specified' check (lifecycle_state in ('specified','test','active','paused','degraded','superseded','retired')),
  module_scope text[] not null default '{}'::text[],
  tool_scope jsonb not null default '{}'::jsonb,
  schedule_profile text,
  vote_eligible boolean not null default false,
  self_healing_enabled boolean not null default false,
  no_self_approval boolean not null default true,
  heartbeat_ttl_seconds integer not null default 3600 check (heartbeat_ttl_seconds between 60 and 604800),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chlom_runtime.agent_health (
  agent_id text primary key references chlom_runtime.agent_templates(agent_id) on delete cascade,
  run_id text,
  health_state text not null default 'pending' check (health_state in ('pending','healthy','degraded','failed','paused','retired')),
  current_task text,
  last_heartbeat_at timestamptz,
  last_success_at timestamptz,
  last_error_code text,
  current_commit_sha text,
  current_policy_sha text,
  resource_state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists chlom_runtime.oracle_registry (
  oracle_id text primary key,
  oracle_class text not null check (oracle_class in ('identity','regulatory','rights','pricing_fx','chain','sanctions','usage','media_fingerprint','ai_risk','governance','evidence','time_finality','other')),
  canonical_name text not null,
  source_policy text not null,
  oracle_state text not null default 'specified' check (oracle_state in ('specified','test','active','degraded','suspended','retired')),
  aggregation_policy text not null default 'single_source_review',
  authority_ceiling text not null default 'D1' check (authority_ceiling in ('D0','D1','D2','D3')),
  freshness_ttl_seconds integer,
  stake_model text,
  public_key_ref text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chlom_runtime.oracle_observations (
  observation_id uuid primary key default gen_random_uuid(),
  oracle_id text not null references chlom_runtime.oracle_registry(oracle_id) on delete restrict,
  observation_type text not null,
  subject_id text not null,
  value jsonb not null,
  confidence numeric(6,5) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  observed_at timestamptz not null,
  expires_at timestamptz,
  signature_ref text,
  source_digest_sha256 text,
  observation_state text not null default 'candidate' check (observation_state in ('candidate','accepted','outlier','expired','revoked')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_chlom_oracle_observation_subject on chlom_runtime.oracle_observations(subject_id, observation_type, observed_at desc);
create index if not exists idx_chlom_oracle_observation_oracle on chlom_runtime.oracle_observations(oracle_id, observed_at desc);

create table if not exists chlom_runtime.module_health (
  module_id text primary key references chlom_runtime.modules(module_id) on delete cascade,
  health_state text not null default 'pending' check (health_state in ('pending','healthy','degraded','failed','hold','not_applicable')),
  check_type text not null default 'registry',
  last_checked_at timestamptz,
  last_success_at timestamptz,
  evidence jsonb not null default '{}'::jsonb,
  repair_state text not null default 'none' check (repair_state in ('none','candidate','simulating','canary','repaired','rolled_back','escalated')),
  updated_at timestamptz not null default now()
);

-- Capability/product pallets: cloud/API packaging model, not Substrate runtime pallets.
insert into chlom_runtime.modules(module_id,canonical_name,module_class,semantic_version,lifecycle_state,authority_ceiling,self_healing_class,public_contract,metadata)
values
('ct.chlom.capability-pallet.p01','P-01 Identity & Access','pallet','0.1.0','reconciled','D2','rollback_capable','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p02','P-02 Governance & Compliance','pallet','0.1.0','reconciled','D3','human_reserved','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p03','P-03 Rights & Licensing','pallet','0.1.0','reconciled','D3','human_reserved','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p04','P-04 Media & Intellectual Property','pallet','0.1.0','reconciled','D3','human_reserved','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p05','P-05 Growth, Advertising & Measurement','pallet','0.1.0','reconciled','D2','rollback_capable','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p06','P-06 Commerce, Booking & Loyalty','pallet','0.1.0','reconciled','D3','human_reserved','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p07','P-07 Community, Directory & Events','pallet','0.1.0','reconciled','D2','rollback_capable','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p08','P-08 Education, Incubator & Impact','pallet','0.1.0','reconciled','D2','rollback_capable','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p09','P-09 Physical Suites & Place-Based','pallet','0.1.0','reconciled','D3','human_reserved','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p10','P-10 Operations & Institutional Memory','pallet','0.1.0','reconciled','D2','rollback_capable','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p11','P-11 Capital, Revenue & Settlement','pallet','0.1.0','reconciled','D3','human_reserved','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}'),
('ct.chlom.capability-pallet.p12','P-12 Sustainability & Impact Evidence','pallet','0.1.0','reconciled','D2','rollback_capable','{"pallet_namespace":"capability-packaging"}','{"pallet_kind":"cloud_api_product_packaging","not_substrate_runtime":true}')
on conflict(module_id) do update set canonical_name=excluded.canonical_name,lifecycle_state=excluded.lifecycle_state,authority_ceiling=excluded.authority_ceiling,self_healing_class=excluded.self_healing_class,public_contract=excluded.public_contract,metadata=chlom_runtime.modules.metadata||excluded.metadata,updated_at=now();

-- Runtime-pallet targets are separate from capability pallets.
insert into chlom_runtime.modules(module_id,canonical_name,module_class,semantic_version,lifecycle_state,authority_ceiling,self_healing_class,public_contract,metadata)
values
('ct.chlom.runtime-pallet.identity','Substrate Identity & Credential Pallet','pallet','0.1.0','specified','D2','quorum_required','{"runtime_family":"polkadot-sdk"}','{"pallet_kind":"substrate_runtime_target","production_verified":false}'),
('ct.chlom.runtime-pallet.dail','Substrate DAIL Anchor Pallet','pallet','0.1.0','specified','D2','quorum_required','{"runtime_family":"polkadot-sdk"}','{"pallet_kind":"substrate_runtime_target","production_verified":false}'),
('ct.chlom.runtime-pallet.rights','Substrate Rights/Attestation Pallet','pallet','0.1.0','specified','D3','human_reserved','{"runtime_family":"polkadot-sdk"}','{"pallet_kind":"substrate_runtime_target","production_verified":false}'),
('ct.chlom.runtime-pallet.dla','Substrate DLA Reference Pallet','pallet','0.1.0','specified','D3','human_reserved','{"runtime_family":"polkadot-sdk"}','{"pallet_kind":"substrate_runtime_target","production_verified":false}'),
('ct.chlom.runtime-pallet.policy','Substrate Policy Commitment Pallet','pallet','0.1.0','specified','D2','quorum_required','{"runtime_family":"polkadot-sdk"}','{"pallet_kind":"substrate_runtime_target","production_verified":false}'),
('ct.chlom.runtime-pallet.oracle','Substrate Oracle Attestation Pallet','pallet','0.1.0','specified','D2','quorum_required','{"runtime_family":"polkadot-sdk"}','{"pallet_kind":"substrate_runtime_target","production_verified":false}'),
('ct.chlom.runtime-pallet.governance','Substrate Governance Test Pallet','pallet','0.1.0','specified','D3','human_reserved','{"runtime_family":"polkadot-sdk"}','{"pallet_kind":"substrate_runtime_target","production_verified":false}')
on conflict(module_id) do update set canonical_name=excluded.canonical_name,lifecycle_state=excluded.lifecycle_state,authority_ceiling=excluded.authority_ceiling,self_healing_class=excluded.self_healing_class,public_contract=excluded.public_contract,metadata=chlom_runtime.modules.metadata||excluded.metadata,updated_at=now();

insert into chlom_runtime.module_capabilities(capability_id,module_id,canonical_name,capability_kind,semantic_version,risk_class,capability_state,interface_ref,public_safe,hot_swappable,metadata)
values
('ct.cap.chlom.module.discover','ct.chlom.kernel','Module Discovery','api','0.1.0','D0','prototype','/v1/modules',true,true,'{"fluid_metaprotocol":true}'),
('ct.cap.chlom.module.capabilities','ct.chlom.kernel','Capability Negotiation','api','0.1.0','D0','specified','/v1/modules/{id}/capabilities',true,true,'{"fluid_metaprotocol":true}'),
('ct.cap.chlom.module.health','ct.chlom.observability','Module Health','api','0.1.0','D0','specified','/v1/modules/{id}/health',true,true,'{}'),
('ct.cap.chlom.identity.resolve','ct.chlom.identity','Public ID Resolver','api','1.0.0','D0','test','supabase-edge:chlom-public-resolver@v1',true,true,'{"http_verified":true}'),
('ct.cap.chlom.identity.hosted-key','ct.chlom.identity','Hosted Key Registration','workflow','0.1.0','D2','test','vault + public key registry',false,true,'{"private_key_never_public":true}'),
('ct.cap.chlom.dail.append','ct.chlom.dail','DAIL Append','event','0.1.0','D2','test','public.chlom_append_dail_event',false,false,'{"append_only":true}'),
('ct.cap.chlom.dail.public-verify','ct.chlom.dail','Public DAIL Verification','api','0.1.0','D0','test','public.chlom_query_public_dail',true,true,'{}'),
('ct.cap.chlom.mcp.control','ct.chlom.api-mcp','Dedicated CHLOM MCP Server','mcp','0.1.0','D2','test','supabase-edge:chlom-api-control@v1',false,true,'{"server_id":"ct.mcp.chlom-core"}')
on conflict(capability_id) do update set capability_state=excluded.capability_state,interface_ref=excluded.interface_ref,public_safe=excluded.public_safe,hot_swappable=excluded.hot_swappable,metadata=chlom_runtime.module_capabilities.metadata||excluded.metadata,updated_at=now();

insert into chlom_runtime.platform_bindings(binding_id,module_id,platform_id,binding_type,binding_state,environment,feature_flag,evidence_ref,metadata)
values
('ct.bind.vm.chlom.identity','ct.chlom.identity','ct.platform.virality-music','consumer','controlled_test','test','chlom_identity_enabled','supabase:chlom_identity','{"activation":"pilot"}'),
('ct.bind.vm.chlom.dail','ct.chlom.dail','ct.platform.virality-music','evidence','controlled_test','test','chlom_dail_enabled','supabase:chlom_runtime.dail_events','{"activation":"pilot"}'),
('ct.bind.vm.chlom.dla','ct.chlom.dla','ct.platform.virality-music','commerce','specified','test','chlom_dla_enabled',null,'{"activation":"pilot_pending"}'),
('ct.bind.vm.chlom.lex','ct.chlom.lex','ct.platform.virality-music','commerce','specified','test','chlom_lex_enabled',null,'{"activation":"pilot_pending"}'),
('ct.bind.kjv.chlom.identity','ct.chlom.identity','ct.platform.kjv-sermon-toolkit','consumer','controlled_test','test','chlom_identity_enabled','supabase:chlom_identity','{"activation":"pilot"}'),
('ct.bind.kjv.chlom.dail','ct.chlom.dail','ct.platform.kjv-sermon-toolkit','evidence','controlled_test','test','chlom_dail_enabled','supabase:chlom_runtime.dail_events','{"activation":"pilot"}'),
('ct.bind.kjv.chlom.dla','ct.chlom.dla','ct.platform.kjv-sermon-toolkit','commerce','specified','test','chlom_dla_enabled',null,'{"activation":"pilot_pending"}')
on conflict(binding_id) do update set binding_state=excluded.binding_state,feature_flag=excluded.feature_flag,evidence_ref=excluded.evidence_ref,metadata=chlom_runtime.platform_bindings.metadata||excluded.metadata,updated_at=now();

-- Agent fabric seed. Parent must exist before children.
insert into chlom_runtime.agent_templates(agent_id,parent_agent_id,canonical_name,agent_class,autonomy_class,authority_ceiling,lifecycle_state,module_scope,tool_scope,schedule_profile,vote_eligible,self_healing_enabled,metadata)
values
('ct.chlom.agent.orchestrator',null,'CHLOM Orchestrator','orchestrator','A3','D2','test',array['ct.chlom.kernel','ct.chlom.agent-fabric'],'{"scope":"orchestration_only"}','continuous',false,true,'{"cannot_self_approve":true}')
on conflict(agent_id) do update set lifecycle_state=excluded.lifecycle_state,updated_at=now();

insert into chlom_runtime.agent_templates(agent_id,parent_agent_id,canonical_name,agent_class,autonomy_class,authority_ceiling,lifecycle_state,module_scope,tool_scope,schedule_profile,vote_eligible,self_healing_enabled,metadata)
values
('ct.chlom.agent.continuity','ct.chlom.agent.orchestrator','Institutional Continuity Agent','continuity','A2','D2','test',array['ct.chlom.documentation','ct.chlom.dail'],'{"drive":"write_governed_docs","mintlify":"draft_only"}','daily',false,true,'{}'),
('ct.chlom.agent.kernel','ct.chlom.agent.orchestrator','Kernel Agent','kernel','A2','D2','test',array['ct.chlom.kernel'],'{"code":"private_repo_candidate"}',null,false,true,'{}'),
('ct.chlom.agent.identity','ct.chlom.agent.orchestrator','Identity & Fingerprint Agent','identity','A2','D2','test',array['ct.chlom.identity','ct.chlom.fingerprint'],'{"vault":"reference_only"}','daily',false,true,'{}'),
('ct.chlom.agent.dail','ct.chlom.agent.orchestrator','DAIL Integrity Agent','dail','A2','D2','test',array['ct.chlom.dail'],'{"dail":"append_verify"}','daily',true,true,'{}'),
('ct.chlom.agent.dla','ct.chlom.agent.orchestrator','DLA Agent','dla','A1','D3','test',array['ct.chlom.dla','ct.chlom.rights'],'{"license":"prepare_only"}',null,false,false,'{}'),
('ct.chlom.agent.lex','ct.chlom.agent.orchestrator','LEX Agent','lex','A1','D3','test',array['ct.chlom.lex','ct.chlom.dla'],'{"marketplace":"prepare_only"}',null,false,false,'{}'),
('ct.chlom.agent.dispute','ct.chlom.agent.orchestrator','Dispute & Remedies Agent','dispute','A1','D3','test',array['ct.chlom.disputes'],'{"case":"prepare_review"}',null,false,false,'{}'),
('ct.chlom.agent.ace','ct.chlom.agent.orchestrator','Adaptive Compliance Engine Agent','ace','A2','D2','test',array['ct.chlom.ace'],'{"policy":"evaluate"}','daily',true,true,'{}'),
('ct.chlom.agent.aie','ct.chlom.agent.orchestrator','Anomaly Intelligence Engine Agent','aie','A2','D2','test',array['ct.chlom.aie'],'{"risk":"score_recommend"}','daily',true,true,'{}'),
('ct.chlom.agent.zkx','ct.chlom.agent.orchestrator','ZKX Agent','zkx','A1','D2','test',array['ct.chlom.zkx'],'{"zk":"research_test"}','weekly',false,false,'{}'),
('ct.chlom.agent.oracle','ct.chlom.agent.orchestrator','Oracle Fabric Agent','oracle','A2','D2','test',array['ct.chlom.oracle-fabric'],'{"oracle":"observe_aggregate"}','hourly',true,true,'{}'),
('ct.chlom.agent.chain','ct.chlom.agent.orchestrator','Chain Adapter Agent','chain','A1','D2','test',array['ct.chlom.chain-adapters'],'{"chain":"testnet_only"}','hourly',false,true,'{}'),
('ct.chlom.agent.security','ct.chlom.agent.orchestrator','Security Sentinel','security','A2','D2','test',array['ct.chlom.kernel','ct.chlom.api-mcp','ct.chlom.observability'],'{"security":"scan_block"}','hourly',true,true,'{}'),
('ct.chlom.agent.tevv','ct.chlom.agent.orchestrator','AI/ML TEVV Agent','tevv','A2','D2','test',array['ct.chlom.aie','ct.chlom.ace'],'{"model":"evaluate_block"}','weekly',true,true,'{}'),
('ct.chlom.agent.formal','ct.chlom.agent.orchestrator','Formal Methods Agent','formal_methods','A1','D2','test',array['ct.chlom.kernel','ct.chlom.dail','ct.chlom.dla'],'{"formal":"spec_verify"}','weekly',false,false,'{}'),
('ct.chlom.agent.sre','ct.chlom.agent.orchestrator','SRE & Self-Healing Agent','sre','A2','D2','test',array['ct.chlom.observability'],'{"repair":"bounded"}','hourly',true,true,'{}'),
('ct.chlom.agent.red-team','ct.chlom.agent.orchestrator','Red Team Agent','red_team','A1','D2','test',array['ct.chlom.kernel','ct.chlom.api-mcp'],'{"attack":"test_only"}','weekly',false,false,'{}'),
('ct.chlom.agent.docs','ct.chlom.agent.orchestrator','Documentation & Papers Agent','documentation','A2','D2','test',array['ct.chlom.documentation'],'{"mintlify":"draft","drive":"write"}','daily',false,true,'{}'),
('ct.chlom.agent.commerce','ct.chlom.agent.orchestrator','Commerce & Settlement Agent','commerce','A1','D3','test',array['ct.chlom.dla','ct.chlom.lex'],'{"commerce":"prepare_reconcile"}','daily',false,false,'{}'),
('ct.chlom.agent.developer','ct.chlom.agent.orchestrator','Developer API/MCP Agent','developer','A2','D2','test',array['ct.chlom.api-mcp'],'{"api":"build_test"}','daily',false,true,'{}')
on conflict(agent_id) do update set parent_agent_id=excluded.parent_agent_id,canonical_name=excluded.canonical_name,agent_class=excluded.agent_class,autonomy_class=excluded.autonomy_class,authority_ceiling=excluded.authority_ceiling,lifecycle_state=excluded.lifecycle_state,module_scope=excluded.module_scope,tool_scope=excluded.tool_scope,schedule_profile=excluded.schedule_profile,vote_eligible=excluded.vote_eligible,self_healing_enabled=excluded.self_healing_enabled,metadata=chlom_runtime.agent_templates.metadata||excluded.metadata,updated_at=now();

insert into chlom_runtime.agent_health(agent_id,health_state,updated_at)
select agent_id,'pending',now() from chlom_runtime.agent_templates
on conflict(agent_id) do nothing;

insert into chlom_runtime.oracle_registry(oracle_id,oracle_class,canonical_name,source_policy,oracle_state,aggregation_policy,authority_ceiling,freshness_ttl_seconds,metadata)
values
('ct.chlom.oracle.identity','identity','Identity Attestation Oracle','trusted-verifier signed attestations','specified','quorum_or_direct_authority','D2',86400,'{}'),
('ct.chlom.oracle.regulatory','regulatory','Regulatory Source Oracle','authoritative public legal/regulatory sources','specified','multi_source_reconciliation','D2',86400,'{}'),
('ct.chlom.oracle.rights','rights','Rights Evidence Oracle','governed chain-of-title evidence','specified','evidence_weighted_review','D3',null,'{}'),
('ct.chlom.oracle.fx','pricing_fx','Pricing / FX Oracle','approved market data providers','specified','weighted_median','D2',900,'{}'),
('ct.chlom.oracle.chain','chain','Chain Finality Oracle','approved RPC/readback providers','specified','quorum_finality','D2',120,'{}'),
('ct.chlom.oracle.sanctions','sanctions','Sanctions Oracle','official sanctions sources only','specified','source_authority_precedence','D3',86400,'{}'),
('ct.chlom.oracle.usage','usage','Usage Attestation Oracle','signed platform usage events','specified','signed_source_quorum','D2',3600,'{}'),
('ct.chlom.oracle.media','media_fingerprint','Media Fingerprint Oracle','approved fingerprint engines','specified','multi_algorithm_similarity','D2',null,'{}'),
('ct.chlom.oracle.aie','ai_risk','AIE Risk Oracle','governed AIE model registry','specified','ensemble_with_reason_codes','D2',300,'{}'),
('ct.chlom.oracle.governance','governance','Governance Decision Oracle','signed governed decision records','specified','quorum_signature','D3',null,'{}'),
('ct.chlom.oracle.evidence','evidence','Evidence Integrity Oracle','DAIL and evidence hash verification','test','hash_chain_and_merkle','D2',3600,'{}'),
('ct.chlom.oracle.time','time_finality','Time & Finality Oracle','chain timestamps plus trusted time sources','specified','median_with_chain_finality','D2',120,'{}')
on conflict(oracle_id) do update set oracle_state=excluded.oracle_state,aggregation_policy=excluded.aggregation_policy,authority_ceiling=excluded.authority_ceiling,freshness_ttl_seconds=excluded.freshness_ttl_seconds,metadata=chlom_runtime.oracle_registry.metadata||excluded.metadata,updated_at=now();

insert into chlom_runtime.module_health(module_id,health_state,check_type,last_checked_at,evidence)
select module_id,
       case when lifecycle_state in ('prototype','test') then 'pending' when lifecycle_state in ('specified','reconciled','source_recovered') then 'not_applicable' else 'pending' end,
       'registry',now(),jsonb_build_object('lifecycle_state',lifecycle_state)
from chlom_runtime.modules
on conflict(module_id) do update set check_type=excluded.check_type,last_checked_at=excluded.last_checked_at,evidence=excluded.evidence,updated_at=now();

select chlom_runtime.append_dail_event(
  'chlom.fluid_registry.seeded','framework','ct.framework.chlom',
  jsonb_build_object(
    'module_count',(select count(*) from chlom_runtime.modules),
    'capability_count',(select count(*) from chlom_runtime.module_capabilities),
    'agent_template_count',(select count(*) from chlom_runtime.agent_templates),
    'oracle_count',(select count(*) from chlom_runtime.oracle_registry),
    'platform_binding_count',(select count(*) from chlom_runtime.platform_bindings),
    'fluid_modular',true
  ),
  'founder-directive-2026-08-20',null,'ct.chlom.agent.orchestrator','0.1.0',null,null,'D2 founder authorized architecture',null,'internal'
);