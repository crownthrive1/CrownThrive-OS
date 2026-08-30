create table if not exists integration_control.penta_family_certification_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  family_key text not null,
  assurance_certification_id text not null,
  standard_ref text not null,
  disposition text not null,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (family_key, assurance_certification_id)
);

create or replace function integration_control.penta_family_certification_receipts_append_only_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
begin
  raise exception 'PENTA_FAMILY_CERTIFICATION_RECEIPTS_APPEND_ONLY';
end
$$;

drop trigger if exists penta_family_certification_receipts_append_only_v1
  on integration_control.penta_family_certification_receipts_v1;
create trigger penta_family_certification_receipts_append_only_v1
before update or delete on integration_control.penta_family_certification_receipts_v1
for each row execute function integration_control.penta_family_certification_receipts_append_only_v1();

do $$
declare
  v_def text;
  v_new text;
begin
  select pg_get_functiondef('integration_control.penta_identity_refresh_v1(text)'::regprocedure)
    into v_def;

  v_new := replace(
    v_def,
    '''certification:pending''',
    '''certification:''||lower(replace(coalesce((select certification_state from integration_control.penta_family_runtime_v1 where family_key=r.family_key),''PENDING''),''_'',''-''))'
  );

  v_new := replace(
    v_new,
    'certification_state=excluded.certification_state',
    'certification_state=case when integration_control.penta_family_runtime_v1.certification_state<>''PENDING'' then integration_control.penta_family_runtime_v1.certification_state else excluded.certification_state end'
  );

  if v_new = v_def then
    raise exception 'PENTA_FAMILY_CERTIFICATION_REFRESH_PATCH_NOT_APPLIED';
  end if;

  execute v_new;
end
$$;

create or replace function integration_control.penta_family_certify_v1(
  p_family_key text,
  p_assurance_certification_id text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, public, extensions
as $$
declare
  v_key text := upper(btrim(p_family_key));
  v_family integration_control.penta_family_runtime_v1%rowtype;
  v_cert public.penta_assure_certifications%rowtype;
  v_identity_key text;
  v_before jsonb;
  v_after jsonb;
  v_event_payload jsonb;
  v_event_sha text;
  v_receipt_id uuid;
begin
  select * into strict v_family
  from integration_control.penta_family_runtime_v1
  where family_key = v_key
  for update;

  select * into strict v_cert
  from public.penta_assure_certifications
  where certification_id = p_assurance_certification_id;

  if v_cert.subject_ref <> 'penta-family:' || v_key then
    raise exception 'PENTA_FAMILY_CERT_SUBJECT_MISMATCH';
  end if;
  if v_cert.standard_ref <> 'ct.penta.family.router-cert.v1' then
    raise exception 'PENTA_FAMILY_CERT_STANDARD_MISMATCH';
  end if;
  if v_cert.disposition <> 'certified'
     or v_cert.independence_state <> 'separation_of_duties_satisfied' then
    raise exception 'PENTA_FAMILY_CERT_NOT_INDEPENDENTLY_CERTIFIED';
  end if;
  if v_cert.risk_class = 'D3' then
    raise exception 'PENTA_FAMILY_CERT_D3_HUMAN_RESERVED';
  end if;
  if v_cert.expires_at is not null and v_cert.expires_at <= now() then
    raise exception 'PENTA_FAMILY_CERT_EXPIRED';
  end if;

  if v_family.runtime_state <> 'IMPLEMENTED_REGISTRY_ROUTER'
     or v_family.activation_state <> 'ACTIVE_FAIL_CLOSED'
     or coalesce(v_family.metadata->>'dispatch_authority','') <> 'NONE_FROM_ROUTER' then
    raise exception 'PENTA_FAMILY_ROUTER_BOUNDARY_NOT_SATISFIED';
  end if;

  v_identity_key := 'penta.family.' || lower(replace(v_key,'_','-'));
  v_before := to_jsonb(v_family);

  insert into integration_control.penta_family_certification_receipts_v1(
    family_key, assurance_certification_id, standard_ref, disposition, evidence
  )
  values(
    v_key,
    v_cert.certification_id,
    v_cert.standard_ref,
    'CERTIFIED_COORDINATION_ONLY',
    jsonb_build_object(
      'risk_class', v_cert.risk_class,
      'independence_state', v_cert.independence_state,
      'assurance_evidence_refs', v_cert.evidence_refs,
      'assurance_checks', v_cert.checks,
      'member_count', v_family.member_count,
      'runtime_state', v_family.runtime_state,
      'activation_state', v_family.activation_state,
      'dispatch_authority', v_family.metadata->>'dispatch_authority',
      'authority_expansion', false
    )
  )
  on conflict (family_key, assurance_certification_id) do nothing
  returning receipt_id into v_receipt_id;

  update integration_control.penta_family_runtime_v1
  set certification_state = 'CERTIFIED_COORDINATION_ONLY',
      labels = array_replace(labels,'certification:pending','certification:certified-coordination-only'),
      metadata = metadata || jsonb_build_object(
        'certification_id', v_cert.certification_id,
        'certification_standard', v_cert.standard_ref,
        'certified_at', coalesce(v_cert.certified_at, now()),
        'certification_scope', 'coordination_router_only',
        'authority_expansion', false
      ),
      updated_at = now()
  where family_key = v_key
  returning jsonb_build_object(
    'family_key',family_key,
    'canonical_name',canonical_name,
    'member_count',member_count,
    'runtime_state',runtime_state,
    'activation_state',activation_state,
    'certification_state',certification_state,
    'labels',to_jsonb(labels),
    'metadata',metadata
  ) into v_after;

  update integration_control.penta_identity_registry_v1
  set labels = array_replace(labels,'certification:pending','certification:certified-coordination-only'),
      metadata = metadata || jsonb_build_object(
        'family_certification_id', v_cert.certification_id,
        'family_certification_scope', 'coordination_router_only',
        'authority_expansion', false
      ),
      updated_at = now()
  where identity_key = v_identity_key
    and current
    and identity_class = 'FAMILY';

  update integration_control.penta_identity_labels_v1
  set active = false, last_seen_at = now()
  where identity_key = v_identity_key
    and label_class = 'certification';

  insert into integration_control.penta_identity_labels_v1(
    identity_key,label,label_class,source_ref,active
  )
  values(
    v_identity_key,
    'certification:certified-coordination-only',
    'certification',
    'assure:' || v_cert.certification_id,
    true
  )
  on conflict(identity_key,label) do update
  set active = true,
      source_ref = excluded.source_ref,
      last_seen_at = now();

  v_event_payload := jsonb_build_object(
    'family_key', v_key,
    'assurance_certification_id', v_cert.certification_id,
    'standard_ref', v_cert.standard_ref,
    'disposition', 'CERTIFIED_COORDINATION_ONLY',
    'authority_expansion', false
  );
  v_event_sha := encode(extensions.digest(convert_to(v_event_payload::text,'UTF8'),'sha256'),'hex');

  insert into integration_control.penta_identity_history_v1(
    identity_key,event_type,before_state,after_state,source_ref,source_sha256,event_sha256
  )
  values(
    v_identity_key,
    'FAMILY_CERTIFICATION',
    v_before,
    v_after,
    'assure:' || v_cert.certification_id,
    null,
    v_event_sha
  );

  return jsonb_build_object(
    'family_key', v_key,
    'certification_state', 'CERTIFIED_COORDINATION_ONLY',
    'assurance_certification_id', v_cert.certification_id,
    'receipt_id', v_receipt_id,
    'authority_expansion', false,
    'dispatch_authority', 'NONE_FROM_ROUTER',
    'at', now()
  );
exception
  when no_data_found then
    raise exception 'PENTA_FAMILY_OR_ASSURANCE_CERT_NOT_FOUND';
end
$$;

revoke all on function integration_control.penta_family_certify_v1(text,text) from public;
grant execute on function integration_control.penta_family_certify_v1(text,text) to service_role;
