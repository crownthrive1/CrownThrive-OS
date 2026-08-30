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
  family_key text not null default 'SECURITY_TRUST',
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
  security_decider_ref text,
  certifier_ref text,
  chlom_authority_ref text,
  evidence_digest text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(subject_ref, subject_version)
);

create table if not exists penta_runtime.security_assurance_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  case_id uuid not null references penta_runtime.security_assurance_cases_v1(case_id) on delete restrict,
  from_state text,
  to_state text not null,
  actor_ref text not null,
  evidence_ref text not null,
  dail_lane text not null check (dail_lane in ('human','hybrid','machine')),
  semantic_stage text not null check (semantic_stage in ('evidence','decision','execution')),
  event_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function penta_runtime.security_assurance_events_immutable_v1()
returns trigger
language plpgsql
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

create or replace function penta_runtime.security_assurance_transition_v1(
  p_case_id uuid,
  p_to_state text,
  p_actor_ref text,
  p_evidence_ref text,
  p_dail_lane text,
  p_semantic_stage text,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
as $$
declare
  v penta_runtime.security_assurance_cases_v1%rowtype;
  ok boolean := false;
begin
  select * into v
  from penta_runtime.security_assurance_cases_v1
  where case_id = p_case_id
  for update;

  if not found then
    raise exception 'unknown assurance case';
  end if;
  if p_actor_ref is null or btrim(p_actor_ref) = '' or p_evidence_ref is null or btrim(p_evidence_ref) = '' then
    raise exception 'actor and evidence required';
  end if;
  if p_dail_lane not in ('human','hybrid','machine') or p_semantic_stage not in ('evidence','decision','execution') then
    raise exception 'invalid DAIL lane or semantic stage';
  end if;
  if p_to_state in ('certified','released') and p_actor_ref = v.originator_ref then
    raise exception 'originator cannot certify or release own work';
  end if;
  if p_to_state = 'certified' and v.certifier_ref is null then
    raise exception 'independent certifier binding required before certification';
  end if;
  if p_to_state = 'certified' and v.certifier_ref <> p_actor_ref then
    raise exception 'certification actor must match bound independent certifier';
  end if;
  if p_to_state = 'certified' and v.certifier_ref = v.originator_ref then
    raise exception 'originator cannot be bound independent certifier';
  end if;

  ok :=
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

  if not ok then
    raise exception 'invalid assurance transition % -> %', v.current_state, p_to_state;
  end if;

  insert into penta_runtime.security_assurance_events_v1(
    case_id, from_state, to_state, actor_ref, evidence_ref, dail_lane, semantic_stage, event_metadata
  ) values (
    p_case_id, v.current_state, p_to_state, p_actor_ref, p_evidence_ref,
    p_dail_lane, p_semantic_stage, coalesce(p_metadata, '{}'::jsonb)
  );

  update penta_runtime.security_assurance_cases_v1
  set current_state = p_to_state,
      updated_at = now(),
      security_decider_ref = case when p_to_state = 'security_pass' then p_actor_ref else security_decider_ref end,
      chlom_authority_ref = case when p_to_state = 'chlom_pass' then p_actor_ref else chlom_authority_ref end
  where case_id = p_case_id;

  return jsonb_build_object(
    'case_id', p_case_id,
    'from_state', v.current_state,
    'to_state', p_to_state,
    'actor_ref', p_actor_ref
  );
end
$$;

-- HUMAN/HYBRID/MACHINE are the verified canonical DAIL lanes.
-- EVIDENCE/DECISION/EXECUTION are semantic stages routed over those lanes, not replacement ledgers.
create or replace view penta_runtime.security_dail_semantics_v1 as
select * from (values
  ('human'::text, 'canonical_dail_lane'::text, 'explainable/approval-facing continuity'::text),
  ('hybrid', 'canonical_dail_lane', 'joint human+autonomous relay'),
  ('machine', 'canonical_dail_lane', 'machine execution/evidence lineage'),
  ('evidence', 'semantic_stage', 'observed facts/source provenance'),
  ('decision', 'semantic_stage', 'governed interpretation/authority decision'),
  ('execution', 'semantic_stage', 'material execution/outcome receipt')
) v(key, kind, purpose);

revoke all on penta_runtime.security_framework_registry_v1,
  penta_runtime.security_capability_bindings_v1,
  penta_runtime.security_assurance_cases_v1,
  penta_runtime.security_assurance_events_v1
from public, anon, authenticated;
revoke all on function penta_runtime.security_assurance_transition_v1(uuid,text,text,text,text,text,jsonb)
from public, anon, authenticated;

grant select, insert, update on penta_runtime.security_framework_registry_v1,
  penta_runtime.security_capability_bindings_v1,
  penta_runtime.security_assurance_cases_v1
to service_role;
grant select, insert on penta_runtime.security_assurance_events_v1 to service_role;
grant select on penta_runtime.security_dail_semantics_v1 to service_role;
grant execute on function penta_runtime.security_assurance_transition_v1(uuid,text,text,text,text,text,jsonb)
to service_role;

insert into penta_runtime.security_framework_registry_v1(
  framework_key, framework_name, version_ref, baseline_role, implementation_status, source_ref, metadata
) values
('nist.csf','NIST Cybersecurity Framework','2.0','umbrella_governance','mapped','https://www.nist.gov/cyberframework','{}'),
('nist.800-53','NIST SP 800-53','Rev. 5','control_catalog','mapped','https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final','{}'),
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
('nist.privacy','NIST Privacy Framework','1.0','privacy_governance','mapped','https://www.nist.gov/privacy-framework','{}')
on conflict(framework_key) do update
set framework_name = excluded.framework_name,
    version_ref = excluded.version_ref,
    baseline_role = excluded.baseline_role,
    source_ref = excluded.source_ref,
    updated_at = now();

insert into penta_runtime.security_capability_bindings_v1(
  capability_key, canonical_name, canonical_identity_key, implementation_state, alias_of, source_ref, evidence
) values
('security','PentaSecurity','penta.security','existing_identity',null,'PentaCensus','{"family":"SECURITY_TRUST"}'),
('iam','PentaIAM','penta.security.iam','existing_identity',null,'PentaCensus','{}'),
('zero-trust','PentaZeroTrust','penta.security.zero-trust','existing_identity',null,'PentaCensus','{}'),
('secrets','PentaSecrets','penta.security.secrets','existing_identity',null,'PentaCensus','{}'),
('pki','PentaPKI','penta.security.pki','existing_identity',null,'PentaCensus','{}'),
('policy','PentaPolicy','penta.security.policy','existing_identity',null,'PentaCensus','{}'),
('guard','PentaGuard','penta.security.guard','existing_identity',null,'PentaCensus','{}'),
('scan','PentaScan','penta.security.scan','existing_identity',null,'PentaCensus','{}'),
('threat','PentaThreat','penta.security.threat','existing_identity',null,'PentaCensus','{}'),
('siem','PentaSIEM','penta.security.siem','existing_identity',null,'PentaCensus','{}'),
('soc','PentaSOC','penta.security.soc','existing_identity',null,'PentaCensus','{}'),
('vuln','PentaVuln','penta.security.vuln','existing_identity',null,'PentaCensus','{}'),
('red','PentaRed','penta.security.red','existing_identity',null,'PentaCensus','{}'),
('keys','PentaKeys',null,'alias_candidate','penta.security.encryption','PentaCensus','{"requires_semantic_equivalence_review":true}'),
('sbom','PentaSBOM',null,'gap_hold',null,'PentaCensus','{"reason":"exact canonical runtime not yet verified"}'),
('provenance','PentaProvenance',null,'alias_candidate','penta.provenance-ledger','PentaCensus','{"requires_semantic_equivalence_review":true}'),
('incident','PentaIncident',null,'alias_candidate','penta.micro.incident-route','PentaCensus','{"requires_semantic_equivalence_review":true}'),
('forensics','PentaForensics',null,'gap_hold',null,'PentaCensus','{"reason":"exact canonical runtime not yet verified"}'),
('patch','PentaPatch',null,'gap_hold',null,'PentaCensus','{"reason":"exact canonical runtime not yet verified"}'),
('purple','PentaPurple',null,'build_candidate',null,'PentaCensus','{"reason":"blue/red assurance exists; purple orchestration identity not verified"}'),
('dr','PentaDR',null,'gap_hold',null,'PentaCensus','{"reason":"resilience/continuity exists; exact disaster-recovery identity not verified"}')
on conflict(capability_key) do update
set canonical_name = excluded.canonical_name,
    canonical_identity_key = coalesce(excluded.canonical_identity_key, penta_runtime.security_capability_bindings_v1.canonical_identity_key),
    implementation_state = excluded.implementation_state,
    alias_of = excluded.alias_of,
    source_ref = excluded.source_ref,
    evidence = excluded.evidence,
    updated_at = now();
