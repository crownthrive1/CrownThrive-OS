create schema if not exists integration_control;
revoke all on schema integration_control from public, anon, authenticated;
grant usage on schema integration_control to service_role;

create table if not exists integration_control.services (
  service_id text primary key,
  display_name text not null,
  base_url text not null,
  docs_url text not null,
  auth_scheme text not null,
  credential_ref text not null,
  credential_state text not null default 'unverified' check (credential_state in ('unverified','configured','verified','mismatch','blocked')),
  integration_state text not null default 'documented' check (integration_state in ('documented','configured','read_verified','write_verified','blocked','retired')),
  write_gate boolean not null default false,
  monthly_request_limit integer,
  timezone text not null default 'UTC',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.endpoint_catalog (
  endpoint_id text primary key,
  service_id text not null references integration_control.services(service_id) on delete cascade,
  operation_key text not null,
  http_method text not null check (http_method in ('GET','POST','PUT','PATCH','DELETE')),
  path_template text not null,
  risk_class text not null default 'D0' check (risk_class in ('D0','D1','D2','D3')),
  mutation boolean not null default false,
  source_state text not null default 'documented' check (source_state in ('documented','verified_read','verified_write','blocked','deprecated')),
  enabled boolean not null default true,
  mcp_candidate boolean not null default false,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(service_id, operation_key)
);

create table if not exists integration_control.request_budget (
  service_id text primary key references integration_control.services(service_id) on delete cascade,
  period_start date not null default date_trunc('month', now())::date,
  request_count bigint not null default 0 check (request_count >= 0),
  last_request_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.gates (
  service_id text not null references integration_control.services(service_id) on delete cascade,
  gate_key text not null,
  state text not null check (state in ('open','closed','blocked','passed')),
  reason text,
  evidence_ref text,
  updated_at timestamptz not null default now(),
  primary key(service_id, gate_key)
);

create table if not exists integration_control.request_audit (
  id bigint generated always as identity primary key,
  service_id text not null references integration_control.services(service_id) on delete restrict,
  operation_key text,
  http_method text not null,
  path_template text not null,
  http_status integer,
  success boolean,
  actor text not null default 'automation',
  source text not null default 'supabase',
  latency_ms integer,
  response_sha256 text,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists integration_control.mcp_tools (
  tool_name text primary key,
  service_id text not null references integration_control.services(service_id) on delete cascade,
  operation_key text not null,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  enabled boolean not null default false,
  requires_human_approval boolean not null default false,
  input_schema jsonb not null default '{}'::jsonb,
  output_schema jsonb not null default '{}'::jsonb,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function integration_control.touch_updated_at()
returns trigger language plpgsql set search_path = pg_catalog, integration_control as $$
begin
  new.updated_at = now();
  return new;
end $$;

create trigger services_touch_updated_at before update on integration_control.services for each row execute function integration_control.touch_updated_at();
create trigger endpoints_touch_updated_at before update on integration_control.endpoint_catalog for each row execute function integration_control.touch_updated_at();
create trigger mcp_tools_touch_updated_at before update on integration_control.mcp_tools for each row execute function integration_control.touch_updated_at();

revoke all on all tables in schema integration_control from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema integration_control to service_role;
grant usage, select on all sequences in schema integration_control to service_role;

insert into integration_control.services(service_id,display_name,base_url,docs_url,auth_scheme,credential_ref,credential_state,integration_state,write_gate,monthly_request_limit,timezone,metadata)
values
('collab_portal','Collab Portal Secure API','https://portal.crownthrive.com/secure-api','https://portal.crownthrive.com/secure-api/swagger','X-Public-ID + X-Secret-Key','vault:collab_portal_public_id+collab_portal_secret_key','mismatch','configured',false,20000,'UTC',jsonb_build_object('credential_rule','runtime_only','secret_exposure','forbidden')),
('crownthrive_io','CrownThrive IO REST API','https://crownthrive.io/api','https://crownthrive.io/api-documentation','Bearer','vault:crownthrive_io_api_key','verified','read_verified',false,null,'UTC',jsonb_build_object('credential_rule','runtime_only','secret_exposure','forbidden','docs_verified_at',now()))
on conflict(service_id) do update set
 display_name=excluded.display_name, base_url=excluded.base_url, docs_url=excluded.docs_url, auth_scheme=excluded.auth_scheme,
 credential_ref=excluded.credential_ref, credential_state=excluded.credential_state, integration_state=excluded.integration_state,
 write_gate=excluded.write_gate, monthly_request_limit=excluded.monthly_request_limit, timezone=excluded.timezone, metadata=excluded.metadata, updated_at=now();

insert into integration_control.request_budget(service_id,period_start,request_count)
values ('collab_portal',date_trunc('month',now())::date,0),('crownthrive_io',date_trunc('month',now())::date,0)
on conflict(service_id) do nothing;

insert into integration_control.gates(service_id,gate_key,state,reason,evidence_ref) values
('collab_portal','credential_exact_match','blocked','Stored secret does not hash-match founder-supplied live secret; connector safety blocked direct replacement.','sha256_compare_2026-08-19'),
('collab_portal','authenticated_read','blocked','Exact credential match required before certification.','collab_portal_pm_v2'),
('collab_portal','bounded_write','closed','Requires exact credentials, project metadata, real UID, approved field mapping, read pass, then one write/readback.','collab_portal_pm_v2'),
('crownthrive_io','credential_exact_match','passed','Vault-stored API key hash matches founder-supplied live key.','sha256_compare_2026-08-19'),
('crownthrive_io','authenticated_read','passed','GET /api/user returned HTTP 200 JSON using Vault-injected Bearer key.','io_user_read_2026-08-19'),
('crownthrive_io','write_operations','closed','Mutation families documented but not yet separately scoped or certified.','founder_secure_api_directive')
on conflict(service_id,gate_key) do update set state=excluded.state, reason=excluded.reason, evidence_ref=excluded.evidence_ref, updated_at=now();

insert into integration_control.endpoint_catalog(endpoint_id,service_id,operation_key,http_method,path_template,risk_class,mutation,source_state,enabled,mcp_candidate,notes) values
('ctio.user.read','crownthrive_io','user.read','GET','/user','D0',false,'verified_read',true,true,'Authenticated read verified 2026-08-19.'),
('ctio.links.list','crownthrive_io','links.list','GET','/links/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.statistics.read','crownthrive_io','statistics.read','GET','/statistics/','D0',false,'documented',true,true,'Documented statistics read; object parameters may be required.'),
('ctio.projects.list','crownthrive_io','projects.list','GET','/projects/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.pixels.list','crownthrive_io','pixels.list','GET','/pixels/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.splash_pages.list','crownthrive_io','splash_pages.list','GET','/splash-pages/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.qr_codes.list','crownthrive_io','qr_codes.list','GET','/qr-codes/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.data.list','crownthrive_io','data.list','GET','/data/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.notification_handlers.list','crownthrive_io','notification_handlers.list','GET','/notification-handlers/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.domains.list','crownthrive_io','domains.list','GET','/domains/','D0',false,'documented',true,true,'Documented custom-domain collection read.'),
('ctio.teams.list','crownthrive_io','teams.list','GET','/teams/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.team_members.list','crownthrive_io','team_members.list','GET','/team-members/','D0',false,'documented',true,true,'Documented collection read.'),
('ctio.teams_member.list','crownthrive_io','teams_member.list','GET','/teams-member/','D0',false,'documented',true,true,'Documented member-of-teams read.'),
('ctio.payments.list','crownthrive_io','payments.list','GET','/payments/','D1',false,'documented',true,false,'Financially sensitive account payment history; read only and restricted.'),
('ctio.logs.list','crownthrive_io','logs.list','GET','/logs/','D1',false,'documented',true,false,'Account audit logs; read only and restricted.')
on conflict(endpoint_id) do update set source_state=excluded.source_state, enabled=excluded.enabled, mcp_candidate=excluded.mcp_candidate, notes=excluded.notes, updated_at=now();

insert into integration_control.mcp_tools(tool_name,service_id,operation_key,risk_class,enabled,requires_human_approval,input_schema,output_schema,notes) values
('crownthrive_io_get_user','crownthrive_io','user.read','D0',true,false,'{"type":"object","properties":{},"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Read-only identity/account metadata adapter; does not replace CrownThrive ID.'),
('crownthrive_io_list_links','crownthrive_io','links.list','D0',false,false,'{"type":"object","properties":{"page":{"type":"integer","minimum":1}},"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Enable after collection read certification.'),
('crownthrive_io_list_projects','crownthrive_io','projects.list','D0',false,false,'{"type":"object","properties":{"page":{"type":"integer","minimum":1}},"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Enable after collection read certification.')
on conflict(tool_name) do update set enabled=excluded.enabled, requires_human_approval=excluded.requires_human_approval, input_schema=excluded.input_schema, output_schema=excluded.output_schema, notes=excluded.notes, updated_at=now();