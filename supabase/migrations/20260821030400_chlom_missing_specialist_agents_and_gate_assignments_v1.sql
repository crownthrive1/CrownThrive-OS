insert into chlom_runtime.agent_templates(
  agent_id,parent_agent_id,canonical_name,agent_class,autonomy_class,authority_ceiling,lifecycle_state,module_scope,tool_scope,schedule_profile,vote_eligible,self_healing_enabled,no_self_approval,heartbeat_ttl_seconds,metadata
) values
('ct.chlom.agent.vm-integration','ct.chlom.agent.orchestrator','Virality Music CHLOM Integration Agent','builder','A2','D2','test',array['ct.chlom.identity','ct.chlom.fingerprint','ct.chlom.rights','ct.chlom.dla','ct.chlom.dail','ct.chlom.lex','ct.chlom.settlement'],jsonb_build_object('platform','ct.platform.virality-music'),'continuous',false,true,true,3600,jsonb_build_object('role','customer_zero_integration')),
('ct.chlom.agent.kjv-integration','ct.chlom.agent.orchestrator','KJV/Sermon Toolkit CHLOM Integration Agent','builder','A2','D2','test',array['ct.chlom.identity','ct.chlom.fingerprint','ct.chlom.rights','ct.chlom.dla','ct.chlom.dail','ct.chlom.settlement'],jsonb_build_object('platform','ct.platform.kjv-sermon-toolkit'),'continuous',false,true,true,3600,jsonb_build_object('role','customer_one_integration')),
('ct.chlom.agent.creator-beta','ct.chlom.agent.orchestrator','Third-Party Creator Beta Agent','builder','A1','D2','test',array['ct.chlom.identity','ct.chlom.rights','ct.chlom.dla','ct.chlom.lex','ct.chlom.disputes'],jsonb_build_object('scope','gated_creator_onboarding'),'daily',false,false,true,7200,jsonb_build_object('role','external_creator_beta')),
('ct.chlom.agent.legal-regulatory','ct.chlom.agent.orchestrator','Legal and Regulatory Research Agent','researcher','A1','D2','test',array['ct.chlom.rights','ct.chlom.dla','ct.chlom.lex','ct.chlom.treasury','ct.chlom.settlement','ct.chlom.governance'],jsonb_build_object('specialist_domain','legal_regulatory'),'weekly',false,false,true,86400,jsonb_build_object('cannot_substitute_for_counsel',true)),
('ct.chlom.agent.ip-licensing','ct.chlom.agent.orchestrator','IP Rights and Licensing Specialist Agent','rights','A1','D2','test',array['ct.chlom.rights','ct.chlom.dla','ct.chlom.lex','ct.chlom.disputes','ct.chlom.ade'],jsonb_build_object('specialist_domain','ip_licensing'),'continuous',false,false,true,7200,jsonb_build_object('rights_authority','review_only_until_delegated')),
('ct.chlom.agent.finance-tax','ct.chlom.agent.orchestrator','Finance Tax and Treasury Review Agent','reviewer','A1','D2','test',array['ct.chlom.treasury','ct.chlom.settlement','ct.chlom.ade','ct.chlom.lex'],jsonb_build_object('specialist_domain','finance_tax_treasury'),'weekly',false,false,true,86400,jsonb_build_object('cannot_substitute_for_licensed_professional',true)),
('ct.chlom.agent.accessibility-consumer','ct.chlom.agent.orchestrator','Accessibility and Consumer Protection Agent','reviewer','A1','D2','test',array['ct.chlom.lex','ct.chlom.dla','ct.chlom.api-mcp'],jsonb_build_object('specialist_domain','accessibility_consumer'),'weekly',false,false,true,86400,jsonb_build_object('role','consumer_protection_accessibility')),
('ct.chlom.agent.cultural-governance','ct.chlom.agent.orchestrator','CIE Cultural Governance Agent','reviewer','A1','D2','test',array['ct.chlom.rights','ct.chlom.dla','ct.chlom.lex','ct.chlom.governance','ct.chlom.agent-fabric'],jsonb_build_object('specialist_domain','cultural_governance'),'continuous',false,false,true,7200,jsonb_build_object('framework','ct.framework.cultural-imprint-engine')),
('ct.chlom.agent.blockchain-crypto','ct.chlom.agent.orchestrator','Blockchain and Cryptographic Protocol Specialist Agent','chain','A1','D2','test',array['ct.chlom.chain-adapters','ct.chlom.zkx','ct.chlom.governance','ct.chlom.treasury'],jsonb_build_object('specialist_domain','blockchain_crypto'),'continuous',false,false,true,7200,jsonb_build_object('role','chain_crypto_assurance')),
('ct.chlom.agent.tokenomics-treasury','ct.chlom.agent.orchestrator','Tokenomics and Treasury Simulation Agent','commerce','A1','D2','test',array['ct.chlom.treasury','ct.chlom.settlement','ct.chlom.governance','ct.chlom.chain-adapters'],jsonb_build_object('scope','economic_simulation_only'),'weekly',false,false,true,86400,jsonb_build_object('real_value_execution',false)),
('ct.chlom.agent.recovery','ct.chlom.agent.orchestrator','CHLOM Recovery and Custody Agent','recovery','A2','D2','test',array['ct.chlom.backup-recovery','ct.chlom.identity','ct.chlom.dail'],jsonb_build_object('scope','restore_and_custody_validation'),'daily',false,true,true,7200,jsonb_build_object('private_key_export',false)),
('ct.chlom.agent.release-certifier','ct.chlom.agent.orchestrator','CHLOM Independent Release Certifier','verifier','A1','D2','test',array[]::text[],jsonb_build_object('scope','independent_promotion_verification'),'continuous',false,false,true,7200,jsonb_build_object('cannot_be_originator',true))
on conflict (agent_id) do update set
 parent_agent_id=excluded.parent_agent_id,canonical_name=excluded.canonical_name,agent_class=excluded.agent_class,
 autonomy_class=excluded.autonomy_class,authority_ceiling=excluded.authority_ceiling,lifecycle_state=excluded.lifecycle_state,
 module_scope=excluded.module_scope,tool_scope=excluded.tool_scope,schedule_profile=excluded.schedule_profile,
 vote_eligible=false,self_healing_enabled=excluded.self_healing_enabled,no_self_approval=true,
 heartbeat_ttl_seconds=excluded.heartbeat_ttl_seconds,metadata=excluded.metadata,updated_at=now();

create table if not exists chlom_runtime.construction_gate_assignments (
  gate_id text primary key references chlom_runtime.construction_gate_definitions(gate_id) on delete cascade,
  primary_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  verifier_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  recovery_agent_id text references chlom_runtime.agent_templates(agent_id) on delete restrict,
  assignment_state text not null default 'active' check (assignment_state in ('active','paused','superseded')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (primary_agent_id <> verifier_agent_id)
);
revoke all on chlom_runtime.construction_gate_assignments from public,anon,authenticated;

insert into chlom_runtime.construction_gate_assignments(gate_id,primary_agent_id,verifier_agent_id,recovery_agent_id,metadata)
select g.gate_id,
  case g.gate_family
    when 'source' then 'ct.chlom.agent.continuity'
    when 'identity' then 'ct.chlom.agent.identity'
    when 'terminology' then 'ct.chlom.agent.continuity'
    when 'architecture' then 'ct.chlom.agent.kernel'
    when 'data' then 'ct.chlom.agent.kernel'
    when 'authority' then 'ct.chlom.agent.security'
    when 'security' then 'ct.chlom.agent.security'
    when 'privacy' then 'ct.chlom.agent.security'
    when 'implementation' then 'ct.chlom.agent.kernel'
    when 'testing' then 'ct.chlom.agent.tevv'
    when 'assurance' then 'ct.chlom.agent.formal'
    when 'evidence' then 'ct.chlom.agent.dail'
    when 'operations' then 'ct.chlom.agent.sre'
    when 'resilience' then 'ct.chlom.agent.sre'
    when 'performance' then 'ct.chlom.agent.sre'
    when 'developer' then 'ct.chlom.agent.developer'
    when 'agents' then 'ct.chlom.agent.orchestrator'
    when 'oracles' then 'ct.chlom.agent.oracle'
    when 'ai_ml' then 'ct.chlom.agent.tevv'
    when 'rights' then 'ct.chlom.agent.ip-licensing'
    when 'licensing' then 'ct.chlom.agent.dla'
    when 'market' then 'ct.chlom.agent.lex'
    when 'remedies' then 'ct.chlom.agent.dispute'
    when 'commerce' then 'ct.chlom.agent.commerce'
    when 'finance' then 'ct.chlom.agent.finance-tax'
    when 'economics' then 'ct.chlom.agent.tokenomics-treasury'
    when 'legal' then 'ct.chlom.agent.legal-regulatory'
    when 'custody' then 'ct.chlom.agent.recovery'
    when 'chain' then 'ct.chlom.agent.chain'
    when 'integration' then case g.gate_id when 'CG-044' then 'ct.chlom.agent.vm-integration' when 'CG-045' then 'ct.chlom.agent.kjv-integration' else 'ct.chlom.agent.creator-beta' end
    when 'consumer' then 'ct.chlom.agent.accessibility-consumer'
    when 'culture' then 'ct.chlom.agent.cultural-governance'
    when 'governance' then 'ct.chlom.agent.orchestrator'
    when 'documentation' then 'ct.chlom.agent.docs'
    when 'continuity' then 'ct.chlom.agent.continuity'
    when 'portability' then 'ct.chlom.agent.continuity'
    when 'claims' then 'ct.chlom.agent.docs'
    when 'release' then 'ct.chlom.agent.release-certifier'
    else 'ct.chlom.agent.orchestrator' end,
  case
    when g.gate_family='release' then 'ct.chlom.agent.security'
    when g.gate_family in ('security','privacy','custody','chain') then 'ct.chlom.agent.release-certifier'
    when g.gate_family in ('rights','licensing','market','remedies') then 'ct.chlom.agent.security'
    when g.gate_family in ('ai_ml','oracles','agents') then 'ct.chlom.agent.security'
    else 'ct.chlom.agent.release-certifier' end,
  case when g.gate_family in ('operations','resilience','custody','continuity','release','chain') then 'ct.chlom.agent.recovery' else null end,
  jsonb_build_object('assignment_source','construction_gate_family_v1')
from chlom_runtime.construction_gate_definitions g
on conflict (gate_id) do update set primary_agent_id=excluded.primary_agent_id,verifier_agent_id=excluded.verifier_agent_id,recovery_agent_id=excluded.recovery_agent_id,metadata=excluded.metadata,updated_at=now();