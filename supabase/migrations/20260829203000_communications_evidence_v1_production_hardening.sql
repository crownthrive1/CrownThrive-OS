begin;

alter table communications_evidence.messages_v1
  add column if not exists source_fidelity text not null default 'CANONICALIZED',
  add column if not exists provider_delete_state text not null default 'NONE';

alter table communications_evidence.restore_receipts_v1
  add column if not exists verification_mode text not null default 'INDEPENDENT',
  add column if not exists independence_verified boolean not null default false,
  add column if not exists independence_evidence_ref text;

alter table communications_evidence.certifications_v1
  add column if not exists certification_mode text not null default 'INDEPENDENT',
  add column if not exists independence_verified boolean not null default false,
  add column if not exists independence_evidence_ref text;

alter table communications_evidence.provider_purge_receipts_v1
  add column if not exists delete_semantics text not null default 'UNKNOWN',
  add column if not exists provider_trash_verified boolean not null default false,
  add column if not exists provider_hard_absence_verified boolean not null default false;

create table if not exists communications_evidence.census_receipts_v1 (
  census_receipt_id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null references communications_evidence.messages_v1(evidence_id) on delete restrict,
  census_scope_ref text not null,
  provider_discovered boolean not null default false,
  canonical_accounted boolean not null default false,
  unexplained_variance integer not null default 0 check (unexplained_variance >= 0),
  evidence_ref text not null,
  recorded_by text not null,
  recorded_at timestamptz not null default now(),
  unique(evidence_id, census_scope_ref)
);

alter table communications_evidence.census_receipts_v1 enable row level security;
revoke all on communications_evidence.census_receipts_v1 from public, anon, authenticated;
grant select, insert, update on communications_evidence.census_receipts_v1 to service_role;

DO $$ begin
  if not exists (select 1 from pg_constraint where conname='ce_messages_source_fidelity_ck') then
    alter table communications_evidence.messages_v1 add constraint ce_messages_source_fidelity_ck check (source_fidelity in ('PROVIDER_RAW','CANONICALIZED','PARTIAL'));
  end if;
  if not exists (select 1 from pg_constraint where conname='ce_messages_provider_delete_state_ck') then
    alter table communications_evidence.messages_v1 add constraint ce_messages_provider_delete_state_ck check (provider_delete_state in ('NONE','TRASHED','HARD_DELETED'));
  end if;
  if not exists (select 1 from pg_constraint where conname='ce_restore_verification_mode_ck') then
    alter table communications_evidence.restore_receipts_v1 add constraint ce_restore_verification_mode_ck check (verification_mode in ('INDEPENDENT','FOUNDER_AUTHORIZED_WAVE1_SELF_TEST'));
  end if;
  if not exists (select 1 from pg_constraint where conname='ce_certification_mode_ck') then
    alter table communications_evidence.certifications_v1 add constraint ce_certification_mode_ck check (certification_mode in ('INDEPENDENT','FOUNDER_AUTHORIZED_WAVE1_SELF_TEST'));
  end if;
  if not exists (select 1 from pg_constraint where conname='ce_delete_semantics_ck') then
    alter table communications_evidence.provider_purge_receipts_v1 add constraint ce_delete_semantics_ck check (delete_semantics in ('UNKNOWN','SOFT_DELETE_TRASH','HARD_DELETE'));
  end if;
end $$;

create unique index if not exists ce_single_founder_wave1_self_test_pass_idx
  on communications_evidence.certifications_v1 ((certification_mode))
  where certification_mode='FOUNDER_AUTHORIZED_WAVE1_SELF_TEST' and verdict='PASS';

create index if not exists ce_census_evidence_idx on communications_evidence.census_receipts_v1(evidence_id, unexplained_variance);

create or replace function communications_evidence.coverage_v1(p_wave_ref text default 'wave1')
returns jsonb
language sql
security definer
set search_path = pg_catalog, communications_evidence
as $$
with x as (
  select
    count(*) as discovered,
    count(*) filter (where m.excluded) as excluded,
    count(*) filter (where m.lifecycle_state like 'HOLD_%' or m.operational_plane_state like 'HOLD_%') as held,
    count(*) filter (where m.evidence_fingerprint_sha256 is not null) as fingerprinted,
    count(*) filter (where m.dail_readback_verified) as dail_verified,
    count(*) filter (where m.purge_eligible_at is not null) as purge_eligible,
    count(*) filter (where m.provider_delete_state='TRASHED') as trashed,
    count(*) filter (where m.provider_delete_state='HARD_DELETED') as hard_deleted,
    count(*) filter (where exists (
      select 1 from communications_evidence.census_receipts_v1 c
       where c.evidence_id=m.evidence_id and c.provider_discovered and c.canonical_accounted and c.unexplained_variance=0
    )) as accounted
  from communications_evidence.messages_v1 m
  where m.wave_ref=p_wave_ref
)
select to_jsonb(x) || jsonb_build_object('wave_ref',p_wave_ref,'unexplained_variance',greatest(x.discovered-x.accounted,0)) from x
$$;

create or replace function communications_evidence.evaluate_purge_v1(p_evidence_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, communications_evidence
as $$
declare
  v communications_evidence.messages_v1%rowtype;
  v_missing_attachments int; v_hot_machine int; v_warm_hybrid int; v_cold_readable int;
  v_restore_independent int; v_restore_canary int; v_open_conflicts int;
  v_cert_independent int; v_cert_canary int; v_census_clear int; v_core_classification int;
  v_canary boolean; v_eligible boolean; v_cert_path text;
begin
  select * into v from communications_evidence.messages_v1 where evidence_id=p_evidence_id;
  if not found then raise exception 'evidence_not_found'; end if;
  v_canary := v.wave_ref='wave1-canary';
  select count(*) into v_missing_attachments from communications_evidence.attachments_v1 where parent_evidence_id=p_evidence_id and required_for_parent_purge and not (acquired and hash_verified and restore_verified);
  select count(*) into v_hot_machine from communications_evidence.custody_receipts_v1 where evidence_id=p_evidence_id and temperature='HOT' and view_class='MACHINE' and readback_verified and custody_verified;
  select count(*) into v_warm_hybrid from communications_evidence.custody_receipts_v1 where evidence_id=p_evidence_id and temperature='WARM' and view_class='HYBRID' and readback_verified and custody_verified;
  select count(*) into v_cold_readable from communications_evidence.custody_receipts_v1 where evidence_id=p_evidence_id and temperature='COLD' and view_class in ('HUMAN','HYBRID') and readback_verified and custody_verified;
  select count(*) into v_restore_independent from communications_evidence.restore_receipts_v1 where evidence_id=p_evidence_id and result='PASS' and manifest_hash_verified and body_or_source_verified and attachments_verified and reconstruction_verified and verification_mode='INDEPENDENT' and independence_verified;
  select count(*) into v_restore_canary from communications_evidence.restore_receipts_v1 where evidence_id=p_evidence_id and result='PASS' and manifest_hash_verified and body_or_source_verified and attachments_verified and reconstruction_verified and verification_mode='FOUNDER_AUTHORIZED_WAVE1_SELF_TEST';
  select count(*) into v_open_conflicts from communications_evidence.reconciliation_links_v1 where evidence_id=p_evidence_id and relation_type='CONTRADICTS' and not resolved;
  select count(*) into v_cert_independent from communications_evidence.certifications_v1 where evidence_id=p_evidence_id and certification_kind='PURGE_ELIGIBILITY' and verdict='PASS' and certification_mode='INDEPENDENT' and independence_verified and certifier_actor is distinct from v.originating_actor;
  select count(*) into v_cert_canary from communications_evidence.certifications_v1 where evidence_id=p_evidence_id and certification_kind='PURGE_ELIGIBILITY' and verdict='PASS' and certification_mode='FOUNDER_AUTHORIZED_WAVE1_SELF_TEST';
  select count(*) into v_census_clear from communications_evidence.census_receipts_v1 where evidence_id=p_evidence_id and provider_discovered and canonical_accounted and unexplained_variance=0;
  select count(*) into v_core_classification from communications_evidence.classifications_v1 where evidence_id=p_evidence_id and dimension='evidence_type';
  v_cert_path := case when v_cert_independent>0 and v_restore_independent>0 then 'INDEPENDENT' when v_canary and v_cert_canary>0 and v_restore_canary>0 then 'FOUNDER_AUTHORIZED_WAVE1_SELF_TEST' else 'NONE' end;
  v_eligible := not v.excluded and v.source_object_ref is not null and v.source_fidelity in ('PROVIDER_RAW','CANONICALIZED') and v.canonical_headers_sha256 is not null and v.body_sha256 is not null and v.manifest_sha256 is not null and v.evidence_fingerprint_sha256 is not null and v.acquired_at is not null and v.normalized_at is not null and v.classified_at is not null and v_core_classification>0 and v.chlom_bound and v.dail_bound and v.dail_readback_verified and v_missing_attachments=0 and v_hot_machine>0 and v_warm_hybrid>0 and v_cold_readable>0 and ((v_restore_independent>0) or (v_canary and v_restore_canary>0)) and v_open_conflicts=0 and not v.legal_hold and not v.compliance_hold and (v.retain_until is null or v.retain_until <= now()) and v.reconciled_at is not null and v_census_clear>0 and ((v_cert_independent>0) or (v_canary and v_cert_canary>0));
  if v_eligible and v.lifecycle_state not in ('PROVIDER_TRASHED','PROVIDER_DELETED','DELETION_VERIFIED') then update communications_evidence.messages_v1 set lifecycle_state='PURGE_ELIGIBLE',purge_eligible_at=coalesce(purge_eligible_at,now()),updated_at=now() where evidence_id=p_evidence_id; end if;
  return jsonb_build_object('evidence_id',p_evidence_id,'eligible',v_eligible,'certification_path',v_cert_path,'independent_certification',v_cert_path='INDEPENDENT','founder_authorized_canary_self_test',v_cert_path='FOUNDER_AUTHORIZED_WAVE1_SELF_TEST','missing_attachments',v_missing_attachments,'hot_machine_verified',v_hot_machine>0,'warm_hybrid_verified',v_warm_hybrid>0,'cold_readable_verified',v_cold_readable>0,'restore_independent_verified',v_restore_independent>0,'restore_canary_verified',v_restore_canary>0,'core_classification_verified',v_core_classification>0,'census_accounted',v_census_clear>0,'open_conflicts',v_open_conflicts,'retention_clear',(v.retain_until is null or v.retain_until<=now()),'legal_compliance_clear',not v.legal_hold and not v.compliance_hold,'dail_verified',v.dail_bound and v.dail_readback_verified);
end $$;

create or replace function communications_evidence.record_provider_delete_receipt_v1(p_evidence_id uuid,p_provider_delete_request_ref text,p_actor_ref text,p_actor_did text,p_agent_id text,p_authority_basis text,p_delete_semantics text,p_provider_trash_verified boolean,p_provider_hard_absence_verified boolean)
returns jsonb language plpgsql security definer set search_path=pg_catalog,communications_evidence,chlom_runtime as $$
declare v communications_evidence.messages_v1%rowtype; e jsonb; r jsonb; v_event_id uuid; v_seq bigint;
begin
  if p_delete_semantics not in ('SOFT_DELETE_TRASH','HARD_DELETE') then raise exception 'invalid_delete_semantics'; end if;
  select * into v from communications_evidence.messages_v1 where evidence_id=p_evidence_id for update; if not found then raise exception 'evidence_not_found'; end if;
  e:=communications_evidence.evaluate_purge_v1(p_evidence_id); if coalesce((e->>'eligible')::boolean,false) is not true then raise exception 'purge_not_eligible'; end if;
  if p_delete_semantics='SOFT_DELETE_TRASH' and p_provider_trash_verified is not true then raise exception 'trash_readback_required'; end if;
  if p_delete_semantics='HARD_DELETE' and p_provider_hard_absence_verified is not true then raise exception 'hard_absence_readback_required'; end if;
  r:=chlom_runtime.append_dail_event(case when p_delete_semantics='HARD_DELETE' then 'COMMUNICATION_PROVIDER_HARD_DELETED' else 'COMMUNICATION_PROVIDER_TRASHED' end,'communications_evidence',p_evidence_id::text,jsonb_build_object('contract_ref',v.contract_ref,'provider',v.provider,'provider_message_id_sha256',encode(extensions.digest(v.provider_message_id,'sha256'),'hex'),'fingerprint_sha256',v.evidence_fingerprint_sha256,'delete_semantics',p_delete_semantics,'provider_trash_verified',p_provider_trash_verified,'provider_hard_absence_verified',p_provider_hard_absence_verified),p_actor_ref,p_actor_did,p_agent_id,'1.0.1',p_evidence_id::text,v.dail_event_id::text,p_authority_basis,null,'internal');
  v_event_id:=nullif(r->>'event_id','')::uuid; if v_event_id is null then raise exception 'terminal_dail_append_missing_event_id'; end if; select sequence_id into v_seq from chlom_runtime.dail_events where event_id=v_event_id; if v_seq is null then raise exception 'terminal_dail_readback_failed'; end if;
  insert into communications_evidence.provider_purge_receipts_v1(evidence_id,provider_delete_request_ref,delete_requested_by,provider_absence_verified,provider_trash_verified,provider_hard_absence_verified,delete_semantics,canonical_evidence_present_verified,fingerprint_verified,chlom_dail_lineage_verified,retrieval_verified,terminal_dail_event_id,terminal_dail_sequence_id,verified_at) values(p_evidence_id,p_provider_delete_request_ref,p_actor_ref,p_provider_hard_absence_verified,p_provider_trash_verified,p_provider_hard_absence_verified,p_delete_semantics,true,true,true,true,v_event_id,v_seq,now()) on conflict(evidence_id) do update set provider_delete_request_ref=excluded.provider_delete_request_ref,delete_requested_by=excluded.delete_requested_by,provider_absence_verified=excluded.provider_absence_verified,provider_trash_verified=excluded.provider_trash_verified,provider_hard_absence_verified=excluded.provider_hard_absence_verified,delete_semantics=excluded.delete_semantics,canonical_evidence_present_verified=excluded.canonical_evidence_present_verified,fingerprint_verified=excluded.fingerprint_verified,chlom_dail_lineage_verified=excluded.chlom_dail_lineage_verified,retrieval_verified=excluded.retrieval_verified,terminal_dail_event_id=excluded.terminal_dail_event_id,terminal_dail_sequence_id=excluded.terminal_dail_sequence_id,verified_at=excluded.verified_at;
  update communications_evidence.messages_v1 set provider_deleted_at=coalesce(provider_deleted_at,now()),provider_delete_state=case when p_delete_semantics='HARD_DELETE' then 'HARD_DELETED' else 'TRASHED' end,lifecycle_state=case when p_delete_semantics='HARD_DELETE' then 'DELETION_VERIFIED' else 'PROVIDER_TRASHED' end,deletion_verified_at=case when p_delete_semantics='HARD_DELETE' then coalesce(deletion_verified_at,now()) else deletion_verified_at end,updated_at=now() where evidence_id=p_evidence_id;
  return jsonb_build_object('evidence_id',p_evidence_id,'delete_semantics',p_delete_semantics,'provider_trash_verified',p_provider_trash_verified,'provider_hard_absence_verified',p_provider_hard_absence_verified,'terminal_dail_event_id',v_event_id,'terminal_dail_sequence_id',v_seq);
end $$;

revoke all on function communications_evidence.coverage_v1(text) from public,anon,authenticated;
revoke all on function communications_evidence.evaluate_purge_v1(uuid) from public,anon,authenticated;
revoke all on function communications_evidence.record_provider_delete_receipt_v1(uuid,text,text,text,text,text,text,boolean,boolean) from public,anon,authenticated;
grant execute on function communications_evidence.coverage_v1(text) to service_role;
grant execute on function communications_evidence.evaluate_purge_v1(uuid) to service_role;
grant execute on function communications_evidence.record_provider_delete_receipt_v1(uuid,text,text,text,text,text,text,boolean,boolean) to service_role;

commit;
