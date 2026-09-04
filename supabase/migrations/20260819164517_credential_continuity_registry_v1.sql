create table if not exists integration_control.credential_continuity_registry (
  credential_id text primary key,
  service_id text not null,
  credential_class text not null,
  provider_system text not null,
  provider_location_note text not null,
  primary_vault_name text,
  recovery_vault_name text,
  primary_present boolean not null default false,
  recovery_present boolean not null default false,
  fingerprint_sha256 text,
  runtime_consumers jsonb not null default '[]'::jsonb,
  continuity_state text not null default 'pending' check (continuity_state in ('verified_dual_reference','verified_primary_only','pending','blocked_missing_secret','provider_managed_only','retired')),
  recovery_note text,
  last_verified_at timestamptz,
  updated_at timestamptz not null default now()
);

alter table integration_control.credential_continuity_registry enable row level security;
revoke all on table integration_control.credential_continuity_registry from public, anon, authenticated;
grant select,insert,update,delete on table integration_control.credential_continuity_registry to service_role;
drop policy if exists credential_continuity_registry_service_role_all on integration_control.credential_continuity_registry;
create policy credential_continuity_registry_service_role_all on integration_control.credential_continuity_registry for all to service_role using (true) with check (true);

create table if not exists integration_control.runtime_variable_registry (
  variable_key text primary key,
  service_id text not null,
  value_class text not null check (value_class in ('public_url','callback_url','issuer','endpoint','provider_account_id','platform_id','secret_reference','configuration_reference','policy_reference')),
  public_value text,
  secret_reference text,
  canonical_source text not null,
  recovery_source text,
  runtime_consumers jsonb not null default '[]'::jsonb,
  notes text,
  updated_at timestamptz not null default now(),
  check ((public_value is not null) <> (secret_reference is not null) or value_class='configuration_reference')
);

alter table integration_control.runtime_variable_registry enable row level security;
revoke all on table integration_control.runtime_variable_registry from public, anon, authenticated;
grant select,insert,update,delete on table integration_control.runtime_variable_registry to service_role;
drop policy if exists runtime_variable_registry_service_role_all on integration_control.runtime_variable_registry;
create policy runtime_variable_registry_service_role_all on integration_control.runtime_variable_registry for all to service_role using (true) with check (true);

create index if not exists idx_webhook_receipts_service_id on integration_control.webhook_receipts(service_id);

insert into integration_control.runtime_variable_registry(variable_key,service_id,value_class,public_value,secret_reference,canonical_source,recovery_source,runtime_consumers,notes) values
('crownthrive.supabase.project_url','crownthrive_api_control','public_url','https://tzajnzshmtzjenqulehq.supabase.co',null,'Supabase project','Phase 2.99 institutional manifests','["crownthrive-api-control","locticians-api-control","stripe-institutional-webhook","collab-portal-pm"]'::jsonb,'Canonical CrownThrive Supabase project URL.'),
('crownthrive.id.issuer','crownthrive_api_control','issuer','https://tzajnzshmtzjenqulehq.supabase.co/auth/v1',null,'Supabase Auth OIDC discovery','CrownThrive ID federation manifest','["CrownThrive ID","MCP OAuth clients"]'::jsonb,'Institutional identity issuer.'),
('crownthrive.id.onzauth.callback','onzauth','callback_url','https://tzajnzshmtzjenqulehq.supabase.co/auth/v1/callback',null,'Supabase Auth custom OIDC provider','CrownThrive ID federation manifest','["custom:onzauth"]'::jsonb,'Must be allowed in the CrownConnect OnzAuth project.'),
('crownthrive.mcp.remote_url','crownthrive_api_control','endpoint','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/crownthrive-api-control',null,'Supabase Edge Functions','MCP client compatibility manifest','["OpenAI","Codex","Claude","generic MCP clients"]'::jsonb,'Single governed remote MCP target.'),
('stripe.institutional.webhook_url','stripe','endpoint','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/stripe-institutional-webhook',null,'Stripe webhook endpoint we_1U445WCJFUeGxc8S0HL8wI5d','Stripe/Supabase event-plane manifest','["stripe-institutional-webhook"]'::jsonb,'Repurposed retired KJV snapshot endpoint; active institutional observer.'),
('stripe.account_id','stripe','provider_account_id','acct_1MENDxCJFUeGxc8S',null,'Stripe connected account','Stripe provider inventory','["payments control plane"]'::jsonb,'CrownThrive, LLC Stripe account.'),
('locticians.bd.base_url','locticians','public_url','https://www.locticians.com/api/v2',null,'Brilliant Directories Website API 2.0','Locticians adapter manifest','["locticians-api-control","future MCP adapter"]'::jsonb,'Provider API base.'),
('collab.portal.base_url','collab_portal','public_url','https://portal.crownthrive.com/secure-api',null,'Collab Portal Secure API Swagger','Collab adapter manifest','["collab-portal-pm"]'::jsonb,'Provider API base.')
on conflict(variable_key) do update set public_value=excluded.public_value,secret_reference=excluded.secret_reference,canonical_source=excluded.canonical_source,recovery_source=excluded.recovery_source,runtime_consumers=excluded.runtime_consumers,notes=excluded.notes,updated_at=now();