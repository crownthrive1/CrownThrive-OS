create table if not exists integration_control.penta_ads_installs_v1(
  install_id uuid primary key default gen_random_uuid(),
  public_install_key uuid not null unique default gen_random_uuid(),
  tenant_key text not null,
  property_key text not null,
  source_commit_sha text not null check(source_commit_sha ~ '^[a-f0-9]{40}$'),
  release_version text not null,
  allowed_origins text[] not null,
  manifest jsonb not null default '{}'::jsonb,
  state text not null default 'active' check(state in('active','disabled','superseded')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists penta_ads_installs_v1_one_active_property on integration_control.penta_ads_installs_v1(property_key) where state='active';

create table if not exists integration_control.penta_ads_install_sessions_v1(
  session_id uuid primary key default gen_random_uuid(),
  install_id uuid not null references integration_control.penta_ads_installs_v1(install_id) on delete cascade,
  session_hash text not null unique check(session_hash ~ '^[a-f0-9]{64}$'),
  actions text[] not null,
  expires_at timestamptz not null,
  state text not null default 'active' check(state in('active','revoked','expired')),
  created_at timestamptz not null default now(),
  last_used_at timestamptz
);

create table if not exists integration_control.penta_ads_zone_lab_runs_v1(
  run_id uuid primary key default gen_random_uuid(),
  install_id uuid not null references integration_control.penta_ads_installs_v1(install_id),
  property_key text not null,
  source_commit_sha text not null check(source_commit_sha ~ '^[a-f0-9]{40}$'),
  state text not null default 'running' check(state in('running','completed','held','failed')),
  summary jsonb not null default '{}'::jsonb,
  evidence_sha256 text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists integration_control.penta_ads_zone_lab_results_v1(
  result_id uuid primary key default gen_random_uuid(),
  run_id uuid not null references integration_control.penta_ads_zone_lab_runs_v1(run_id) on delete cascade,
  zone_id bigint not null,
  format text not null,
  policy_class text not null,
  state text not null,
  latency_ms integer,
  payload jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now(),
  unique(run_id,zone_id)
);

alter table integration_control.penta_ads_installs_v1 enable row level security;
alter table integration_control.penta_ads_install_sessions_v1 enable row level security;
alter table integration_control.penta_ads_zone_lab_runs_v1 enable row level security;
alter table integration_control.penta_ads_zone_lab_results_v1 enable row level security;
revoke all on integration_control.penta_ads_installs_v1,integration_control.penta_ads_install_sessions_v1,integration_control.penta_ads_zone_lab_runs_v1,integration_control.penta_ads_zone_lab_results_v1 from anon,authenticated,public;

grant select,insert,update,delete on integration_control.penta_ads_installs_v1,integration_control.penta_ads_install_sessions_v1,integration_control.penta_ads_zone_lab_runs_v1,integration_control.penta_ads_zone_lab_results_v1 to service_role;

create or replace function integration_control.penta_ads_mint_sandbox_session_v1(p_property_key text,p_source_sha text,p_release_version text default '1.1.0',p_ttl_minutes integer default 1440)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','extensions'
as $function$
declare v_install integration_control.penta_ads_installs_v1%rowtype; v_origin text; v_tenant text; v_token text; v_hash text; v_exp timestamptz;
begin
  if p_source_sha !~ '^[a-f0-9]{40}$' then raise exception 'penta_ads_self_serve_source_invalid'; end if;
  if p_ttl_minutes < 15 or p_ttl_minutes > 10080 then raise exception 'penta_ads_self_serve_ttl_invalid'; end if;
  select tenant_key,origin into v_tenant,v_origin from integration_control.penta_ads_property_bindings_v1 where property_key=p_property_key and state='active' limit 1;
  if v_tenant is null then raise exception 'penta_ads_self_serve_property_missing'; end if;
  select * into v_install from integration_control.penta_ads_installs_v1 where property_key=p_property_key and state='active' limit 1;
  if v_install.install_id is null then
    insert into integration_control.penta_ads_installs_v1(tenant_key,property_key,source_commit_sha,release_version,allowed_origins,manifest)
    values(v_tenant,p_property_key,p_source_sha,p_release_version,array[v_origin],jsonb_build_object('auto_discover',true,'refresh_seconds',30)) returning * into v_install;
  else
    update integration_control.penta_ads_installs_v1 set source_commit_sha=p_source_sha,release_version=p_release_version,allowed_origins=array[v_origin],updated_at=now() where install_id=v_install.install_id returning * into v_install;
  end if;
  v_token:=encode(extensions.gen_random_bytes(32),'hex');
  v_hash:=encode(extensions.digest(convert_to(v_token,'UTF8'),'sha256'),'hex');
  v_exp:=now()+make_interval(mins=>p_ttl_minutes);
  insert into integration_control.penta_ads_install_sessions_v1(install_id,session_hash,actions,expires_at)
  values(v_install.install_id,v_hash,array['analyze','status','deploy_demo','rollback_demo','zone_catalog','zone_lab_start','zone_lab_result','zone_lab_complete'],v_exp);
  return jsonb_build_object('install_id',v_install.install_id,'public_install_key',v_install.public_install_key,'session',v_token,'expires_at',v_exp,'property_key',p_property_key,'origin',v_origin,'source_sha',p_source_sha,'release_version',p_release_version);
end;
$function$;
revoke all on function integration_control.penta_ads_mint_sandbox_session_v1(text,text,text,integer) from public,anon,authenticated;
grant execute on function integration_control.penta_ads_mint_sandbox_session_v1(text,text,text,integer) to service_role;
