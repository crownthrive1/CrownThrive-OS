create table if not exists penta_os20.release_projection_targets (
  id uuid primary key default gen_random_uuid(),
  target_key text not null unique,
  target_type text not null check (target_type in ('github_tabs','pentadocs','github_release','google_drive')),
  provider_ref text not null,
  update_mode text not null default 'managed_block_only' check (update_mode in ('managed_block_only','release_asset_set')),
  status text not null default 'active' check (status in ('active','hold','retired')),
  required boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_os20.release_projection_queue (
  id uuid primary key default gen_random_uuid(),
  release_version text not null,
  external_release_tag text,
  target_id uuid not null references penta_os20.release_projection_targets(id),
  payload jsonb not null default '{}'::jsonb,
  payload_hash text not null,
  status text not null default 'queued' check (status in ('queued','pending_provider','synchronized','hold','failed')),
  attempts integer not null default 0 check (attempts >= 0),
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  synchronized_at timestamptz,
  unique (release_version,target_id,payload_hash)
);

alter table penta_os20.release_projection_targets enable row level security;
alter table penta_os20.release_projection_queue enable row level security;
revoke all on penta_os20.release_projection_targets from anon, authenticated;
revoke all on penta_os20.release_projection_queue from anon, authenticated;
grant select,insert,update,delete on penta_os20.release_projection_targets to service_role;
grant select,insert,update,delete on penta_os20.release_projection_queue to service_role;

create or replace function penta_os20.enqueue_release_projection(
  p_release_version text,
  p_external_release_tag text,
  p_payload jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security invoker
set search_path = penta_os20, pg_temp
as $$
declare
  v_target penta_os20.release_projection_targets%rowtype;
  v_hash text;
  v_count integer := 0;
begin
  if coalesce(trim(p_release_version),'') = '' then
    raise exception 'release_version_required';
  end if;
  v_hash := encode(digest(coalesce(p_payload,'{}'::jsonb)::text,'sha256'),'hex');
  for v_target in select * from penta_os20.release_projection_targets where status='active' loop
    insert into penta_os20.release_projection_queue(release_version,external_release_tag,target_id,payload,payload_hash,status)
    values (p_release_version,p_external_release_tag,v_target.id,coalesce(p_payload,'{}'::jsonb),v_hash,'queued')
    on conflict (release_version,target_id,payload_hash) do update
      set external_release_tag=excluded.external_release_tag, updated_at=now();
    v_count := v_count + 1;
  end loop;
  perform penta_os20.record_receipt('release_projection_enqueued','PentaRelease','release_projection',null,
    jsonb_build_object('release_version',p_release_version,'external_release_tag',p_external_release_tag,'target_count',v_count,'payload_hash',v_hash));
  return jsonb_build_object('release_version',p_release_version,'external_release_tag',p_external_release_tag,'target_count',v_count,'payload_hash',v_hash);
end;
$$;

create or replace function penta_os20.settle_release_projection(
  p_queue_id uuid,
  p_status text,
  p_evidence jsonb default '{}'::jsonb,
  p_error text default null
) returns jsonb
language plpgsql
security invoker
set search_path = penta_os20, pg_temp
as $$
declare
  v_row penta_os20.release_projection_queue%rowtype;
  v_target_key text;
begin
  if p_status not in ('pending_provider','synchronized','hold','failed') then
    raise exception 'invalid_projection_status';
  end if;
  update penta_os20.release_projection_queue
     set status=p_status,
         attempts=attempts+1,
         last_error=p_error,
         updated_at=now(),
         synchronized_at=case when p_status='synchronized' then now() else synchronized_at end
   where id=p_queue_id
   returning * into v_row;
  if v_row.id is null then raise exception 'projection_queue_not_found'; end if;
  select target_key into v_target_key from penta_os20.release_projection_targets where id=v_row.target_id;
  perform penta_os20.record_receipt('release_projection_'||p_status,'PentaRelease','release_projection',v_row.id,
    jsonb_build_object('release_version',v_row.release_version,'external_release_tag',v_row.external_release_tag,'target_key',v_target_key,'evidence',coalesce(p_evidence,'{}'::jsonb),'error',p_error));
  return jsonb_build_object('queue_id',v_row.id,'target_key',v_target_key,'status',p_status,'attempts',v_row.attempts);
end;
$$;

create or replace function penta_os20.release_projection_status(p_release_version text)
returns jsonb
language sql
security invoker
set search_path = penta_os20, pg_temp
as $$
  select jsonb_build_object(
    'release_version',p_release_version,
    'required_targets',count(*) filter (where t.required),
    'synchronized_required',count(*) filter (where t.required and q.status='synchronized'),
    'open_required',count(*) filter (where t.required and q.status<>'synchronized'),
    'targets',coalesce(jsonb_agg(jsonb_build_object('target_key',t.target_key,'target_type',t.target_type,'status',q.status,'provider_ref',t.provider_ref,'attempts',q.attempts,'last_error',q.last_error) order by t.target_key),'[]'::jsonb)
  )
  from penta_os20.release_projection_queue q
  join penta_os20.release_projection_targets t on t.id=q.target_id
  where q.release_version=p_release_version;
$$;

insert into penta_os20.release_projection_targets(target_key,target_type,provider_ref,update_mode,status,required,metadata)
values
 ('github_visible_tabs','github_tabs','crownthrive1/CrownThrive-OS:CONTRIBUTING.md,SECURITY.md','managed_block_only','active',true,jsonb_build_object('owner','PentaRelease','preserve_unmanaged_content',true)),
 ('pentadocs_release_surface','pentadocs','crownthrive1/CrownThrive-OS:docs.json#Releases & Evidence','managed_block_only','active',true,jsonb_build_object('owner','PentaRelease')),
 ('github_release_assets','github_release','crownthrive1/CrownThrive-OS:releases','release_asset_set','active',true,jsonb_build_object('required_record','PENTARELEASE_RELEASE_RECORD.json')),
 ('google_drive_release_mirror','google_drive','16C3Y96Qv37oG0cnU9C-92CZ6jRadTyaL7tjbih-eyG0','managed_block_only','active',true,jsonb_build_object('folder_id','1boa0JDjy57avp9kjYRZSqJyyVfyrgccQ','provider_system','google_drive','central_dispatch','hold_fail_closed'))
on conflict (target_key) do update set provider_ref=excluded.provider_ref,update_mode=excluded.update_mode,status=excluded.status,required=excluded.required,metadata=excluded.metadata,updated_at=now();
