create table if not exists integration_control.governed_deferrals (
  deferral_id text primary key,
  scope_type text not null check (scope_type in ('hard_exit_gate','service_gate','provider_state','source_recovery','continuity_recovery','other')),
  scope_key text not null,
  title text not null,
  status text not null default 'candidate' check (status in ('candidate','approved','expired','revoked','resolved')),
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  external_dependency boolean not null default true,
  unresolved_condition text not null,
  accountable_owner text not null,
  compensating_controls jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  reopening_trigger text not null,
  review_due_at timestamptz,
  expires_at timestamptz,
  approved_by text,
  approved_at timestamptz,
  resolved_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table integration_control.governed_deferrals enable row level security;

drop policy if exists governed_deferrals_service_role_all on integration_control.governed_deferrals;
create policy governed_deferrals_service_role_all on integration_control.governed_deferrals
for all to service_role using (true) with check (true);

revoke all on integration_control.governed_deferrals from anon, authenticated;
grant all on integration_control.governed_deferrals to service_role;

create index if not exists governed_deferrals_scope_idx on integration_control.governed_deferrals(scope_type, scope_key);
create index if not exists governed_deferrals_status_idx on integration_control.governed_deferrals(status, review_due_at);

create or replace function public.governed_deferral_snapshot()
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','integration_control'
as $$
  select coalesce(jsonb_agg(jsonb_build_object(
    'deferral_id', d.deferral_id,
    'scope_type', d.scope_type,
    'scope_key', d.scope_key,
    'title', d.title,
    'status', d.status,
    'risk_class', d.risk_class,
    'external_dependency', d.external_dependency,
    'unresolved_condition', d.unresolved_condition,
    'accountable_owner', d.accountable_owner,
    'compensating_controls', d.compensating_controls,
    'evidence_refs', d.evidence_refs,
    'reopening_trigger', d.reopening_trigger,
    'review_due_at', d.review_due_at,
    'expires_at', d.expires_at,
    'approved_by', d.approved_by,
    'approved_at', d.approved_at,
    'resolved_at', d.resolved_at,
    'notes', d.notes,
    'updated_at', d.updated_at
  ) order by d.deferral_id), '[]'::jsonb)
  from integration_control.governed_deferrals d;
$$;

revoke all on function public.governed_deferral_snapshot() from public, anon, authenticated;
grant execute on function public.governed_deferral_snapshot() to service_role;