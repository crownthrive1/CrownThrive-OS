-- CrownThrive CHLOM + PentaSecurity assurance fabric v1
-- Additive candidate only. This migration creates no D3 authority, provider-write authority,
-- certification, rights grant, credential authority, money movement, or token economy.

create table if not exists penta_runtime.security_framework_registry_v1 (
  framework_key text primary key,
  framework_name text not null,
  version_ref text not null,
  baseline_role text not null,
  implementation_status text not null default 'mapped'
    check (implementation_status in ('mapped','implemented','certified_target','external_certified')),
  external_certification_claimed boolean not null default false,
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_runtime.security_capability_bindings_v1 (
  capability_key text primary key,
  canonical_name text not null,
  canonical_identity_key text,
  family_key text,
  implementation_state text not null
    check (implementation_state in ('existing_runtime','existing_identity','alias_candidate','gap_hold','build_candidate','certification_hold','production_certified')),
  alias_of text,
  authority_ceiling text not null default 'D2'
    check (authority_ceiling in ('D0','D1','D2','D3')),
  source_ref text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_runtime.security_assurance_cases_v1 (
  case_id uuid primary key default gen_random_uuid(),
  subject_ref text not null,
  subject_version text not null,
  current_state text not null default 'candidate'
    check (current_state in ('candidate','scanned','threat_modeled','tested','security_pass','chlom_pass','cie_pass','certification_pending','certified','released','hold','failed')),
  requires_cie boolean not null default false,
  originator_ref text not null,
  security_decider_ref text not null,
  certifier_ref text not null,
  chlom_authority_ref text not null,
  cie_decider_ref text,
  evidence_digest text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(subject_ref, subject_version),
  check (originator_ref <> security_decider_ref),
  check (originator_ref <> certifier_ref),
  check (security_decider_ref <> certifier_ref),
  check (originator_ref <> chlom_authority_ref),
  check ((not requires_cie) or (cie_decider_ref is not null and cie_decider_ref <> originator_ref and cie_decider_ref <> certifier_ref))
);

create table if not exists penta_runtime.security_assurance_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  case_id uuid not null references penta_runtime.security_assurance_cases_v1(case_id) on delete restrict,
  from_state text,
  to_state text not null,
  actor_ref text not null,
  evidence_ref text not null,
  semantic_stage text not null check (semantic_stage in ('evidence','decision','execution')),
  canonical_dail_event_id uuid not null,
  canonical_dail_event_hash text not null,
  dail_classification jsonb not null,
  event_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(canonical_dail_event_id)
);

create or replace function penta_runtime.security_assurance_events_immutable_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, penta_runtime
as $$
begin
  raise exception 'security assurance events are append-only';
end
$$;

drop trigger if exists security_assurance_events_immutable_v1
  on penta_runtime.security_assurance_events_v1;
create trigger security_assurance_events_immutable_v1
before update or delete on penta_runtime.security_assurance_events_v1
for each row execute function penta_runtime.security_assurance_events_immutable_v1();

create or replace function penta_runtime.security_assurance_open_case_v1(
  p_subject_ref text,
  p_subject_version text,
  p_originator_ref text,
  p_security_decider_ref text,
  p_certifier_ref text,
  p_chlom_authority_ref text,
  p_evidence_ref text,
  p_requires_cie boolean default false,
  p_cie_decider_ref text default null,
  p_evidence_digest text default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, penta_runtime, chlom_runtime
as $$
declare
  v_case_id uuid;
  v_dail jsonb;
  v_classification jsonb;
  v_dail_event_id uuid;
  v_dail_event_hash text;
  v_readback_hash text;
begin
  if coalesce(btrim(p_subject_ref),'') = ''
     or coalesce(btrim(p_subject_version),'') = ''
     or coalesce(btrim(p_originator_ref),'') = ''
     or coalesce(btrim(p_security_decider_ref),'') = ''
     or coalesce(btrim(p_certifier_ref),'') = ''
     or coalesce(btrim(p_chlom_authority_ref),'') = ''
     or coalesce(btrim(p_evidence_ref),'') = '' then
    raise exception 'subject/version/originator/security-decider/certifier/CHLOM-authority/evidence are required';
  end if;

  if p_originator_ref = p_security_decider_ref
     or p_originator_ref = p_certifier_ref
     or p_security_decider_ref = p_certifier_ref
     or p_originator_ref = p_chlom_authority_ref then
    raise exception 'originator, security decider, certifier and CHLOM authority must preserve required separation of duties';
  end if;

  if p_requires_cie and (
      coalesce(btrim(p_cie_decider_ref),'') = ''
      or p_cie_decider_ref = p_originator_ref
      or p_cie_decider_ref = p_certifier_ref
    ) then
    raise exception 'independent CIE decider required when CIE is applicable';
  end if;

  insert into penta_runtime.security_assurance_cases_v1(
    subject_ref, subject_version, requires_cie, originator_ref,
    security_decider_ref, certifier_ref, chlom_authority_ref, cie_decider_ref,
    evidence_digest, metadata
  ) values (
    p_subject_ref, p_subject_version, coalesce(p_requires_cie,false), p_originator_ref,
    p_security_decider_ref, p_certifier_ref, p_chlom_authority_ref, p_cie_decider_ref,
    p_evidence_digest, coalesce(p_metadata,'{}'::jsonb)
  )
  returning case_id into v_case_id;

  v_dail := chlom_runtime.append_dail_event(
    'security_assurance_evidence',
    'security_assurance_case',
    v_case_id::text,
    jsonb_build_object(
      'subject_ref', p_subject_ref,
      'subject_version', p_subject_version,
      'state', 'candidate',
      'semantic_stage', 'evidence',
      'evidence_ref', p_evidence_ref,
      'requires_cie', coalesce(p_requires_cie,false)
    ),
    p_originator_ref,
    p_actor_did,
    p_agent_id,
    p_subject_version,
    v_case_id::text,
    null,
    'ct.pentasecurity.assurance.open.v1',
    null,
    'internal'
  );

  v_dail_event_id := (v_dail->>'event_id')::uuid;
  v_dail_event_hash := v_dail->>'event_hash';
  v_classification := chlom_runtime.dail_classify_event_lanes_v1(v_dail_event_id);

  select event_hash into v_readback_hash
  from chlom_runtime.dail_events
  where event_id = v_dail_event_id;

  if v_readback_hash is null or v_readback_hash <> v_dail_event_hash then
    raise exception 'canonical DAIL append/readback mismatch while opening assurance case';
  end if;

  insert into penta_runtime.security_assurance_events_v1(
    case_id, from_state, to_state, actor_ref, evidence_ref, semantic_stage,
    canonical_dail_event_id, canonical_dail_event_hash, dail_classification, event_metadata
  ) values (
    v_case_id, null, 'candidate', p_originator_ref, p_evidence_ref, 'evidence',
    v_dail_event_id, v_dail_event_hash, v_classification, coalesce(p_metadata,'{}'::jsonb)
  );

  return jsonb_build_object(
    'case_id', v_case_id,
    'state', 'candidate',
    'dail_event_id', v_dail_event_id,
    'dail_event_hash', v_dail_event_hash,
    'dail_classification', v_classification
  );
end
$$;

create or replace function penta_runtime.security_assurance_transition_v1(
  p_case_id uuid,
  p_to_state text,
  p_actor_ref text,
  p_evidence_ref text,
  p_semantic_stage text,
  p_authority_basis text default 'ct.pentasecurity.assurance.transition.v1',
  p_approval_id text default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, penta_runtime, chlom_runtime
as $$
declare
  v penta_runtime.security_assurance_cases_v1%rowtype;
  v_ok boolean := false;
  v_event_type text;
  v_dail jsonb;
  v_classification jsonb;
  v_dail_event_id uuid;
  v_dail_event_hash text;
  v_readback_hash text;
  v_prev_dail_event_id uuid;
begin
  select * into v
  from penta_runtime.security_assurance_cases_v1
  where case_id = p_case_id
  for update;

  if not found then
    raise exception 'unknown assurance case';
  end if;

  if coalesce(btrim(p_actor_ref),'') = ''
     or coalesce(btrim(p_evidence_ref),'') = ''
     or p_semantic_stage not in ('evidence','decision','execution') then
    raise exception 'actor, evidence and valid semantic stage are required';
  end if;

  if p_to_state in ('scanned','threat_modeled','tested') and p_semantic_stage <> 'evidence' then
    raise exception 'scan/threat-model/test transitions require evidence semantic stage';
  end if;
  if p_to_state in ('security_pass','chlom_pass','cie_pass','certified','hold','failed') and p_semantic_stage <> 'decision' then
    raise exception 'security/CHLOM/CIE/certification/HOLD/FAIL transitions require decision semantic stage';
  end if;
  if p_to_state in ('certification_pending','released') and p_semantic_stage <> 'execution' then
    raise exception 'certification-pending/release transitions require execution semantic stage';
  end if;

  if p_to_state = 'security_pass' and p_actor_ref <> v.security_decider_ref then
    raise exception 'security decision actor must match bound independent security decider';
  end if;
  if p_to_state = 'chlom_pass' and p_actor_ref <> v.chlom_authority_ref then
    raise exception 'CHLOM decision actor must match bound CHLOM authority path';
  end if;
  if p_to_state = 'cie_pass' and (not v.requires_cie or p_actor_ref <> v.cie_decider_ref) then
    raise exception 'CIE decision actor must match bound independent CIE decider';
  end if;
  if p_to_state = 'certified' and p_actor_ref <> v.certifier_ref then
    raise exception 'certification actor must match bound independent certifier';
  end if;
  if p_to_state in ('certified','released') and p_actor_ref = v.originator_ref then
    raise exception 'originator cannot certify or release own work';
  end if;
  if p_to_state = 'released' and p_actor_ref = v.certifier_ref then
    raise exception 'certifier cannot also execute release';
  end if;

  v_ok :=
    (v.current_state = 'candidate' and p_to_state in ('scanned','hold','failed')) or
    (v.current_state = 'scanned' and p_to_state in ('threat_modeled','hold','failed')) or
    (v.current_state = 'threat_modeled' and p_to_state in ('tested','hold','failed')) or
    (v.current_state = 'tested' and p_to_state in ('security_pass','hold','failed')) or
    (v.current_state = 'security_pass' and p_to_state in ('chlom_pass','hold','failed')) or
    (v.current_state = 'chlom_pass' and p_to_state in
      (case when v.requires_cie then 'cie_pass' else 'certification_pending' end,'hold','failed')) or
    (v.current_state = 'cie_pass' and p_to_state in ('certification_pending','hold','failed')) or
    (v.current_state = 'certification_pending' and p_to_state in ('certified','hold','failed')) or
    (v.current_state = 'certified' and p_to_state in ('released','hold','failed')) or
    (v.current_state = 'hold' and p_to_state in
      ('candidate','scanned','threat_modeled','tested','security_pass','chlom_pass','cie_pass','certification_pending','hold','failed'));

  if not v_ok then
    raise exception 'invalid assurance transition % -> %', v.current_state, p_to_state;
  end if;

  select canonical_dail_event_id into v_prev_dail_event_id
  from penta_runtime.security_assurance_events_v1
  where case_id = p_case_id
  order by created_at desc, event_id desc
  limit 1;

  v_event_type := case p_semantic_stage
    when 'decision' then 'security_assurance_governance_decision'
    when 'execution' then 'security_assurance_execution'
    else 'security_assurance_evidence'
  end;

  v_dail := chlom_runtime.append_dail_event(
    v_event_type,
    'security_assurance_case',
    p_case_id::text,
    coalesce(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'subject_ref', v.subject_ref,
      'subject_version', v.subject_version,
      'from_state', v.current_state,
      'to_state', p_to_state,
      'semantic_stage', p_semantic_stage,
      'evidence_ref', p_evidence_ref
    ),
    p_actor_ref,
    p_actor_did,
    p_agent_id,
    v.subject_version,
    p_case_id::text,
    v_prev_dail_event_id::text,
    coalesce(nullif(btrim(p_authority_basis),''),'ct.pentasecurity.assurance.transition.v1'),
    p_approval_id,
    'internal'
  );

  v_dail_event_id := (v_dail->>'event_id')::uuid;
  v_dail_event_hash := v_dail->>'event_hash';
  v_classification := chlom_runtime.dail_classify_event_lanes_v1(v_dail_event_id);

  select event_hash into v_readback_hash
  from chlom_runtime.dail_events
  where event_id = v_dail_event_id;

  if v_readback_hash is null or v_readback_hash <> v_dail_event_hash then
    raise exception 'canonical DAIL append/readback mismatch';
  end if;

  insert into penta_runtime.security_assurance_events_v1(
    case_id, from_state, to_state, actor_ref, evidence_ref, semantic_stage,
    canonical_dail_event_id, canonical_dail_event_hash, dail_classification, event_metadata
  ) values (
    p_case_id, v.current_state, p_to_state, p_actor_ref, p_evidence_ref, p_semantic_stage,
    v_dail_event_id, v_dail_event_hash, v_classification, coalesce(p_metadata,'{}'::jsonb)
  );

  update penta_runtime.security_assurance_cases_v1
  set current_state = p_to_state,
      updated_at = now()
  where case_id = p_case_id;

  return jsonb_build_object(
    'case_id', p_case_id,
    'from_state', v.current_state,
    'to_state', p_to_state,
    'actor_ref', p_actor_ref,
    'dail_event_id', v_dail_event_id,
    'dail_event_hash', v_dail_event_hash,
    'dail_classification', v_classification
  );
end
$$;

-- HUMAN/HYBRID/MACHINE are verified canonical DAIL systems.
-- EVIDENCE/DECISION/EXECUTION are semantic stages projected over those systems.
create or replace view penta_runtime.security_dail_semantics_v1 as
select * from (values
  ('ct.dail.human.v1'::text, 'canonical_dail_system'::text, 'human'::text, 'explainable/approval-facing continuity'::text),
  ('ct.dail.hybrid.v1', 'canonical_dail_system', 'hybrid', 'joint human+autonomous crossover relay'),
  ('ct.dail.machine.v1', 'canonical_dail_system', 'machine', 'machine execution/evidence lineage'),
  ('evidence', 'semantic_stage', null, 'observed facts/source provenance'),
  ('decision', 'semantic_stage', null, 'governed interpretation/authority decision'),
  ('execution', 'semantic_stage', null, 'material execution/outcome receipt')
) v(key, kind, lane_class, purpose);

alter table penta_runtime.security_framework_registry_v1 enable row level security;
alter table penta_runtime.security_framework_registry_v1 force row level security;
alter table penta_runtime.security_capability_bindings_v1 enable row level security;
alter table penta_runtime.security_capability_bindings_v1 force row level security;
alter table penta_runtime.security_assurance_cases_v1 enable row level security;
alter table penta_runtime.security_assurance_cases_v1 force row level security;
alter table penta_runtime.security_assurance_events_v1 enable row level security;
alter table penta_runtime.security_assurance_events_v1 force row level security;

revoke all on penta_runtime.security_framework_registry_v1,
  penta_runtime.security_capability_bindings_v1,
  penta_runtime.security_assurance_cases_v1,
  penta_runtime.security_assurance_events_v1
from public, anon, authenticated, service_role;

revoke all on function penta_runtime.security_assurance_open_case_v1(text,text,text,text,text,text,text,boolean,text,text,text,text,jsonb)
from public, anon, authenticated;
revoke all on function penta_runtime.security_assurance_transition_v1(uuid,text,text,text,text,text,text,text,text,jsonb)
from public, anon, authenticated;

grant select on penta_runtime.security_framework_registry_v1,
  penta_runtime.security_capability_bindings_v1,
  penta_runtime.security_assurance_cases_v1,
  penta_runtime.security_assurance_events_v1,
  penta_runtime.security_dail_semantics_v1
to service_role;

grant execute on function penta_runtime.security_assurance_open_case_v1(text,text,text,text,text,text,text,boolean,text,text,text,text,jsonb)
to service_role;
grant execute on function penta_runtime.security_assurance_transition_v1(uuid,text,text,text,text,text,text,text,text,jsonb)
to service_role;

insert into penta_runtime.security_framework_registry_v1(
  framework_key, framework_name, version_ref, baseline_role, implementation_status, source_ref, metadata
) values
('nist.csf','NIST Cybersecurity Framework','2.0','umbrella_governance','mapped','https://www.nist.gov/cyberframework','{}'),
('nist.800-53','NIST SP 800-53','Rev. 5 Update 1','control_catalog','mapped','https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final','{}'),
('nist.800-207','NIST SP 800-207 Zero Trust Architecture','Final','zero_trust_architecture','mapped','https://csrc.nist.gov/pubs/sp/800/207/final','{}'),
('nist.800-218','NIST SSDF SP 800-218','1.1','secure_software_development','mapped','https://csrc.nist.gov/pubs/sp/800/218/final','{}'),
('nist.800-161','NIST SP 800-161','Rev. 1 Update 1','supply_chain_risk','mapped','https://csrc.nist.gov/pubs/sp/800/161/r1/upd1/final','{}'),
('cisa.zta','CISA Zero Trust Maturity Model','2.0','maturity_benchmark','mapped','https://www.cisa.gov/resources-tools/resources/zero-trust-maturity-model','{}'),
('owasp.asvs','OWASP Application Security Verification Standard','5.0.0','application_acceptance','mapped','https://owasp.org/www-project-application-security-verification-standard/','{}'),
('owasp.api','OWASP API Security Top 10','2023','api_acceptance','mapped','https://owasp.org/API-Security/','{}'),
('cis.controls','CIS Critical Security Controls','8.1','implementation_controls','mapped','https://www.cisecurity.org/controls','{}'),
('slsa','Supply-chain Levels for Software Artifacts','1.1','software_provenance','mapped','https://slsa.dev/spec/v1.1/','{}'),
('iso.27001','ISO/IEC 27001','2022','isms_target','certified_target','https://www.iso.org/standard/27001','{"external_certification_required":true}'),
('soc2','AICPA SOC 2','current_trust_services_criteria','commercial_assurance_target','certified_target','https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2','{"external_attestation_required":true}'),
('pci.dss','PCI DSS','4.0.1','payment_scope_isolation','mapped','https://www.pcisecuritystandards.org/standards/pci-dss/','{}'),
('nist.privacy','NIST Privacy Framework','1.0 final / 1.1 IPD tracked','privacy_governance','mapped','https://www.nist.gov/privacy-framework','{"note":"Do not represent Privacy Framework 1.1 as final until NIST publishes the final release."}')
on conflict(framework_key) do update
set framework_name = excluded.framework_name,
    version_ref = excluded.version_ref,
    baseline_role = excluded.baseline_role,
    source_ref = excluded.source_ref,
    metadata = excluded.metadata,
    updated_at = now();

-- Fresh PentaCensus readback on 2026-08-30 proved PentaSecurity itself exists.
-- The requested child names are capability intents until an exact current identity/runtime is independently read back.
-- Adjacent canonical systems are reused as semantic candidates instead of inventing nonexistent penta.security.* identities.
insert into penta_runtime.security_capability_bindings_v1(
  capability_key, canonical_name, canonical_identity_key, family_key, implementation_state, alias_of, source_ref, evidence
) values
('security','PentaSecurity','penta.security','SECURITY_TRUST','existing_identity',null,'PentaCensus','{"runtime_state":"RUNTIME_PRESENT","maturity":"implemented"}'),
('pentachlom','PentaCHLOM',null,null,'build_candidate',null,'PentaCensus','{"reason":"No exact PentaCHLOM identity, routine, table or adapter runtime was found in the current census/readback; build as CHLOM Web2 interop adapter without authority inheritance."}'),
('iam','PentaIAM',null,'SECURITY_TRUST','alias_candidate','penta.identity','PentaCensus','{"candidate_components":["penta.identity","penta.auth","penta.authority"],"requires_semantic_equivalence_review":true}'),
('zero-trust','PentaZeroTrust',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"candidate_components":["penta.bound","penta.identity","penta.auth","penta.policy"],"reason":"Zero-trust orchestration identity is not currently registered."}'),
('secrets','PentaSecrets',null,'SECURITY_TRUST','alias_candidate','penta.vault','PentaCensus','{"candidate_components":["penta.vault","penta.credentials"],"requires_semantic_equivalence_review":true}'),
('keys','PentaKeys',null,'SECURITY_TRUST','alias_candidate','penta.credentials','PentaCensus','{"candidate_components":["penta.credentials","penta.sign","chlom_identity.key_registry"],"requires_semantic_equivalence_review":true}'),
('pki','PentaPKI',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"reason":"Exact PKI orchestration identity/runtime not found."}'),
('policy','PentaPolicy','penta.policy','GOVERNANCE_LEGAL','existing_identity',null,'PentaCensus','{"note":"Canonical PentaPolicy belongs to Governance & Legal; Security consumes it by contract rather than duplicating it."}'),
('guard','PentaGuard',null,'SECURITY_TRUST','alias_candidate','penta.secure','PentaCensus','{"candidate_components":["penta.secure","penta.immune","penta.candidate.guardian"],"requires_semantic_equivalence_review":true}'),
('scan','PentaScan',null,'SECURITY_TRUST','alias_candidate','penta.immune','PentaCensus','{"candidate_components":["penta.immune","penta.audit"],"requires_semantic_equivalence_review":true}'),
('sbom','PentaSBOM',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"reason":"Exact SBOM runtime identity not found."}'),
('provenance','PentaProvenance',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"candidate_components":["penta.evi-builder","penta.audit","chlom_runtime.dail_events"],"reason":"No exact PentaProvenance identity is currently registered."}'),
('threat','PentaThreat',null,'SECURITY_TRUST','alias_candidate','penta.risk','PentaCensus','{"candidate_components":["penta.risk","penta.red","penta.immune"],"requires_semantic_equivalence_review":true}'),
('siem','PentaSIEM',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"reason":"Exact SIEM normalization/correlation identity/runtime not found."}'),
('soc','PentaSOC',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"reason":"Exact SOC orchestration identity/runtime not found."}'),
('incident','PentaIncident',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"candidate_components":["penta.security","public.penta_incident_control_tick_v1"],"reason":"Incident control exists, but no exact PentaIncident identity is currently registered."}'),
('forensics','PentaForensics',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"reason":"Exact forensics evidence-custody runtime identity not found."}'),
('vuln','PentaVuln',null,'SECURITY_TRUST','alias_candidate','penta.immune','PentaCensus','{"candidate_components":["penta.immune","penta.audit"],"requires_semantic_equivalence_review":true}'),
('patch','PentaPatch','penta.patch','TRANSPORT_PRIMITIVES','existing_identity',null,'PentaCensus','{"note":"Canonical PentaPatch exists as a transport primitive and is not duplicated inside Security."}'),
('red','PentaRed','penta.red','SECURITY_TRUST','existing_identity',null,'PentaCensus','{"runtime_state":"INSTITUTIONAL_ONLY","authority":"sandbox-only adversarial simulation"}'),
('purple','PentaPurple',null,'SECURITY_TRUST','build_candidate',null,'PentaCensus','{"candidate_components":["penta.red","penta.blue"],"reason":"Red/Blue identities exist; Purple orchestration identity not found."}'),
('dr','PentaDR',null,'RESILIENCE_CONTINUITY','build_candidate',null,'PentaCensus','{"candidate_components":["penta.heartbeat","penta.bc"],"reason":"Continuity capabilities exist; exact PentaDR identity/runtime not found."}'),
('bc','PentaBC','penta.bc','PROVISIONAL_UNASSIGNED','existing_identity',null,'PentaCensus','{"runtime_state":"INSTITUTIONAL_ONLY","activation_state":"HOLD_FAMILY","note":"Preserve existing identity; do not silently re-home it without family governance."}')
on conflict(capability_key) do update
set canonical_name = excluded.canonical_name,
    canonical_identity_key = excluded.canonical_identity_key,
    family_key = excluded.family_key,
    implementation_state = excluded.implementation_state,
    alias_of = excluded.alias_of,
    source_ref = excluded.source_ref,
    evidence = excluded.evidence,
    updated_at = now();
