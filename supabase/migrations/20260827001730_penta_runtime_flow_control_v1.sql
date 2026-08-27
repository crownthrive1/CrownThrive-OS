-- Penta runtime flow-control capability pack v1.
--
-- This migration installs a non-voting, non-certifying execution surface for
-- PentaQueue (under PentaRoute), PentaLoad, PentaBalancer and PentaCosts.  The
-- Founder D3 directive is bound for exactly fourteen days from its immutable
-- database receipt.  It does not substitute for independent evidence, release
-- gates, provider readback, rights review, money authority or credential
-- authority.  GitHub provider work remains fail-closed in HOLD.

create schema if not exists penta_runtime;

-- ---------------------------------------------------------------------------
-- Immutable campaign authority binding and append-only operating evidence.
-- ---------------------------------------------------------------------------

create table if not exists penta_runtime.d3_campaign_bindings_v1 (
  campaign_id text primary key,
  directive_id text not null unique
    references developer_commerce.founder_directives(directive_id) on delete restrict,
  founder_ref text not null,
  directive_source_sha256 text not null
    check (directive_source_sha256 ~ '^[0-9a-f]{64}$'),
  scope_sha256 text not null check (scope_sha256 ~ '^[0-9a-f]{64}$'),
  starts_at timestamptz not null,
  expires_at timestamptz not null,
  authorized_actions text[] not null,
  allowed_source_types text[] not null,
  repository_snapshot jsonb not null check (jsonb_typeof(repository_snapshot) = 'array'),
  factory_snapshot jsonb not null check (jsonb_typeof(factory_snapshot) = 'array'),
  max_concurrency integer not null check (max_concurrency between 1 and 64),
  max_claim_batch integer not null check (max_claim_batch between 1 and 64),
  max_cost_minor bigint not null default 0 check (max_cost_minor = 0),
  max_internal_units bigint not null check (max_internal_units > 0),
  independent_evidence_required boolean not null default true
    check (independent_evidence_required is true),
  provider_write_authority boolean not null default false
    check (provider_write_authority is false),
  money_movement_authority boolean not null default false
    check (money_movement_authority is false),
  rights_disposition_authority boolean not null default false
    check (rights_disposition_authority is false),
  credential_authority boolean not null default false
    check (credential_authority is false),
  nonrenewing boolean not null default true check (nonrenewing is true),
  created_at timestamptz not null default clock_timestamp(),
  check (expires_at = starts_at + interval '14 days'),
  check (cardinality(authorized_actions) > 0),
  check (cardinality(allowed_source_types) > 0)
);

create table if not exists penta_runtime.d3_campaign_holds_v1 (
  campaign_id text primary key
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  hold_reason text not null check (length(btrim(hold_reason)) between 1 and 1000),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  held_by text not null,
  held_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_runtime.runtime_release_baselines_v1 (
  baseline_id uuid primary key default gen_random_uuid(),
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  migration_sha256 text not null check (migration_sha256 ~ '^[0-9a-f]{64}$'),
  technical_evidence_sha256 text not null check (technical_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  security_evidence_sha256 text not null check (security_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  independent_verifier_ref text not null,
  independent_verification_sha256 text not null
    check (independent_verification_sha256 ~ '^[0-9a-f]{64}$'),
  rollback_ref text not null,
  verified_by text not null,
  verified_at timestamptz not null,
  state text not null check (state = 'verified'),
  metadata jsonb not null default '{}'::jsonb,
  unique (campaign_id, exact_head_sha, migration_sha256),
  check (length(btrim(independent_verifier_ref)) between 1 and 500),
  check (length(btrim(rollback_ref)) between 1 and 1000),
  check (length(btrim(verified_by)) between 1 and 500),
  check (verified_by <> independent_verifier_ref)
);

-- Runtime activation is deliberately absent from this implementation migration.
-- A later exact-evidence migration may append one receipt after independent
-- technical/security review.  No function below can execute candidates without
-- that receipt.
create table if not exists penta_runtime.runtime_activation_receipts_v1 (
  activation_id uuid primary key default gen_random_uuid(),
  campaign_id text not null unique
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  baseline_id uuid not null unique
    references penta_runtime.runtime_release_baselines_v1(baseline_id) on delete restrict,
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  migration_sha256 text not null check (migration_sha256 ~ '^[0-9a-f]{64}$'),
  technical_evidence_sha256 text not null check (technical_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  security_evidence_sha256 text not null check (security_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  independent_verifier_ref text not null,
  independent_verification_sha256 text not null
    check (independent_verification_sha256 ~ '^[0-9a-f]{64}$'),
  rollback_ref text not null,
  activated_route_keys text[] not null check (cardinality(activated_route_keys) > 0),
  certified_target_adapter_keys text[] not null
    check (cardinality(certified_target_adapter_keys) > 0),
  activated_at timestamptz not null default clock_timestamp(),
  expires_at timestamptz not null,
  state text not null default 'active' check (state = 'active'),
  self_certification boolean not null default false check (self_certification is false),
  metadata jsonb not null default '{}'::jsonb,
  check (expires_at > activated_at),
  check (length(btrim(independent_verifier_ref)) between 1 and 500),
  check (length(btrim(rollback_ref)) between 1 and 1000)
);

create table if not exists penta_runtime.factory_target_adapters_v1 (
  target_adapter_key text primary key,
  target_kind text not null unique,
  interface_version text not null,
  claim_semantics text not null,
  idempotency_semantics text not null,
  fencing_semantics text not null,
  supported boolean not null default false,
  eligible boolean not null default false,
  state text not null default 'hold' check (state in ('implemented','hold')),
  direct_table_mutation boolean not null default false check (direct_table_mutation is false),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  check ((supported and eligible and state = 'implemented')
         or (not eligible and state = 'hold'))
);

create table if not exists penta_runtime.component_registry_rollback_v1 (
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  component_key text not null,
  prior_row jsonb not null check (jsonb_typeof(prior_row) = 'object'),
  prior_row_sha256 text not null check (prior_row_sha256 ~ '^[0-9a-f]{64}$'),
  captured_at timestamptz not null default clock_timestamp(),
  primary key (campaign_id, component_key)
);

create table if not exists penta_runtime.factory_routes_v1 (
  route_key text primary key,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  target_adapter_key text not null
    references penta_runtime.factory_target_adapters_v1(target_adapter_key) on delete restrict,
  project_id uuid not null references public.ct_factory_projects(id) on delete restrict,
  project_key text not null,
  factory_repository text,
  allowed_target_repositories text[] not null,
  release_channel text not null default 'staging'
    check (release_channel in ('development','staging')),
  max_inflight integer not null check (max_inflight between 1 and 64),
  max_claim_batch integer not null check (max_claim_batch between 1 and 64),
  weight integer not null default 100 check (weight between 1 and 10000),
  enabled boolean not null default false check (enabled is false),
  provider_claim_enabled boolean not null default false
    check (provider_claim_enabled is false),
  created_at timestamptz not null default clock_timestamp(),
  unique (campaign_id, project_id),
  check (cardinality(allowed_target_repositories) > 0)
);

create table if not exists penta_runtime.cost_rate_books_v1 (
  rate_key text primary key,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  operation_key text not null,
  unit_key text not null,
  rate_units bigint not null check (rate_units > 0),
  cost_minor bigint not null default 0 check (cost_minor = 0),
  cost_currency text not null default 'USD' check (cost_currency = 'USD'),
  effective_at timestamptz not null,
  expires_at timestamptz not null,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  implementation_state text not null default 'implemented'
    check (implementation_state = 'implemented'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  unique (campaign_id, operation_key, effective_at),
  check (expires_at > effective_at)
);

-- Dedicated queue isolation: generic jobs_v1 remains untouched because its
-- legacy maintenance clock and dispatcher have incompatible state semantics.
create table if not exists penta_runtime.flow_jobs_v1 (
  job_id uuid primary key default gen_random_uuid(),
  job_key text not null unique,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  route_key text not null references penta_runtime.factory_routes_v1(route_key) on delete restrict,
  job_kind text not null
    check (job_kind in ('bugfix','security','security_hotfix','wave','vault','identity','docs','release','verification','routing')),
  severity text not null default 'medium'
    check (severity in ('info','low','medium','high','critical')),
  state text not null default 'queued'
    check (state in ('queued','leased','dispatched','implemented','hold','failed','expired')),
  source_type text not null check (source_type in ('penta_runtime','institutional_backlog','penta_helper')),
  source_ref text not null,
  source_digest_sha256 text not null check (source_digest_sha256 ~ '^[0-9a-f]{64}$'),
  objective text not null,
  target_repositories text[] not null check (cardinality(target_repositories) > 0),
  owner_agent_id text not null,
  verifier_agent_id text not null,
  priority integer not null default 100 check (priority between 0 and 1000),
  available_at timestamptz not null default now(),
  deadline_at timestamptz not null,
  lease_owner text,
  lease_expires_at timestamptz,
  fencing_token bigint not null default 0 check (fencing_token >= 0),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 5 check (max_attempts between 1 and 100),
  estimated_units bigint not null check (estimated_units > 0),
  reserved_units bigint not null default 0 check (reserved_units >= 0),
  accounted_units bigint not null default 0 check (accounted_units >= 0),
  estimated_cost_minor bigint not null default 0 check (estimated_cost_minor = 0),
  reserved_cost_minor bigint not null default 0 check (reserved_cost_minor = 0),
  cost_currency text not null default 'USD' check (cost_currency = 'USD'),
  result jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  last_error text,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  check (owner_agent_id <> verifier_agent_id),
  check (reserved_units <= estimated_units and accounted_units <= estimated_units),
  check ((lease_owner is null and lease_expires_at is null)
         or (lease_owner is not null and lease_expires_at is not null))
);

create index if not exists flow_jobs_v1_claim_idx
  on penta_runtime.flow_jobs_v1
  (campaign_id,state,priority desc,available_at,created_at)
  where state='queued';
create index if not exists flow_jobs_v1_lease_idx
  on penta_runtime.flow_jobs_v1(campaign_id,lease_expires_at)
  where lease_expires_at is not null;
create index if not exists flow_jobs_v1_route_state_idx
  on penta_runtime.flow_jobs_v1(campaign_id,route_key,state);

create table if not exists penta_runtime.cost_unit_budgets_v1 (
  unit_budget_id uuid primary key default gen_random_uuid(),
  budget_key text not null unique,
  campaign_id text not null unique
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  ceiling_units bigint not null check (ceiling_units > 0),
  cash_or_provider_cost_minor bigint not null default 0
    check (cash_or_provider_cost_minor = 0),
  reserved_units bigint not null default 0 check (reserved_units >= 0),
  accounted_units bigint not null default 0 check (accounted_units >= 0),
  state text not null default 'implemented' check (state in ('implemented','active','held','closed')),
  starts_at timestamptz not null,
  expires_at timestamptz not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  check (reserved_units + accounted_units <= ceiling_units),
  check (expires_at > starts_at)
);

create table if not exists penta_runtime.cost_reservations_v1 (
  reservation_id uuid primary key default gen_random_uuid(),
  reservation_key text not null unique,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  job_id uuid not null references penta_runtime.flow_jobs_v1(job_id) on delete restrict,
  unit_budget_id uuid not null
    references penta_runtime.cost_unit_budgets_v1(unit_budget_id) on delete restrict,
  rate_key text not null references penta_runtime.cost_rate_books_v1(rate_key) on delete restrict,
  quantity bigint not null check (quantity > 0),
  estimated_units bigint not null check (estimated_units > 0),
  accounted_units bigint check (accounted_units is null or accounted_units >= 0),
  estimated_cost_minor bigint not null default 0 check (estimated_cost_minor = 0),
  actual_cost_minor bigint check (actual_cost_minor is null or actual_cost_minor = 0),
  cost_currency text not null default 'USD' check (cost_currency = 'USD'),
  state text not null default 'reserved'
    check (state in ('reserved','accounted','released')),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  reconciled_at timestamptz,
  unique (campaign_id, job_id),
  check (accounted_units is null or accounted_units <= estimated_units)
);

create table if not exists penta_runtime.cost_usage_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  event_key text not null unique,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  job_id uuid not null references penta_runtime.flow_jobs_v1(job_id) on delete restrict,
  reservation_id uuid not null
    references penta_runtime.cost_reservations_v1(reservation_id) on delete restrict,
  rate_key text not null references penta_runtime.cost_rate_books_v1(rate_key) on delete restrict,
  quantity bigint not null check (quantity > 0),
  amount_units bigint not null check (amount_units >= 0),
  cost_minor bigint not null default 0 check (cost_minor = 0),
  cost_currency text not null default 'USD' check (cost_currency = 'USD'),
  rate_source_sha256 text not null check (rate_source_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_runtime.cost_ledger_entries_v1 (
  entry_id uuid primary key default gen_random_uuid(),
  entry_key text not null unique,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  job_id uuid not null references penta_runtime.flow_jobs_v1(job_id) on delete restrict,
  reservation_id uuid not null
    references penta_runtime.cost_reservations_v1(reservation_id) on delete restrict,
  entry_kind text not null check (entry_kind in ('reserve','release','account')),
  amount_units bigint not null check (amount_units >= 0),
  cost_minor bigint not null default 0 check (cost_minor = 0),
  cost_currency text not null default 'USD' check (cost_currency = 'USD'),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_runtime.cost_forecasts_v1 (
  forecast_id uuid primary key default gen_random_uuid(),
  forecast_key text not null unique,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  horizon_minutes integer not null check (horizon_minutes between 1 and 10080),
  observed_event_count bigint not null check (observed_event_count >= 0),
  forecast_units bigint not null check (forecast_units >= 0),
  forecast_cost_minor bigint not null default 0 check (forecast_cost_minor = 0),
  cost_currency text not null default 'USD' check (cost_currency = 'USD'),
  assumptions jsonb not null default '{}'::jsonb,
  advisory_only boolean not null default true check (advisory_only is true),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_runtime.load_snapshots_v1 (
  snapshot_id uuid primary key default gen_random_uuid(),
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  route_key text not null references penta_runtime.factory_routes_v1(route_key) on delete restrict,
  sample_bucket timestamptz not null,
  queued_count bigint not null check (queued_count >= 0),
  leased_count bigint not null check (leased_count >= 0),
  factory_inflight_count bigint not null check (factory_inflight_count >= 0),
  max_inflight integer not null check (max_inflight > 0),
  available_slots integer not null check (available_slots >= 0),
  pressure_state text not null check (pressure_state in ('idle','normal','high','saturated')),
  material_sha256 text not null check (material_sha256 ~ '^[0-9a-f]{64}$'),
  captured_at timestamptz not null default clock_timestamp(),
  unique (campaign_id, route_key, sample_bucket)
);

create table if not exists penta_runtime.consolidated_reports_v1 (
  report_id uuid primary key default gen_random_uuid(),
  report_key text not null unique,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  material_sha256 text not null check (material_sha256 ~ '^[0-9a-f]{64}$'),
  summary jsonb not null,
  raw_counts jsonb not null,
  exception_groups jsonb not null default '[]'::jsonb
    check (jsonb_typeof(exception_groups) = 'array'),
  evidence_scope jsonb not null,
  captured_at timestamptz not null default clock_timestamp(),
  unique (campaign_id, material_sha256)
);

create table if not exists penta_runtime.dispatch_outbox_v1 (
  outbox_id uuid primary key default gen_random_uuid(),
  outbox_key text not null unique,
  job_id uuid not null unique references penta_runtime.flow_jobs_v1(job_id) on delete restrict,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  route_key text not null references penta_runtime.factory_routes_v1(route_key) on delete restrict,
  target_adapter_key text not null
    references penta_runtime.factory_target_adapters_v1(target_adapter_key) on delete restrict,
  state text not null default 'pending' check (state in ('pending','consumed','hold','failed')),
  fencing_token bigint not null check (fencing_token > 0),
  payload jsonb not null,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  available_at timestamptz not null default now(),
  consumed_at timestamptz,
  last_error text,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create index if not exists dispatch_outbox_v1_pending_idx
  on penta_runtime.dispatch_outbox_v1(target_adapter_key,state,available_at,created_at)
  where state='pending';

create table if not exists penta_runtime.dispatch_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  receipt_key text not null unique,
  outbox_id uuid not null references penta_runtime.dispatch_outbox_v1(outbox_id) on delete restrict,
  job_id uuid not null references penta_runtime.flow_jobs_v1(job_id) on delete restrict,
  disposition text not null check (disposition in ('ct_factory_accepted','hold','failed')),
  target_ref text,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp()
);

-- ---------------------------------------------------------------------------
-- RLS and direct privilege boundary.
-- ---------------------------------------------------------------------------

alter table penta_runtime.d3_campaign_bindings_v1 enable row level security;
alter table penta_runtime.d3_campaign_bindings_v1 force row level security;
alter table penta_runtime.d3_campaign_holds_v1 enable row level security;
alter table penta_runtime.d3_campaign_holds_v1 force row level security;
alter table penta_runtime.runtime_release_baselines_v1 enable row level security;
alter table penta_runtime.runtime_release_baselines_v1 force row level security;
alter table penta_runtime.runtime_activation_receipts_v1 enable row level security;
alter table penta_runtime.runtime_activation_receipts_v1 force row level security;
alter table penta_runtime.factory_target_adapters_v1 enable row level security;
alter table penta_runtime.factory_target_adapters_v1 force row level security;
alter table penta_runtime.component_registry_rollback_v1 enable row level security;
alter table penta_runtime.component_registry_rollback_v1 force row level security;
alter table penta_runtime.factory_routes_v1 enable row level security;
alter table penta_runtime.factory_routes_v1 force row level security;
alter table penta_runtime.cost_rate_books_v1 enable row level security;
alter table penta_runtime.cost_rate_books_v1 force row level security;
alter table penta_runtime.cost_unit_budgets_v1 enable row level security;
alter table penta_runtime.cost_unit_budgets_v1 force row level security;
alter table penta_runtime.cost_reservations_v1 enable row level security;
alter table penta_runtime.cost_reservations_v1 force row level security;
alter table penta_runtime.cost_usage_events_v1 enable row level security;
alter table penta_runtime.cost_usage_events_v1 force row level security;
alter table penta_runtime.cost_ledger_entries_v1 enable row level security;
alter table penta_runtime.cost_ledger_entries_v1 force row level security;
alter table penta_runtime.cost_forecasts_v1 enable row level security;
alter table penta_runtime.cost_forecasts_v1 force row level security;
alter table penta_runtime.load_snapshots_v1 enable row level security;
alter table penta_runtime.load_snapshots_v1 force row level security;
alter table penta_runtime.consolidated_reports_v1 enable row level security;
alter table penta_runtime.consolidated_reports_v1 force row level security;
alter table penta_runtime.flow_jobs_v1 enable row level security;
alter table penta_runtime.flow_jobs_v1 force row level security;
alter table penta_runtime.dispatch_outbox_v1 enable row level security;
alter table penta_runtime.dispatch_outbox_v1 force row level security;
alter table penta_runtime.dispatch_receipts_v1 enable row level security;
alter table penta_runtime.dispatch_receipts_v1 force row level security;

revoke all on penta_runtime.d3_campaign_bindings_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.d3_campaign_holds_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.runtime_release_baselines_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.runtime_activation_receipts_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.factory_target_adapters_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.component_registry_rollback_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.factory_routes_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.cost_rate_books_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.cost_unit_budgets_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.cost_reservations_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.cost_usage_events_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.cost_ledger_entries_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.cost_forecasts_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.load_snapshots_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.consolidated_reports_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.flow_jobs_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.dispatch_outbox_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.dispatch_receipts_v1 from public, anon, authenticated, service_role;
-- Existing jobs/cost/provider tables retain their established grants so this
-- implementation-only migration cannot break current callers.  New state is
-- changed only through the narrow SECURITY DEFINER functions below.

grant select on penta_runtime.d3_campaign_bindings_v1 to service_role;
grant select on penta_runtime.d3_campaign_holds_v1 to service_role;
grant select on penta_runtime.runtime_release_baselines_v1 to service_role;
grant select on penta_runtime.runtime_activation_receipts_v1 to service_role;
grant select on penta_runtime.factory_target_adapters_v1 to service_role;
grant select on penta_runtime.component_registry_rollback_v1 to service_role;
grant select on penta_runtime.factory_routes_v1 to service_role;
grant select on penta_runtime.cost_rate_books_v1 to service_role;
grant select on penta_runtime.cost_unit_budgets_v1 to service_role;
grant select on penta_runtime.cost_reservations_v1 to service_role;
grant select on penta_runtime.cost_usage_events_v1 to service_role;
grant select on penta_runtime.cost_ledger_entries_v1 to service_role;
grant select on penta_runtime.cost_forecasts_v1 to service_role;
grant select on penta_runtime.load_snapshots_v1 to service_role;
grant select on penta_runtime.consolidated_reports_v1 to service_role;
grant select on penta_runtime.flow_jobs_v1 to service_role;
grant select on penta_runtime.dispatch_outbox_v1 to service_role;
grant select on penta_runtime.dispatch_receipts_v1 to service_role;

-- ---------------------------------------------------------------------------
-- Immutability and fail-closed provider containment triggers.
-- ---------------------------------------------------------------------------

create or replace function penta_runtime.reject_row_mutation_v1()
returns trigger
language plpgsql
set search_path = 'pg_catalog'
as $$
begin
  raise exception '% is immutable/append-only', tg_table_schema || '.' || tg_table_name
    using errcode = '55000';
end;
$$;

drop trigger if exists trg_d3_campaign_bindings_immutable_v1
  on penta_runtime.d3_campaign_bindings_v1;
create trigger trg_d3_campaign_bindings_immutable_v1
  before update or delete on penta_runtime.d3_campaign_bindings_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_d3_campaign_holds_append_only_v1
  on penta_runtime.d3_campaign_holds_v1;
create trigger trg_d3_campaign_holds_append_only_v1
  before update or delete on penta_runtime.d3_campaign_holds_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_runtime_release_baselines_append_only_v1
  on penta_runtime.runtime_release_baselines_v1;
create trigger trg_runtime_release_baselines_append_only_v1
  before update or delete on penta_runtime.runtime_release_baselines_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_runtime_activation_receipts_append_only_v1
  on penta_runtime.runtime_activation_receipts_v1;
create trigger trg_runtime_activation_receipts_append_only_v1
  before update or delete on penta_runtime.runtime_activation_receipts_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_factory_target_adapters_immutable_v1
  on penta_runtime.factory_target_adapters_v1;
create trigger trg_factory_target_adapters_immutable_v1
  before update or delete on penta_runtime.factory_target_adapters_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_component_registry_rollback_append_only_v1
  on penta_runtime.component_registry_rollback_v1;
create trigger trg_component_registry_rollback_append_only_v1
  before update or delete on penta_runtime.component_registry_rollback_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_factory_routes_immutable_v1
  on penta_runtime.factory_routes_v1;
create trigger trg_factory_routes_immutable_v1
  before update or delete on penta_runtime.factory_routes_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_cost_rate_books_immutable_v1
  on penta_runtime.cost_rate_books_v1;
create trigger trg_cost_rate_books_immutable_v1
  before update or delete on penta_runtime.cost_rate_books_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_cost_usage_events_append_only_v1
  on penta_runtime.cost_usage_events_v1;
create trigger trg_cost_usage_events_append_only_v1
  before update or delete on penta_runtime.cost_usage_events_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_cost_ledger_entries_append_only_v1
  on penta_runtime.cost_ledger_entries_v1;
create trigger trg_cost_ledger_entries_append_only_v1
  before update or delete on penta_runtime.cost_ledger_entries_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_cost_forecasts_append_only_v1
  on penta_runtime.cost_forecasts_v1;
create trigger trg_cost_forecasts_append_only_v1
  before update or delete on penta_runtime.cost_forecasts_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_load_snapshots_append_only_v1
  on penta_runtime.load_snapshots_v1;
create trigger trg_load_snapshots_append_only_v1
  before update or delete on penta_runtime.load_snapshots_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_consolidated_reports_append_only_v1
  on penta_runtime.consolidated_reports_v1;
create trigger trg_consolidated_reports_append_only_v1
  before update or delete on penta_runtime.consolidated_reports_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

drop trigger if exists trg_dispatch_receipts_append_only_v1
  on penta_runtime.dispatch_receipts_v1;
create trigger trg_dispatch_receipts_append_only_v1
  before update or delete on penta_runtime.dispatch_receipts_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

create or replace function penta_runtime.protect_flow_founder_directive_v1()
returns trigger
language plpgsql
set search_path = 'pg_catalog'
as $$
begin
  if old.directive_id = 'ct-founder-directive-penta-flow-control-20260826-v1' then
    raise exception 'bounded flow-control Founder directive is immutable'
      using errcode = '55000';
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end;
$$;

drop trigger if exists trg_protect_flow_founder_directive_v1
  on developer_commerce.founder_directives;
create trigger trg_protect_flow_founder_directive_v1
  before update or delete on developer_commerce.founder_directives
  for each row execute function penta_runtime.protect_flow_founder_directive_v1();

-- ---------------------------------------------------------------------------
-- Seed the exact time-bound directive, immutable binding, zero-cost budget,
-- factory snapshots and implementation-level component registry entries.
-- ---------------------------------------------------------------------------

do $$
declare
  v_now timestamptz := clock_timestamp();
  v_repositories jsonb;
  v_factories jsonb;
  v_scope jsonb;
  v_scope_sha text;
  v_directive developer_commerce.founder_directives%rowtype;
begin
  select * into v_directive
  from developer_commerce.founder_directives
  where directive_id = 'ct-founder-directive-penta-flow-control-20260826-v1';

  if not found then
    select coalesce(jsonb_agg(r.repository_full_name order by r.repository_full_name), '[]'::jsonb)
    into v_repositories
    from penta_runtime.repository_registry_v1 r
    where r.enabled;

    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'project_id', p.id,
          'project_key', p.project_key,
          'repository', p.repo_full_name,
          'production_enabled', p.production_enabled,
          'autonomy_enabled', p.autonomy_enabled
        ) order by p.project_key
      ),
      '[]'::jsonb
    ) into v_factories
    from public.ct_factory_projects p
    where p.production_enabled and p.autonomy_enabled;

    if jsonb_array_length(v_repositories) = 0 then
      raise exception 'no enabled repository snapshot available for bounded campaign';
    end if;
    if jsonb_array_length(v_factories) = 0 then
      raise exception 'no production/autonomous factory snapshot available for bounded campaign';
    end if;

    v_scope := jsonb_build_object(
      'campaign_id', 'ct.penta.flow-control.20260826.v1',
      'duration_seconds', 1209600,
      'authorized_actions', jsonb_build_array(
        'admit_factory_candidates',
        'execute_bounded_candidates',
        'factory_candidate_dispatch',
        'build_and_test',
        'request_independent_certification',
        'promote_only_after_all_independent_gates',
        'publish_deduplicated_consolidated_reports'
      ),
      'allowed_source_types', jsonb_build_array(
        'penta_runtime', 'institutional_backlog', 'penta_helper'
      ),
      'repository_snapshot', v_repositories,
      'factory_snapshot', v_factories,
      'authorization_limits', jsonb_build_object(
        'max_concurrency', 4,
        'max_claim_batch', 8,
        'max_cost_minor', 0,
        'cost_currency', 'USD',
        'max_internal_units', 1000000,
        'internal_unit_ceiling', 9223372036854775807
      ),
      'required_gates', jsonb_build_array(
        'technical_tests', 'security_review', 'exact_head_evidence',
        'independent_verification', 'rollback_readback', 'budget_precommit'
      ),
      'explicit_denials', jsonb_build_array(
        'self_certification', 'self_approval', 'independent_evidence_substitution',
        'ungated_provider_write', 'money_movement', 'payment', 'settlement',
        'pricing', 'treasury', 'accounting_authority', 'rights_disposition',
        'license_grant', 'credential_rotation', 'raw_secret_export',
        'destructive_mutation', 'authority_delegation', 'automatic_renewal'
      ),
      'provider_lane_initial_state', 'hold',
      'raw_directive_text_retained', false,
      'source_retention', 'sha256_and_public_safe_scope_only'
    );

    insert into developer_commerce.founder_directives(
      directive_id, founder_ref, directive_class, scope, source_sha256,
      authority_effect, independent_evidence_substitution_allowed, recorded_at
    ) values (
      'ct-founder-directive-penta-flow-control-20260826-v1',
      'ct.person.founder.kavonte-jones-sr',
      'release_authorization',
      v_scope,
      '11bfa746c993f5862f70b9afee1dd6c7ea709c2de85bb39d6fa782c0860e7661',
      'Authorizes bounded build/test/certification-request and independently gated promotion work for exactly fourteen days; creates no substitute evidence or other authority.',
      false,
      v_now
    );

    select * into v_directive
    from developer_commerce.founder_directives
    where directive_id = 'ct-founder-directive-penta-flow-control-20260826-v1';
  end if;

  if v_directive.founder_ref is distinct from 'ct.person.founder.kavonte-jones-sr'
     or v_directive.directive_class is distinct from 'release_authorization'
     or v_directive.source_sha256 is distinct from '11bfa746c993f5862f70b9afee1dd6c7ea709c2de85bb39d6fa782c0860e7661'
     or v_directive.independent_evidence_substitution_allowed is distinct from false
     or v_directive.scope->>'campaign_id' is distinct from 'ct.penta.flow-control.20260826.v1'
     or (v_directive.scope->>'duration_seconds')::integer is distinct from 1209600
     or (v_directive.scope#>>'{authorization_limits,max_concurrency}')::integer is distinct from 4
     or (v_directive.scope#>>'{authorization_limits,max_claim_batch}')::integer is distinct from 8
     or (v_directive.scope#>>'{authorization_limits,max_cost_minor}')::bigint is distinct from 0
     or (v_directive.scope#>>'{authorization_limits,max_internal_units}')::bigint is distinct from 1000000
     or v_directive.scope->>'provider_lane_initial_state' is distinct from 'hold'
     or jsonb_typeof(v_directive.scope->'repository_snapshot') is distinct from 'array'
     or jsonb_typeof(v_directive.scope->'factory_snapshot') is distinct from 'array'
  then
    raise exception 'existing bounded flow-control Founder directive does not match the exact immutable authority envelope';
  end if;

  v_scope_sha := encode(
    extensions.digest(convert_to(v_directive.scope::text, 'UTF8'), 'sha256'),
    'hex'
  );

  insert into penta_runtime.d3_campaign_bindings_v1(
    campaign_id, directive_id, founder_ref, directive_source_sha256,
    scope_sha256, starts_at, expires_at, authorized_actions,
    allowed_source_types, repository_snapshot, factory_snapshot,
    max_concurrency, max_claim_batch, max_cost_minor, max_internal_units
  ) values (
    'ct.penta.flow-control.20260826.v1',
    v_directive.directive_id,
    v_directive.founder_ref,
    v_directive.source_sha256,
    v_scope_sha,
    v_directive.recorded_at,
    v_directive.recorded_at + interval '14 days',
    array(select jsonb_array_elements_text(v_directive.scope->'authorized_actions')),
    array(select jsonb_array_elements_text(v_directive.scope->'allowed_source_types')),
    v_directive.scope->'repository_snapshot',
    v_directive.scope->'factory_snapshot',
    (v_directive.scope#>>'{authorization_limits,max_concurrency}')::integer,
    (v_directive.scope#>>'{authorization_limits,max_claim_batch}')::integer,
    (v_directive.scope#>>'{authorization_limits,max_cost_minor}')::bigint,
    (v_directive.scope#>>'{authorization_limits,max_internal_units}')::bigint
  ) on conflict (campaign_id) do nothing;

  if not exists (
    select 1 from penta_runtime.d3_campaign_bindings_v1 b
    where b.campaign_id = 'ct.penta.flow-control.20260826.v1'
      and b.directive_id = v_directive.directive_id
      and b.scope_sha256 = v_scope_sha
      and b.starts_at = v_directive.recorded_at
      and b.expires_at = v_directive.recorded_at + interval '14 days'
      and b.max_concurrency = 4
      and b.max_claim_batch = 8
      and b.max_cost_minor = 0
      and b.max_internal_units = 1000000
      and b.authorized_actions = array(
        select jsonb_array_elements_text(v_directive.scope->'authorized_actions')
      )
      and b.allowed_source_types = array(
        select jsonb_array_elements_text(v_directive.scope->'allowed_source_types')
      )
      and b.repository_snapshot = v_directive.scope->'repository_snapshot'
      and b.factory_snapshot = v_directive.scope->'factory_snapshot'
      and b.independent_evidence_required
      and not b.provider_write_authority
      and not b.money_movement_authority
      and not b.rights_disposition_authority
      and not b.credential_authority
      and b.nonrenewing
  ) then
    raise exception 'existing campaign binding does not match canonical Founder directive';
  end if;
end;
$$;

insert into penta_runtime.cost_rate_books_v1(
  rate_key, campaign_id, operation_key, unit_key, rate_units, cost_minor, cost_currency,
  effective_at, expires_at, source_sha256, metadata
)
select
  'ct.penta.flow-control.internal-factory-build.v1',
  b.campaign_id,
  'factory_build',
  'internal_estimate_unit',
  100,
  0,
  'USD',
  b.starts_at,
  b.expires_at,
  b.scope_sha256,
  jsonb_build_object(
    'penta_member', 'PentaRate',
    'versioned_immutable', true,
    'non_monetary', true,
    'provider_charge_authority', false
  )
from penta_runtime.d3_campaign_bindings_v1 b
where b.campaign_id = 'ct.penta.flow-control.20260826.v1'
on conflict (rate_key) do nothing;

insert into penta_runtime.cost_unit_budgets_v1(
  budget_key, campaign_id, ceiling_units, reserved_units, accounted_units,
  state, starts_at, expires_at, metadata
)
select
  'ct.penta.flow-control.20260826.v1.units',
  b.campaign_id,
  b.max_internal_units,
  0,
  0,
  'implemented',
  b.starts_at,
  b.expires_at,
  jsonb_build_object(
    'penta_member','PentaBudget',
    'unit_key','internal_estimate_unit',
    'activation_required',true,
    'cash_or_provider_cost',false
  )
from penta_runtime.d3_campaign_bindings_v1 b
where b.campaign_id = 'ct.penta.flow-control.20260826.v1'
on conflict (budget_key) do nothing;

do $$
begin
  if not exists (
    select 1
    from penta_runtime.cost_rate_books_v1 rb
    join penta_runtime.d3_campaign_bindings_v1 b using (campaign_id)
    where rb.rate_key = 'ct.penta.flow-control.internal-factory-build.v1'
      and rb.operation_key = 'factory_build'
      and rb.unit_key = 'internal_estimate_unit'
      and rb.rate_units = 100
      and rb.cost_minor = 0
      and rb.cost_currency = 'USD'
      and rb.effective_at = b.starts_at
      and rb.expires_at = b.expires_at
      and rb.source_sha256 = b.scope_sha256
      and rb.implementation_state = 'implemented'
  ) then
    raise exception 'internal unit rate collision or invariant mismatch';
  end if;
  if not exists (
    select 1
    from penta_runtime.cost_unit_budgets_v1 ub
    join penta_runtime.d3_campaign_bindings_v1 b using (campaign_id)
    where ub.budget_key = 'ct.penta.flow-control.20260826.v1.units'
      and ub.ceiling_units = b.max_internal_units
      and ub.cash_or_provider_cost_minor = 0
      and ub.reserved_units = 0
      and ub.accounted_units = 0
      and ub.state = 'implemented'
      and ub.starts_at = b.starts_at
      and ub.expires_at = b.expires_at
  ) then
    raise exception 'internal unit budget collision or invariant mismatch';
  end if;
end;
$$;

insert into penta_runtime.factory_target_adapters_v1(
  target_adapter_key, target_kind, interface_version, claim_semantics,
  idempotency_semantics, fencing_semantics, supported, eligible, state, metadata
) values
(
  'ct.factory.v4', 'ct_factory', 'ct.factory.v4',
  'penta_runtime.flow_jobs_v1 lease then dispatch_outbox_v1 consumption',
  'flow_jobs_v1.job_key plus dispatch_outbox_v1.outbox_key',
  'flow_jobs_v1 monotonically increasing fencing_token',
  true, false, 'hold',
  jsonb_build_object('exact_route_only',true,'runtime_activation_required',true)
),
(
  'framework.factory.jobs.v2', 'framework_factory_jobs_v2', 'unknown',
  'not_reconciled', 'not_reconciled', 'not_reconciled',
  false, false, 'hold', jsonb_build_object('reason','claim_idempotency_fencing_contract_not_certified')
),
(
  'proprietary.factory.run.queue', 'proprietary_factory_run_queue', 'unknown',
  'not_reconciled', 'not_reconciled', 'not_reconciled',
  false, false, 'hold', jsonb_build_object('reason','claim_idempotency_fencing_contract_not_certified')
),
(
  'gen6.skill.factory.requests', 'gen6_skill_factory_requests', 'unknown',
  'not_reconciled', 'not_reconciled', 'not_reconciled',
  false, false, 'hold', jsonb_build_object('reason','claim_idempotency_fencing_contract_not_certified')
),
(
  'product.factory.jobs', 'product_factory.factory_jobs', 'unknown',
  'not_reconciled', 'not_reconciled', 'not_reconciled',
  false, false, 'hold', jsonb_build_object('reason','claim_idempotency_fencing_contract_not_certified')
)
on conflict do nothing;

do $$
begin
  if (
    select count(*)
    from penta_runtime.factory_target_adapters_v1
    where target_adapter_key in (
      'ct.factory.v4','framework.factory.jobs.v2','proprietary.factory.run.queue',
      'gen6.skill.factory.requests','product.factory.jobs'
    )
  ) <> 5 then
    raise exception 'target adapter registry collision or missing immutable HOLD row';
  end if;
  if exists (
    select 1 from penta_runtime.factory_target_adapters_v1
    where target_adapter_key in (
      'ct.factory.v4','framework.factory.jobs.v2','proprietary.factory.run.queue',
      'gen6.skill.factory.requests','product.factory.jobs'
    ) and (eligible or state<>'hold' or direct_table_mutation)
  ) then
    raise exception 'all target adapters must begin in immutable HOLD';
  end if;
end;
$$;

insert into penta_runtime.factory_routes_v1(
  route_key, campaign_id, target_adapter_key, project_id, project_key, factory_repository,
  allowed_target_repositories, release_channel, max_inflight,
  max_claim_batch, weight, enabled, provider_claim_enabled
)
select
  'penta.factory.' || p.project_key,
  b.campaign_id,
  'ct.factory.v4',
  p.id,
  p.project_key,
  p.repo_full_name,
  array(select jsonb_array_elements_text(b.repository_snapshot)),
  'staging',
  b.max_concurrency,
  b.max_claim_batch,
  100,
  false,
  false
from penta_runtime.d3_campaign_bindings_v1 b
join public.ct_factory_projects p
  on exists (
    select 1
    from jsonb_array_elements(b.factory_snapshot) f
    where f->>'project_id' = p.id::text
      and f->>'project_key' = p.project_key
  )
where b.campaign_id = 'ct.penta.flow-control.20260826.v1'
  and p.production_enabled and p.autonomy_enabled
on conflict (route_key) do nothing;

do $$
begin
  if not exists (
    select 1 from penta_runtime.factory_routes_v1
    where campaign_id = 'ct.penta.flow-control.20260826.v1'
      and not enabled and not provider_claim_enabled
  ) then
    raise exception 'no fail-closed factory route was bound to the campaign snapshot';
  end if;
  if exists (
    select 1 from penta_runtime.factory_routes_v1
    where campaign_id = 'ct.penta.flow-control.20260826.v1'
      and (enabled or provider_claim_enabled or target_adapter_key <> 'ct.factory.v4')
  ) then
    raise exception 'all immutable v1 factory routes must begin disabled and provider-HOLD';
  end if;
end;
$$;

-- PentaQueue is a PentaRoute primitive, not a competing top-level component.
insert into penta_runtime.component_registry_rollback_v1(
  campaign_id,component_key,prior_row,prior_row_sha256
)
select
  'ct.penta.flow-control.20260826.v1',
  c.component_key,
  to_jsonb(c),
  encode(extensions.digest(convert_to(to_jsonb(c)::text,'UTF8'),'sha256'),'hex')
from penta_runtime.component_registry_v1 c
where c.component_key='penta.route'
on conflict (campaign_id,component_key) do nothing;

update penta_runtime.component_registry_v1
set canonical_name = 'PentaRoute',
    role = 'routing and delivery umbrella governing distinct route primitives',
    primary_axis = 'interoperation',
    stable_contract_id = 'ct.penta.route.v3',
    aliases = '{}'::text[],
    backing_refs = coalesce(backing_refs, '{}'::jsonb) || jsonb_build_object(
      'flow_queue_runtime', 'penta_runtime.flow_jobs_v1',
      'flow_queue_contract', 'crownthrive.penta.runtime-flow-control.v1'
    ),
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'flow_queue_primitive', 'PentaQueue',
      'primitive_of', 'penta.route',
      'route_contract', 'ct.penta.route.v3',
      'controlled_test_only', true,
      'penta_queue_role', 'bounded admission lease fencing retry and hold',
      'penta_queue_authority_effect', false
    ),
    updated_at = clock_timestamp()
where component_key = 'penta.route'
  and (
    canonical_name is distinct from 'PentaRoute'
    or role is distinct from 'routing and delivery umbrella governing distinct route primitives'
    or primary_axis is distinct from 'interoperation'
    or stable_contract_id is distinct from 'ct.penta.route.v3'
    or cardinality(aliases) <> 0
    or
    backing_refs->>'flow_queue_runtime' is distinct from 'penta_runtime.flow_jobs_v1'
    or backing_refs->>'flow_queue_contract' is distinct from 'crownthrive.penta.runtime-flow-control.v1'
    or metadata->>'primitive_of' is distinct from 'penta.route'
    or metadata->>'route_contract' is distinct from 'ct.penta.route.v3'
  );

do $$
begin
  if not exists (
    select 1 from penta_runtime.component_registry_v1
    where component_key = 'penta.route'
      and stable_contract_id = 'ct.penta.route.v3'
      and canonical_name = 'PentaRoute'
      and role = 'routing and delivery umbrella governing distinct route primitives'
      and primary_axis = 'interoperation'
      and cardinality(aliases) = 0
      and backing_refs->>'flow_queue_runtime' = 'penta_runtime.flow_jobs_v1'
      and metadata->>'primitive_of' = 'penta.route'
      and metadata->>'flow_queue_primitive' = 'PentaQueue'
  ) then
    raise exception 'canonical penta.route registry entry is required for PentaQueue binding';
  end if;
end;
$$;

insert into penta_runtime.component_registry_v1(
  component_key, canonical_name, role, primary_axis, stable_contract_id,
  implementation_state, aliases, backing_refs, metadata, enabled
) values
(
  'penta.load', 'PentaLoad', 'demand capacity and utilization measurement',
  'execution', 'ct.penta.load.v1', 'implemented', '{}'::text[],
  jsonb_build_object('runtime', 'penta_runtime.load_snapshots_v1'),
  jsonb_build_object('pack_id','crownthrive.penta.runtime-flow-control.v1','controlled_test_only',true,'certified',false,'authority_effect',false),
  false
),
(
  'penta.balancer', 'PentaBalancer', 'redundancy restoration load shedding and bounded capacity growth',
  'execution', 'ct.penta.balancer.v1', 'implemented', array['PentaLoadBalancer']::text[],
  jsonb_build_object('runtime', 'penta_runtime.select_route_v1'),
  jsonb_build_object('pack_id','crownthrive.penta.runtime-flow-control.v1','controlled_test_only',true,'certified',false,'authority_effect',false),
  false
),
(
  'penta.costs', 'PentaCosts', 'cost-pressure detection and controlled recession recommendations without money movement',
  'authority', 'ct.penta.costs.v1', 'implemented', '{}'::text[],
  jsonb_build_object(
    'rate_book','penta_runtime.cost_rate_books_v1',
    'meter','penta_runtime.cost_usage_events_v1',
    'unit_budget','penta_runtime.cost_unit_budgets_v1',
    'cash_provider_cost_invariant','penta_runtime.d3_campaign_bindings_v1.max_cost_minor=0',
    'ledger','penta_runtime.cost_ledger_entries_v1',
    'forecast','penta_runtime.cost_forecasts_v1'
  ),
  jsonb_build_object(
    'pack_id','crownthrive.penta.runtime-flow-control.v1',
    'controlled_test_only',true,
    'certified',false,
    'money_movement',false,
    'accounting_authority',false
  ),
  false
)
on conflict do nothing;

do $$
declare r record;
begin
  for r in
    select * from (values
      ('penta.load','PentaLoad','demand capacity and utilization measurement','execution','ct.penta.load.v1','{}'::text[]),
      ('penta.balancer','PentaBalancer','redundancy restoration load shedding and bounded capacity growth','execution','ct.penta.balancer.v1',array['PentaLoadBalancer']::text[]),
      ('penta.costs','PentaCosts','cost-pressure detection and controlled recession recommendations without money movement','authority','ct.penta.costs.v1','{}'::text[])
    ) as expected(component_key, canonical_name, role, primary_axis, stable_contract_id, aliases)
  loop
    if not exists (
      select 1 from penta_runtime.component_registry_v1 c
      where c.component_key = r.component_key
        and c.canonical_name = r.canonical_name
        and c.role = r.role
        and c.primary_axis = r.primary_axis
        and c.stable_contract_id = r.stable_contract_id
        and c.aliases = r.aliases
        and c.implementation_state = 'implemented'
        and not c.enabled
    ) then
      raise exception 'component registry collision for %', r.component_key;
    end if;
  end loop;
  if exists (
    select 1 from penta_runtime.component_registry_v1
    where component_key in ('penta.queue','penta.cost')
      and metadata->>'pack_id' = 'crownthrive.penta.runtime-flow-control.v1'
  ) then
    raise exception 'flow-control pack must not create competing penta.queue or penta.cost components';
  end if;
end;
$$;

-- Provider containment was installed by the preceding emergency migrations.
-- This capability pack does not mutate provider state; it refuses installation
-- if that independently installed boundary is not already in force.
do $$
begin
  if not exists (
    select 1 from public.ct_factory_provider_adapters
    where adapter_key='ct.adapter.github.actions.v1' and not enabled
  ) then raise exception 'github_provider_adapter_must_remain_disabled'; end if;
  if exists (
    select 1 from public.ct_factory_provider_jobs
    where adapter_key='ct.adapter.github.actions.v1' and state in ('queued','claimed')
  ) then raise exception 'github_provider_jobs_must_remain_held'; end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- Campaign/activation checks.  Mutating entry points call the active assertion;
-- reporting and authority-reducing cleanup may operate after expiry.
-- ---------------------------------------------------------------------------

create or replace function penta_runtime.campaign_status_v1(p_campaign_id text)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  b penta_runtime.d3_campaign_bindings_v1%rowtype;
  v_now timestamptz := clock_timestamp();
  v_hold boolean;
  v_activation_present boolean;
  v_activation boolean;
  v_components boolean;
  v_budget boolean;
  v_provider_contained boolean;
begin
  select * into b
  from penta_runtime.d3_campaign_bindings_v1
  where campaign_id = p_campaign_id;
  if not found then
    return jsonb_build_object('campaign_id',p_campaign_id,'state','missing','runtime_active',false);
  end if;

  select exists(
    select 1 from penta_runtime.d3_campaign_holds_v1 h
    where h.campaign_id = b.campaign_id
  ) into v_hold;
  select exists(
    select 1 from penta_runtime.runtime_activation_receipts_v1 a
    join penta_runtime.runtime_release_baselines_v1 rb
      on rb.baseline_id=a.baseline_id and rb.campaign_id=a.campaign_id
    where a.campaign_id = b.campaign_id
  ) into v_activation_present;
  select exists(
    select 1 from penta_runtime.runtime_activation_receipts_v1 a
    where a.campaign_id = b.campaign_id
      and a.state = 'active'
      and a.activated_at <= v_now and v_now < a.expires_at
      and a.expires_at <= b.expires_at
      and a.independent_verifier_ref is distinct from b.founder_ref
      and rb.state='verified'
      and rb.exact_head_sha=a.exact_head_sha
      and rb.migration_sha256=a.migration_sha256
      and rb.technical_evidence_sha256=a.technical_evidence_sha256
      and rb.security_evidence_sha256=a.security_evidence_sha256
      and rb.independent_verifier_ref=a.independent_verifier_ref
      and rb.independent_verification_sha256=a.independent_verification_sha256
      and rb.rollback_ref=a.rollback_ref
      and rb.verified_by is distinct from b.founder_ref
      and rb.verified_at <= a.activated_at
      and not a.self_certification
      and not exists (
        select 1 from unnest(a.activated_route_keys) k
        where not exists (
          select 1 from penta_runtime.factory_routes_v1 r
          where r.route_key=k and r.campaign_id=b.campaign_id
            and r.target_adapter_key=any(a.certified_target_adapter_keys)
        )
      )
      and not exists (
        select 1 from unnest(a.certified_target_adapter_keys) k
        where not exists (
          select 1 from penta_runtime.factory_target_adapters_v1 ta
          where ta.target_adapter_key=k and ta.supported
        )
      )
  ) into v_activation;
  select exists (
    select 1 from penta_runtime.component_registry_v1 c
    where c.enabled and c.implementation_state='active' and (
      (c.component_key='penta.load' and c.stable_contract_id='ct.penta.load.v1'
        and c.primary_axis='execution' and c.role='demand capacity and utilization measurement')
      or (c.component_key='penta.balancer' and c.stable_contract_id='ct.penta.balancer.v1'
        and c.primary_axis='execution' and c.role='redundancy restoration load shedding and bounded capacity growth')
      or (c.component_key='penta.costs' and c.stable_contract_id='ct.penta.costs.v1'
        and c.primary_axis='authority' and c.role='cost-pressure detection and controlled recession recommendations without money movement')
    )
    group by true having count(*) = 3
  ) into v_components;
  select exists (
    select 1 from penta_runtime.cost_unit_budgets_v1 ub
    where ub.campaign_id=b.campaign_id and ub.state='active'
      and ub.cash_or_provider_cost_minor=0
      and ub.starts_at<=v_now and v_now<ub.expires_at
  ) into v_budget;
  select (
    exists (
      select 1 from public.ct_factory_provider_adapters
      where adapter_key='ct.adapter.github.actions.v1' and not enabled
    )
    and not exists (
      select 1 from public.ct_factory_provider_jobs
      where adapter_key='ct.adapter.github.actions.v1' and state in ('queued','claimed')
    )
  ) into v_provider_contained;

  return jsonb_build_object(
    'campaign_id',b.campaign_id,
    'directive_id',b.directive_id,
    'starts_at',b.starts_at,
    'expires_at',b.expires_at,
    'time_state',case
      when v_now < b.starts_at then 'not_started'
      when v_now >= b.expires_at then 'expired'
      else 'within_window'
    end,
    'held',v_hold,
    'activation_receipt_present',v_activation_present,
    'activation_receipt_valid',v_activation,
    'components_active',v_components,
    'internal_unit_budget_active',v_budget,
    'github_provider_contained',v_provider_contained,
    'runtime_active',(
      b.starts_at <= v_now and v_now < b.expires_at and not v_hold
      and v_activation and v_components and v_budget and v_provider_contained
    ),
    'provider_write_authority',false,
    'money_movement_authority',false,
    'independent_evidence_required',true
  );
end;
$$;

create or replace function penta_runtime.assert_runtime_active_v1(
  p_campaign_id text,
  p_action text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  b penta_runtime.d3_campaign_bindings_v1%rowtype;
  d developer_commerce.founder_directives%rowtype;
  a penta_runtime.runtime_activation_receipts_v1%rowtype;
  rb penta_runtime.runtime_release_baselines_v1%rowtype;
  v_now timestamptz := clock_timestamp();
  v_scope_sha text;
begin
  perform pg_advisory_xact_lock_shared(
    hashtextextended('penta_runtime.campaign:'||p_campaign_id,0)
  );
  select * into b
  from penta_runtime.d3_campaign_bindings_v1
  where campaign_id = p_campaign_id;
  if not found then raise exception 'campaign_not_found' using errcode='42501'; end if;

  select * into d
  from developer_commerce.founder_directives
  where directive_id = b.directive_id;
  if not found then raise exception 'canonical_founder_directive_missing' using errcode='42501'; end if;

  v_scope_sha := encode(
    extensions.digest(convert_to(d.scope::text,'UTF8'),'sha256'), 'hex'
  );
  if d.source_sha256 is distinct from b.directive_source_sha256
     or v_scope_sha is distinct from b.scope_sha256
     or d.recorded_at is distinct from b.starts_at
     or d.directive_class is distinct from 'release_authorization'
     or d.founder_ref is distinct from b.founder_ref
     or d.independent_evidence_substitution_allowed is distinct from false
  then
    raise exception 'campaign_directive_binding_invalid' using errcode='42501';
  end if;
  if p_action is null or not coalesce(p_action = any(b.authorized_actions),false) then
    raise exception 'action_outside_campaign_scope' using errcode='42501';
  end if;
  if v_now < b.starts_at or v_now >= b.expires_at then
    raise exception 'campaign_outside_time_window' using errcode='42501';
  end if;
  if exists (
    select 1 from penta_runtime.d3_campaign_holds_v1 h
    where h.campaign_id = b.campaign_id
  ) then
    raise exception 'campaign_held' using errcode='42501';
  end if;

  select * into a
  from penta_runtime.runtime_activation_receipts_v1
  where campaign_id = b.campaign_id
    and state = 'active'
    and activated_at <= v_now and v_now < expires_at
    and expires_at <= b.expires_at;
  if not found then
    raise exception 'runtime_activation_exact_evidence_required' using errcode='42501';
  end if;
  if a.independent_verifier_ref is not distinct from b.founder_ref
     or a.self_certification is distinct from false then
    raise exception 'independent_runtime_activation_required' using errcode='42501';
  end if;
  select * into rb
  from penta_runtime.runtime_release_baselines_v1
  where baseline_id=a.baseline_id and campaign_id=b.campaign_id
    and state='verified';
  if not found
     or rb.exact_head_sha is distinct from a.exact_head_sha
     or rb.migration_sha256 is distinct from a.migration_sha256
     or rb.technical_evidence_sha256 is distinct from a.technical_evidence_sha256
     or rb.security_evidence_sha256 is distinct from a.security_evidence_sha256
     or rb.independent_verifier_ref is distinct from a.independent_verifier_ref
     or rb.independent_verification_sha256 is distinct from a.independent_verification_sha256
     or rb.rollback_ref is distinct from a.rollback_ref
     or rb.verified_by is not distinct from b.founder_ref
     or rb.verified_at > a.activated_at
  then
    raise exception 'runtime_activation_baseline_binding_invalid' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.ct_factory_provider_adapters
    where adapter_key='ct.adapter.github.actions.v1' and not enabled
  ) or exists (
    select 1 from public.ct_factory_provider_jobs
    where adapter_key='ct.adapter.github.actions.v1' and state in ('queued','claimed')
  ) then
    raise exception 'github_provider_containment_required' using errcode='42501';
  end if;
  if exists (
    select 1 from unnest(a.activated_route_keys) k
    where not exists (
      select 1 from penta_runtime.factory_routes_v1 r
      where r.route_key=k and r.campaign_id=b.campaign_id
        and r.target_adapter_key=any(a.certified_target_adapter_keys)
    )
  ) then
    raise exception 'activation_route_or_target_binding_invalid' using errcode='42501';
  end if;
  if exists (
    select 1 from unnest(a.certified_target_adapter_keys) k
    where not exists (
      select 1 from penta_runtime.factory_target_adapters_v1 ta
      where ta.target_adapter_key=k and ta.supported
    )
  ) then
    raise exception 'activation_target_adapter_not_implemented' using errcode='42501';
  end if;
  if not exists (
    select 1
    from penta_runtime.component_registry_v1 c
    where c.enabled and c.implementation_state='active' and (
      (c.component_key='penta.load' and c.stable_contract_id='ct.penta.load.v1'
        and c.primary_axis='execution' and c.role='demand capacity and utilization measurement')
      or (c.component_key='penta.balancer' and c.stable_contract_id='ct.penta.balancer.v1'
        and c.primary_axis='execution' and c.role='redundancy restoration load shedding and bounded capacity growth')
      or (c.component_key='penta.costs' and c.stable_contract_id='ct.penta.costs.v1'
        and c.primary_axis='authority' and c.role='cost-pressure detection and controlled recession recommendations without money movement')
    )
    group by true having count(*) = 3
  ) then
    raise exception 'runtime_components_not_activated' using errcode='42501';
  end if;
  if not exists (
    select 1 from penta_runtime.cost_unit_budgets_v1 ub
    where ub.campaign_id=b.campaign_id and ub.state='active'
      and ub.cash_or_provider_cost_minor=0
      and ub.starts_at<=v_now and v_now<ub.expires_at
  ) then
    raise exception 'internal_unit_budget_not_activated' using errcode='42501';
  end if;

  return jsonb_build_object(
    'campaign_id',b.campaign_id,
    'directive_id',b.directive_id,
    'scope_sha256',b.scope_sha256,
    'activation_id',a.activation_id,
    'exact_head_sha',a.exact_head_sha,
    'expires_at',least(b.expires_at,a.expires_at),
    'activated_route_keys',to_jsonb(a.activated_route_keys),
    'certified_target_adapter_keys',to_jsonb(a.certified_target_adapter_keys)
  );
end;
$$;

create or replace function penta_runtime.hold_campaign_v1(
  p_campaign_id text,
  p_hold_reason text,
  p_evidence_sha256 text,
  p_held_by text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare v_held_at timestamptz;
begin
  -- HOLD takes the exclusive campaign lock used in shared mode by every
  -- execution assertion, so a hold and a new execution transition cannot
  -- cross one another inside separate transactions.
  perform pg_advisory_xact_lock(
    hashtextextended('penta_runtime.campaign:'||p_campaign_id,0)
  );
  if p_evidence_sha256 is null or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'hold_evidence_sha256_invalid';
  end if;
  insert into penta_runtime.d3_campaign_holds_v1(
    campaign_id,hold_reason,evidence_sha256,held_by
  ) values (
    p_campaign_id,left(btrim(p_hold_reason),1000),p_evidence_sha256,p_held_by
  ) on conflict (campaign_id) do nothing
  returning held_at into v_held_at;
  if v_held_at is null then
    select held_at into v_held_at
    from penta_runtime.d3_campaign_holds_v1 where campaign_id=p_campaign_id;
  end if;
  return jsonb_build_object('campaign_id',p_campaign_id,'held',true,'held_at',v_held_at);
end;
$$;

-- ---------------------------------------------------------------------------
-- PentaCosts: separate internal resource units from the immutable zero cash/
-- provider-cost ceiling.  These transitions are atomic and idempotent.
-- ---------------------------------------------------------------------------

create or replace function penta_runtime.reserve_units_v1(
  p_campaign_id text,
  p_job_id uuid,
  p_reservation_key text,
  p_rate_key text,
  p_quantity bigint,
  p_evidence_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  v_rate penta_runtime.cost_rate_books_v1%rowtype;
  v_budget penta_runtime.cost_unit_budgets_v1%rowtype;
  v_job penta_runtime.flow_jobs_v1%rowtype;
  v_existing penta_runtime.cost_reservations_v1%rowtype;
  v_reservation penta_runtime.cost_reservations_v1%rowtype;
  v_units_numeric numeric;
  v_units bigint;
begin
  perform penta_runtime.assert_runtime_active_v1(p_campaign_id,'execute_bounded_candidates');
  if p_quantity is null or p_quantity <= 0 then raise exception 'quantity_must_be_positive'; end if;
  if p_evidence_sha256 is null or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'evidence_sha256_invalid'; end if;

  -- Lock and bind the exact campaign job first.  This prevents cross-campaign
  -- reservation attachment and serializes idempotent admissions for one job.
  select * into v_job from penta_runtime.flow_jobs_v1
  where job_id=p_job_id and campaign_id=p_campaign_id for update;
  if not found then raise exception 'campaign_flow_job_not_found'; end if;

  select * into v_rate from penta_runtime.cost_rate_books_v1
  where rate_key=p_rate_key and campaign_id=p_campaign_id
    and effective_at <= clock_timestamp() and clock_timestamp() < expires_at;
  if not found then raise exception 'active_rate_not_found'; end if;
  if v_rate.cost_minor <> 0 or v_rate.cost_currency <> 'USD' then
    raise exception 'cash_or_provider_cost_not_authorized' using errcode='42501';
  end if;

  v_units_numeric := v_rate.rate_units::numeric * p_quantity::numeric;
  if v_units_numeric > 9223372036854775807::numeric then raise exception 'internal_unit_overflow'; end if;
  v_units := v_units_numeric::bigint;
  if v_job.estimated_units is distinct from v_units
     or v_job.estimated_cost_minor is distinct from 0
     or v_job.reserved_cost_minor is distinct from 0
  then raise exception 'flow_job_internal_unit_binding_invalid'; end if;

  select * into v_existing from penta_runtime.cost_reservations_v1
  where reservation_key=p_reservation_key
     or (campaign_id=p_campaign_id and job_id=p_job_id)
  limit 1;
  if found then
    if v_existing.reservation_key is distinct from p_reservation_key
       or v_existing.campaign_id is distinct from p_campaign_id
       or v_existing.job_id is distinct from p_job_id
       or v_existing.rate_key is distinct from p_rate_key
       or v_existing.quantity is distinct from p_quantity
       or v_existing.estimated_units is distinct from v_units
       or v_existing.estimated_cost_minor is distinct from 0
       or v_existing.evidence_sha256 is distinct from p_evidence_sha256
    then raise exception 'reservation_idempotency_conflict'; end if;
    return to_jsonb(v_existing);
  end if;

  select * into v_budget from penta_runtime.cost_unit_budgets_v1
  where campaign_id=p_campaign_id for update;
  if not found or v_budget.state <> 'active' then raise exception 'internal_unit_budget_not_active'; end if;
  if clock_timestamp() >= v_budget.expires_at then raise exception 'internal_unit_budget_expired'; end if;

  -- A competing reservation key can target another job while waiting on the
  -- shared budget row.  Re-read after that serialization point before debit.
  select * into v_existing from penta_runtime.cost_reservations_v1
  where reservation_key=p_reservation_key
     or (campaign_id=p_campaign_id and job_id=p_job_id)
  limit 1;
  if found then
    if v_existing.reservation_key is distinct from p_reservation_key
       or v_existing.campaign_id is distinct from p_campaign_id
       or v_existing.job_id is distinct from p_job_id
       or v_existing.rate_key is distinct from p_rate_key
       or v_existing.quantity is distinct from p_quantity
       or v_existing.estimated_units is distinct from v_units
       or v_existing.estimated_cost_minor is distinct from 0
       or v_existing.evidence_sha256 is distinct from p_evidence_sha256
    then raise exception 'reservation_idempotency_conflict'; end if;
    return to_jsonb(v_existing);
  end if;
  if v_budget.reserved_units + v_budget.accounted_units + v_units > v_budget.ceiling_units then
    raise exception 'internal_unit_budget_exceeded';
  end if;

  insert into penta_runtime.cost_reservations_v1(
    reservation_key,campaign_id,job_id,unit_budget_id,rate_key,
    quantity,estimated_units,estimated_cost_minor,cost_currency,state,evidence_sha256
  ) values (
    p_reservation_key,p_campaign_id,p_job_id,v_budget.unit_budget_id,
    p_rate_key,p_quantity,v_units,0,'USD','reserved',p_evidence_sha256
  ) returning * into v_reservation;

  update penta_runtime.cost_unit_budgets_v1
  set reserved_units=reserved_units+v_units,updated_at=clock_timestamp()
  where unit_budget_id=v_budget.unit_budget_id;
  update penta_runtime.flow_jobs_v1
  set reserved_units=v_units,reserved_cost_minor=0,updated_at=clock_timestamp()
  where job_id=p_job_id and campaign_id=p_campaign_id;

  insert into penta_runtime.cost_ledger_entries_v1(
    entry_key,campaign_id,job_id,reservation_id,entry_kind,amount_units,
    cost_minor,cost_currency,evidence_sha256,metadata
  ) values (
    p_reservation_key||':reserve',p_campaign_id,p_job_id,v_reservation.reservation_id,
    'reserve',v_units,0,'USD',p_evidence_sha256,
    jsonb_build_object('penta_member','PentaCostLedger','non_accounting',true)
  );
  return to_jsonb(v_reservation);
end;
$$;

create or replace function penta_runtime.release_units_v1(
  p_reservation_key text,
  p_reason text,
  p_evidence_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare r penta_runtime.cost_reservations_v1%rowtype;
begin
  if p_evidence_sha256 is null or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'evidence_sha256_invalid'; end if;
  select * into r from penta_runtime.cost_reservations_v1
  where reservation_key=p_reservation_key for update;
  if not found then raise exception 'reservation_not_found'; end if;
  if r.state in ('released','accounted') then return to_jsonb(r); end if;

  update penta_runtime.cost_unit_budgets_v1
  set reserved_units=reserved_units-r.estimated_units,updated_at=clock_timestamp()
  where unit_budget_id=r.unit_budget_id and reserved_units >= r.estimated_units;
  if not found then raise exception 'unit_budget_release_invariant_failed'; end if;

  update penta_runtime.cost_reservations_v1
  set state='released',actual_cost_minor=0,accounted_units=0,reconciled_at=clock_timestamp()
  where reservation_id=r.reservation_id returning * into r;
  update penta_runtime.flow_jobs_v1
  set reserved_units=0,reserved_cost_minor=0,updated_at=clock_timestamp()
  where job_id=r.job_id;
  insert into penta_runtime.cost_ledger_entries_v1(
    entry_key,campaign_id,job_id,reservation_id,entry_kind,amount_units,
    cost_minor,cost_currency,evidence_sha256,metadata
  ) values (
    p_reservation_key||':release',r.campaign_id,r.job_id,r.reservation_id,
    'release',r.estimated_units,0,'USD',p_evidence_sha256,
    jsonb_build_object('reason',left(coalesce(p_reason,'released'),500),'non_accounting',true)
  ) on conflict (entry_key) do nothing;
  return to_jsonb(r);
end;
$$;

create or replace function penta_runtime.account_units_v1(
  p_reservation_key text,
  p_accounted_units bigint,
  p_evidence_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  r penta_runtime.cost_reservations_v1%rowtype;
  rb penta_runtime.cost_rate_books_v1%rowtype;
begin
  if p_accounted_units is null or p_accounted_units < 0 then raise exception 'accounted_units_negative'; end if;
  if p_evidence_sha256 is null or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'evidence_sha256_invalid'; end if;
  select * into r from penta_runtime.cost_reservations_v1
  where reservation_key=p_reservation_key for update;
  if not found then raise exception 'reservation_not_found'; end if;
  if r.state='accounted' then
    if r.accounted_units is distinct from p_accounted_units then raise exception 'account_idempotency_conflict'; end if;
    return to_jsonb(r);
  end if;
  if r.state <> 'reserved' or p_accounted_units > r.estimated_units then
    raise exception 'accounting_exceeds_valid_reservation';
  end if;
  select * into rb from penta_runtime.cost_rate_books_v1 where rate_key=r.rate_key;

  update penta_runtime.cost_unit_budgets_v1
  set reserved_units=reserved_units-r.estimated_units,
      accounted_units=accounted_units+p_accounted_units,
      updated_at=clock_timestamp()
  where unit_budget_id=r.unit_budget_id and reserved_units >= r.estimated_units
    and accounted_units+p_accounted_units <= ceiling_units;
  if not found then raise exception 'unit_budget_account_invariant_failed'; end if;

  update penta_runtime.cost_reservations_v1
  set state='accounted',accounted_units=p_accounted_units,actual_cost_minor=0,
      reconciled_at=clock_timestamp()
  where reservation_id=r.reservation_id returning * into r;
  update penta_runtime.flow_jobs_v1
  set reserved_units=0,accounted_units=p_accounted_units,reserved_cost_minor=0,
      updated_at=clock_timestamp()
  where job_id=r.job_id;

  insert into penta_runtime.cost_usage_events_v1(
    event_key,campaign_id,job_id,reservation_id,rate_key,quantity,amount_units,
    cost_minor,cost_currency,rate_source_sha256,evidence_sha256,metadata
  ) values (
    p_reservation_key||':usage',r.campaign_id,r.job_id,r.reservation_id,r.rate_key,
    r.quantity,p_accounted_units,0,'USD',rb.source_sha256,p_evidence_sha256,
    jsonb_build_object('penta_member','PentaMeter','cash_or_provider_cost',false)
  ) on conflict (event_key) do nothing;
  insert into penta_runtime.cost_ledger_entries_v1(
    entry_key,campaign_id,job_id,reservation_id,entry_kind,amount_units,
    cost_minor,cost_currency,evidence_sha256,metadata
  ) values (
    p_reservation_key||':account',r.campaign_id,r.job_id,r.reservation_id,
    'account',p_accounted_units,0,'USD',p_evidence_sha256,
    jsonb_build_object('penta_member','PentaCostLedger','non_accounting',true)
  ) on conflict (entry_key) do nothing;
  return to_jsonb(r);
end;
$$;

-- ---------------------------------------------------------------------------
-- PentaLoad and PentaBalancer.  Base routes remain enabled=false; an immutable
-- activation receipt must enumerate the exact route before effective use.
-- ---------------------------------------------------------------------------

create or replace function penta_runtime.select_route_v1(
  p_campaign_id text,
  p_job_key text,
  p_target_repositories text[]
)
returns text
language sql
security definer
set search_path = 'pg_catalog'
as $$
  select r.route_key
  from penta_runtime.factory_routes_v1 r
  join penta_runtime.runtime_activation_receipts_v1 a
    on a.campaign_id=r.campaign_id and r.route_key=any(a.activated_route_keys)
  join penta_runtime.factory_target_adapters_v1 ta
    on ta.target_adapter_key=r.target_adapter_key
  join public.ct_factory_projects p on p.id=r.project_id
  left join lateral (
    select count(*)::bigint as inflight
    from penta_runtime.flow_jobs_v1 j
    where j.campaign_id=r.campaign_id and j.route_key=r.route_key
      and j.state in ('leased','dispatched')
  ) load on true
  where r.campaign_id=p_campaign_id
    and (r.enabled or r.route_key=any(a.activated_route_keys))
    and ta.supported
    and (ta.eligible or ta.target_adapter_key=any(a.certified_target_adapter_keys))
    and r.target_adapter_key='ct.factory.v4'
    and p.production_enabled and p.autonomy_enabled
    and p_target_repositories <@ r.allowed_target_repositories
    and a.state='active' and a.activated_at <= clock_timestamp()
    and clock_timestamp() < a.expires_at
    and load.inflight < r.max_inflight
  order by (load.inflight::numeric/r.max_inflight::numeric) asc,
           md5(p_job_key||':'||r.route_key) asc,
           r.route_key asc
  limit 1
$$;

create or replace function penta_runtime.capture_load_snapshot_v1(
  p_campaign_id text,
  p_route_key text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  r penta_runtime.factory_routes_v1%rowtype;
  v_queued bigint;
  v_leased bigint;
  v_factory bigint;
  v_available integer;
  v_pressure text;
  v_bucket timestamptz := date_trunc('minute',clock_timestamp());
  v_material jsonb;
  v_sha text;
  s penta_runtime.load_snapshots_v1%rowtype;
begin
  select * into r from penta_runtime.factory_routes_v1
  where route_key=p_route_key and campaign_id=p_campaign_id;
  if not found then raise exception 'route_not_found'; end if;
  select
    count(*) filter(where state='queued' and (lease_expires_at is null or lease_expires_at<clock_timestamp())),
    count(*) filter(where state='leased' and lease_expires_at>=clock_timestamp()),
    count(*) filter(where state='dispatched')
  into v_queued,v_leased,v_factory
  from penta_runtime.flow_jobs_v1
  where campaign_id=p_campaign_id and route_key=p_route_key;
  v_available := greatest(0,r.max_inflight-least(r.max_inflight,(v_leased+v_factory)::integer));
  v_pressure := case
    when v_queued=0 and v_leased+v_factory=0 then 'idle'
    when v_available=0 then 'saturated'
    when v_available*4 <= r.max_inflight then 'high'
    else 'normal'
  end;
  v_material := jsonb_build_object(
    'campaign_id',p_campaign_id,'route_key',p_route_key,'sample_bucket',v_bucket,
    'queued',v_queued,'leased',v_leased,'factory_inflight',v_factory,
    'max_inflight',r.max_inflight,'available_slots',v_available,'pressure',v_pressure
  );
  v_sha := encode(extensions.digest(convert_to(v_material::text,'UTF8'),'sha256'),'hex');
  insert into penta_runtime.load_snapshots_v1(
    campaign_id,route_key,sample_bucket,queued_count,leased_count,
    factory_inflight_count,max_inflight,available_slots,pressure_state,material_sha256
  ) values (
    p_campaign_id,p_route_key,v_bucket,v_queued,v_leased,v_factory,
    r.max_inflight,v_available,v_pressure,v_sha
  ) on conflict (campaign_id,route_key,sample_bucket) do nothing
  returning * into s;
  if s.snapshot_id is null then
    select * into s from penta_runtime.load_snapshots_v1
    where campaign_id=p_campaign_id and route_key=p_route_key and sample_bucket=v_bucket;
  end if;
  v_material := jsonb_build_object(
    'campaign_id',s.campaign_id,'route_key',s.route_key,'sample_bucket',s.sample_bucket,
    'queued',s.queued_count,'leased',s.leased_count,
    'factory_inflight',s.factory_inflight_count,'max_inflight',s.max_inflight,
    'available_slots',s.available_slots,'pressure',s.pressure_state
  );
  return jsonb_build_object(
    'snapshot_id',s.snapshot_id,'route_key',s.route_key,
    'material',v_material,'material_sha256',s.material_sha256
  );
end;
$$;

create or replace function penta_runtime.admit_candidate_v1(
  p_campaign_id text,
  p_job_key text,
  p_job_kind text,
  p_severity text,
  p_source_type text,
  p_source_ref text,
  p_source_digest_sha256 text,
  p_objective text,
  p_target_repositories text[],
  p_owner_agent_id text,
  p_verifier_agent_id text,
  p_priority integer default 100,
  p_quantity bigint default 1,
  p_available_at timestamptz default now(),
  p_deadline_at timestamptz default null,
  p_max_attempts integer default 5,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  b penta_runtime.d3_campaign_bindings_v1%rowtype;
  rb penta_runtime.cost_rate_books_v1%rowtype;
  j penta_runtime.flow_jobs_v1%rowtype;
  v_route text;
  v_units_numeric numeric;
  v_units bigint;
  v_deadline timestamptz;
  v_evidence_sha text;
  v_targets text[];
begin
  perform penta_runtime.assert_runtime_active_v1(p_campaign_id,'admit_factory_candidates');
  select * into b from penta_runtime.d3_campaign_bindings_v1 where campaign_id=p_campaign_id;
  if p_job_key is null or length(btrim(p_job_key)) not between 1 and 300 then raise exception 'job_key_invalid'; end if;
  if not coalesce(p_source_type=any(b.allowed_source_types),false) then raise exception 'source_type_not_authorized'; end if;
  if p_source_digest_sha256 is null or p_source_digest_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'source_digest_sha256_invalid'; end if;
  if p_priority is null or p_priority not between 0 and 1000 then raise exception 'priority_out_of_range'; end if;
  if p_max_attempts is null or p_max_attempts not between 1 and 100 then raise exception 'max_attempts_out_of_range'; end if;
  if p_quantity is null or p_quantity <= 0 then raise exception 'quantity_must_be_positive'; end if;
  if jsonb_typeof(coalesce(p_metadata,'{}'::jsonb))<>'object' then raise exception 'metadata_must_be_object'; end if;
  if p_target_repositories is null or cardinality(p_target_repositories)=0
     or exists (select 1 from unnest(p_target_repositories) x where x is null or length(btrim(x))=0)
  then raise exception 'target_repositories_required'; end if;
  select array_agg(x order by x) into v_targets
  from (select distinct x from unnest(p_target_repositories) x) normalized;
  if not coalesce(v_targets <@ array(select jsonb_array_elements_text(b.repository_snapshot)),false) then
    raise exception 'target_repository_outside_immutable_campaign_snapshot';
  end if;
  if p_owner_agent_id is not distinct from p_verifier_agent_id then raise exception 'independent_verifier_required'; end if;
  if not exists (
    select 1 from penta_runtime.agent_registry_v1 a
    where a.agent_id=p_owner_agent_id and a.status='active' and not a.self_approval
  ) then raise exception 'owner_agent_not_eligible'; end if;
  if not exists (
    select 1 from penta_runtime.agent_registry_v1 a
    where a.agent_id=p_verifier_agent_id and a.status='active' and not a.self_approval
  ) then raise exception 'verifier_agent_not_eligible'; end if;

  select * into rb from penta_runtime.cost_rate_books_v1
  where campaign_id=p_campaign_id and operation_key='factory_build'
    and effective_at<=clock_timestamp() and clock_timestamp()<expires_at
  order by effective_at desc limit 1;
  if not found then raise exception 'factory_build_rate_not_found'; end if;
  if rb.cost_minor is distinct from 0 or rb.cost_currency is distinct from 'USD' then
    raise exception 'cash_or_provider_cost_not_authorized';
  end if;
  v_units_numeric := rb.rate_units::numeric*p_quantity::numeric;
  if v_units_numeric>9223372036854775807::numeric then raise exception 'internal_unit_overflow'; end if;
  v_units := v_units_numeric::bigint;
  if v_units>b.max_internal_units then raise exception 'candidate_internal_unit_ceiling_exceeded'; end if;

  v_deadline := least(coalesce(p_deadline_at,b.expires_at),b.expires_at);
  if v_deadline<=clock_timestamp() then raise exception 'candidate_deadline_expired'; end if;

  -- Resolve an existing idempotency key before consulting the load-sensitive
  -- balancer.  A retry therefore preserves its original deterministic route.
  select * into j from penta_runtime.flow_jobs_v1 where job_key=p_job_key for update;
  if not found then
    v_route := penta_runtime.select_route_v1(p_campaign_id,p_job_key,v_targets);
    if v_route is null then raise exception 'no_currently_eligible_factory_route'; end if;
    insert into penta_runtime.flow_jobs_v1(
      job_key,campaign_id,route_key,job_kind,severity,state,source_type,source_ref,
      source_digest_sha256,objective,target_repositories,owner_agent_id,verifier_agent_id,
      priority,available_at,deadline_at,max_attempts,estimated_units,
      estimated_cost_minor,reserved_cost_minor,cost_currency,metadata
    ) values (
      p_job_key,p_campaign_id,v_route,p_job_kind,p_severity,'queued',p_source_type,p_source_ref,
      p_source_digest_sha256,p_objective,v_targets,p_owner_agent_id,p_verifier_agent_id,
      p_priority,greatest(coalesce(p_available_at,clock_timestamp()),clock_timestamp()),
      v_deadline,p_max_attempts,v_units,0,0,'USD',jsonb_build_object(
        'pack_id','crownthrive.penta.runtime-flow-control.v1',
        'implementation_only',true,'certification_effect',false,
        'provider_write_authority',false,'request_metadata',coalesce(p_metadata,'{}'::jsonb)
      )
    ) on conflict (job_key) do nothing returning * into j;
    if j.job_id is null then
      select * into j from penta_runtime.flow_jobs_v1 where job_key=p_job_key for update;
    end if;
  end if;

  if j.job_id is null
     or j.campaign_id is distinct from p_campaign_id
     or j.job_kind is distinct from p_job_kind
     or j.severity is distinct from p_severity
     or j.source_type is distinct from p_source_type
     or j.source_ref is distinct from p_source_ref
     or j.source_digest_sha256 is distinct from p_source_digest_sha256
     or j.objective is distinct from p_objective
     or j.target_repositories is distinct from v_targets
     or j.owner_agent_id is distinct from p_owner_agent_id
     or j.verifier_agent_id is distinct from p_verifier_agent_id
     or j.priority is distinct from p_priority
     or j.deadline_at is distinct from v_deadline
     or j.max_attempts is distinct from p_max_attempts
     or j.estimated_units is distinct from v_units
     or j.estimated_cost_minor is distinct from 0
     or j.metadata->'request_metadata' is distinct from coalesce(p_metadata,'{}'::jsonb)
  then raise exception 'candidate_idempotency_conflict'; end if;

  v_evidence_sha := encode(extensions.digest(convert_to(
    jsonb_build_object(
      'campaign_id',p_campaign_id,'job_key',p_job_key,'source_digest',p_source_digest_sha256,
      'route_key',j.route_key,'rate_key',rb.rate_key,'quantity',p_quantity,'estimated_units',v_units
    )::text,'UTF8'),'sha256'),'hex');

  perform penta_runtime.reserve_units_v1(
    p_campaign_id,j.job_id,'flow:'||p_job_key||':units',rb.rate_key,p_quantity,v_evidence_sha
  );
  select * into j from penta_runtime.flow_jobs_v1 where job_id=j.job_id;
  return to_jsonb(j);
end;
$$;

create or replace function penta_runtime.claim_candidates_v1(
  p_campaign_id text,
  p_worker_id text,
  p_batch_size integer default 4,
  p_lease_seconds integer default 300
)
returns setof penta_runtime.flow_jobs_v1
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  b penta_runtime.d3_campaign_bindings_v1%rowtype;
  a penta_runtime.runtime_activation_receipts_v1%rowtype;
  j penta_runtime.flow_jobs_v1%rowtype;
  v_limit integer;
  v_active bigint;
  v_until timestamptz;
  i integer;
begin
  -- Serialize capacity accounting per campaign. SKIP LOCKED distributes rows;
  -- this transaction lock makes the aggregate campaign/route caps exact.
  perform pg_advisory_xact_lock(
    hashtextextended('penta_runtime.claim:'||p_campaign_id,0)
  );
  perform penta_runtime.assert_runtime_active_v1(p_campaign_id,'execute_bounded_candidates');
  if p_worker_id is null or length(btrim(p_worker_id)) not between 1 and 200 then raise exception 'worker_id_invalid'; end if;
  if not exists (
    select 1 from penta_runtime.agent_registry_v1 ar
    where ar.agent_id=p_worker_id and ar.status='active' and not ar.self_approval
      and ar.capabilities @> array['penta.flow.claim.v1']::text[]
  ) then raise exception 'worker_agent_not_registered_for_flow_claim'; end if;
  if p_lease_seconds is null or p_lease_seconds not between 30 and 900 then
    raise exception 'lease_seconds_out_of_range';
  end if;
  if p_batch_size is null or p_batch_size < 1 then raise exception 'batch_size_out_of_range'; end if;
  select * into b from penta_runtime.d3_campaign_bindings_v1 where campaign_id=p_campaign_id;
  select * into a from penta_runtime.runtime_activation_receipts_v1 where campaign_id=p_campaign_id;
  v_limit:=least(p_batch_size,b.max_claim_batch);

  for i in 1..v_limit loop
    select count(*) into v_active from penta_runtime.flow_jobs_v1
    where campaign_id=p_campaign_id and state in ('leased','dispatched');
    if v_active>=b.max_concurrency then exit; end if;

    select q.* into j
    from penta_runtime.flow_jobs_v1 q
    join penta_runtime.factory_routes_v1 r on r.route_key=q.route_key
    join penta_runtime.factory_target_adapters_v1 ta on ta.target_adapter_key=r.target_adapter_key
    join penta_runtime.cost_reservations_v1 cr on cr.job_id=q.job_id and cr.state='reserved'
    where q.campaign_id=p_campaign_id and q.state='queued'
      and q.available_at<=clock_timestamp() and q.deadline_at>clock_timestamp()
      and q.attempt_count<q.max_attempts
      and q.route_key=any(a.activated_route_keys)
      and ta.target_adapter_key='ct.factory.v4' and ta.supported
      and ta.target_adapter_key=any(a.certified_target_adapter_keys)
      and (
        select count(*) from penta_runtime.flow_jobs_v1 rj
        where rj.campaign_id=q.campaign_id and rj.route_key=q.route_key
          and rj.state in ('leased','dispatched')
      ) < r.max_inflight
    order by q.priority desc,q.available_at,q.created_at,q.job_id
    limit 1
    for update of q skip locked;
    if not found then exit; end if;

    v_until:=least(
      clock_timestamp()+make_interval(secs=>p_lease_seconds),
      b.expires_at,a.expires_at,j.deadline_at
    );
    update penta_runtime.flow_jobs_v1
    set state='leased',lease_owner=p_worker_id,lease_expires_at=v_until,
        fencing_token=fencing_token+1,attempt_count=attempt_count+1,
        last_error=null,updated_at=clock_timestamp()
    where job_id=j.job_id returning * into j;
    return next j;
  end loop;
  return;
end;
$$;

create or replace function penta_runtime.enqueue_dispatch_outbox_v1(
  p_job_id uuid,
  p_worker_id text,
  p_fencing_token bigint
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  j penta_runtime.flow_jobs_v1%rowtype;
  r penta_runtime.factory_routes_v1%rowtype;
  o penta_runtime.dispatch_outbox_v1%rowtype;
  v_payload jsonb;
  v_sha text;
  v_receipt_id uuid;
begin
  select * into j from penta_runtime.flow_jobs_v1 where job_id=p_job_id for update;
  if not found then raise exception 'flow_job_not_found'; end if;
  perform penta_runtime.assert_runtime_active_v1(j.campaign_id,'factory_candidate_dispatch');
  if j.state is distinct from 'leased'
     or j.lease_owner is distinct from p_worker_id
     or j.fencing_token is distinct from p_fencing_token
     or j.lease_expires_at is null or j.lease_expires_at<=clock_timestamp()
  then raise exception 'invalid_or_stale_flow_job_lease'; end if;
  select * into r from penta_runtime.factory_routes_v1 where route_key=j.route_key;
  if r.target_adapter_key<>'ct.factory.v4' then raise exception 'unsupported_target_adapter_is_hold_only'; end if;
  if not exists (
    select 1 from penta_runtime.runtime_activation_receipts_v1 a
    where a.campaign_id=j.campaign_id and j.route_key=any(a.activated_route_keys)
      and r.target_adapter_key=any(a.certified_target_adapter_keys)
  ) then raise exception 'route_not_in_exact_activation_receipt'; end if;

  v_payload:=jsonb_build_object(
    'campaign_id',j.campaign_id,'job_id',j.job_id,'job_key',j.job_key,
    'route_key',j.route_key,'target_adapter_key',r.target_adapter_key,
    'project_id',r.project_id,'source_type',j.source_type,'source_ref',j.source_ref,
    'source_digest_sha256',j.source_digest_sha256,'objective',j.objective,
    'target_repositories',to_jsonb(j.target_repositories),'job_kind',j.job_kind,
    'severity',j.severity,'deadline_at',j.deadline_at,'fencing_token',j.fencing_token,
    'estimated_units',j.estimated_units,'estimated_cost_minor',0,
    'provider_write_authority',false,'independent_certification_required',true
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into penta_runtime.dispatch_outbox_v1(
    outbox_key,job_id,campaign_id,route_key,target_adapter_key,state,
    fencing_token,payload,payload_sha256,available_at
  ) values (
    'flow:'||j.job_key||':dispatch',j.job_id,j.campaign_id,j.route_key,r.target_adapter_key,
    'hold',j.fencing_token,v_payload,v_sha,clock_timestamp()
  ) on conflict (outbox_key) do nothing returning * into o;
  if o.outbox_id is null then
    select * into o from penta_runtime.dispatch_outbox_v1 where outbox_key='flow:'||j.job_key||':dispatch';
    if o.job_id is distinct from j.job_id
       or o.fencing_token is distinct from j.fencing_token
       or o.payload_sha256 is distinct from v_sha
       or o.state is distinct from 'hold' then
      raise exception 'dispatch_outbox_idempotency_conflict';
    end if;
  end if;
  update penta_runtime.flow_jobs_v1
  set state='hold',lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp(),
      last_error='target_effect_adapter_not_certified',
      result=result||jsonb_build_object(
        'dispatch_outbox_id',o.outbox_id,'dispatch_payload_sha256',v_sha,
        'outbox_state','hold','external_effect',false
      )
  where job_id=j.job_id;
  insert into penta_runtime.dispatch_receipts_v1(
    receipt_key,outbox_id,job_id,disposition,target_ref,payload_sha256,evidence
  ) values (
    o.outbox_key||':hold',o.outbox_id,j.job_id,'hold',null,o.payload_sha256,
    jsonb_build_object(
      'reason','target_effect_adapter_not_certified',
      'target_adapter_key',o.target_adapter_key,'external_effect',false,
      'certification_effect',false
    )
  ) on conflict (receipt_key) do nothing returning receipt_id into v_receipt_id;
  perform penta_runtime.release_units_v1(
    'flow:'||j.job_key||':units','target_effect_adapter_not_certified',v_sha
  );
  return to_jsonb(o)||jsonb_build_object('receipt_id',v_receipt_id,'external_effect',false);
end;
$$;

create or replace function penta_runtime.release_flow_lease_v1(
  p_job_id uuid,
  p_worker_id text,
  p_fencing_token bigint,
  p_error text,
  p_retry_delay_seconds integer default 60
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare j penta_runtime.flow_jobs_v1%rowtype; v_state text;
begin
  select * into j from penta_runtime.flow_jobs_v1 where job_id=p_job_id for update;
  if not found then raise exception 'flow_job_not_found'; end if;
  if p_retry_delay_seconds is null or p_retry_delay_seconds not between 0 and 3600 then
    raise exception 'retry_delay_seconds_out_of_range';
  end if;
  if j.state is distinct from 'leased'
     or j.lease_owner is distinct from p_worker_id
     or j.fencing_token is distinct from p_fencing_token then
    raise exception 'invalid_or_stale_flow_job_lease';
  end if;
  v_state:=case
    when clock_timestamp()>=j.deadline_at then 'expired'
    when j.attempt_count>=j.max_attempts then 'hold'
    else 'queued'
  end;
  update penta_runtime.flow_jobs_v1
  set state=v_state,lease_owner=null,lease_expires_at=null,
      available_at=case when v_state='queued' then least(
        clock_timestamp()+make_interval(secs=>p_retry_delay_seconds),deadline_at
      ) else available_at end,
      last_error=left(coalesce(p_error,'lease_released'),1000),updated_at=clock_timestamp()
  where job_id=j.job_id returning * into j;
  if v_state in ('hold','expired') then
    perform penta_runtime.release_units_v1(
      'flow:'||j.job_key||':units','terminal_'||v_state,
      encode(extensions.digest(convert_to((j.job_id::text||':'||v_state||':'||j.fencing_token::text),'UTF8'),'sha256'),'hex')
    );
  end if;
  return to_jsonb(j);
end;
$$;

create or replace function penta_runtime.reap_flow_jobs_v1(p_campaign_id text)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare j penta_runtime.flow_jobs_v1%rowtype; v_requeued integer:=0; v_terminal integer:=0; v_state text; v_sha text;
begin
  for j in
    select * from penta_runtime.flow_jobs_v1
    where campaign_id=p_campaign_id and (
      (state='leased' and lease_expires_at<clock_timestamp())
      or (state in ('queued','leased') and deadline_at<=clock_timestamp())
      or (state in ('queued','leased') and exists(
        select 1 from penta_runtime.d3_campaign_bindings_v1 b
        where b.campaign_id=p_campaign_id and b.expires_at<=clock_timestamp()
      ))
    ) order by job_id for update skip locked
  loop
    v_state:=case
                  when j.deadline_at<=clock_timestamp() or exists (
                    select 1 from penta_runtime.d3_campaign_bindings_v1 b
                    where b.campaign_id=p_campaign_id and b.expires_at<=clock_timestamp()
                  ) then 'expired'
                  when j.attempt_count>=j.max_attempts then 'hold' else 'queued' end;
    update penta_runtime.flow_jobs_v1
    set state=v_state,lease_owner=null,lease_expires_at=null,
        available_at=case when v_state='queued' then clock_timestamp()+interval '60 seconds' else available_at end,
        last_error=case when v_state='queued' then 'lease_expired_retry' else 'flow_job_terminal' end,
        updated_at=clock_timestamp()
    where job_id=j.job_id;
    if v_state='queued' then v_requeued:=v_requeued+1; else
      v_terminal:=v_terminal+1;
      v_sha:=encode(extensions.digest(convert_to((j.job_id::text||':'||v_state||':reap'),'UTF8'),'sha256'),'hex');
      perform penta_runtime.release_units_v1('flow:'||j.job_key||':units','reaper_'||v_state,v_sha);
    end if;
  end loop;
  return jsonb_build_object('campaign_id',p_campaign_id,'requeued',v_requeued,'terminal',v_terminal);
end;
$$;

create or replace function penta_runtime.record_cost_forecast_v1(
  p_campaign_id text,
  p_forecast_key text,
  p_horizon_minutes integer,
  p_evidence_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  v_count bigint;
  v_pending bigint;
  v_mean numeric;
  v_forecast_numeric numeric;
  v_forecast bigint;
  v_row penta_runtime.cost_forecasts_v1%rowtype;
begin
  if p_horizon_minutes is null or p_horizon_minutes not between 1 and 10080 then raise exception 'forecast_horizon_out_of_range'; end if;
  if p_evidence_sha256 is null or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'evidence_sha256_invalid'; end if;
  select count(*),coalesce(avg(amount_units),0) into v_count,v_mean
  from penta_runtime.cost_usage_events_v1
  where campaign_id=p_campaign_id
    and observed_at>=clock_timestamp()-make_interval(mins=>p_horizon_minutes);
  select count(*) into v_pending from penta_runtime.flow_jobs_v1
  where campaign_id=p_campaign_id and state in ('queued','leased','dispatched');
  if v_count=0 then
    select coalesce(max(rate_units),0) into v_mean
    from penta_runtime.cost_rate_books_v1 where campaign_id=p_campaign_id;
  end if;
  v_forecast_numeric:=ceil(v_mean)*v_pending;
  if v_forecast_numeric>9223372036854775807::numeric then raise exception 'forecast_unit_overflow'; end if;
  v_forecast:=v_forecast_numeric::bigint;
  insert into penta_runtime.cost_forecasts_v1(
    forecast_key,campaign_id,horizon_minutes,observed_event_count,forecast_units,
    forecast_cost_minor,cost_currency,assumptions,advisory_only,evidence_sha256
  ) values (
    p_forecast_key,p_campaign_id,p_horizon_minutes,v_count,v_forecast,0,'USD',
    jsonb_build_object(
      'method','ceiling_mean_times_current_pending',
      'pending_count',v_pending,'mean_units',v_mean,
      'cash_or_provider_cost_minor',0,'reservation_effect',false
    ),true,p_evidence_sha256
  ) on conflict (forecast_key) do nothing returning * into v_row;
  if v_row.forecast_id is null then
    select * into v_row from penta_runtime.cost_forecasts_v1 where forecast_key=p_forecast_key;
    if v_row.campaign_id is distinct from p_campaign_id
       or v_row.horizon_minutes is distinct from p_horizon_minutes
       or v_row.evidence_sha256 is distinct from p_evidence_sha256
    then raise exception 'forecast_idempotency_conflict'; end if;
  end if;
  return to_jsonb(v_row);
end;
$$;

create or replace function penta_runtime.capture_consolidated_report_v1(p_campaign_id text)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  v_campaign jsonb;
  v_jobs jsonb;
  v_outbox jsonb;
  v_targets jsonb;
  v_routes jsonb;
  v_provider jsonb;
  v_units jsonb;
  v_components jsonb;
  v_raw jsonb;
  v_exceptions jsonb:='[]'::jsonb;
  v_summary jsonb;
  v_scope jsonb;
  v_material jsonb;
  v_sha text;
  v_report_key text;
  v_id uuid;
  v_inserted boolean;
  v_github_enabled boolean;
  v_github_runnable bigint;
  v_route_violations bigint;
  v_provider_lane text;
begin
  v_campaign:=penta_runtime.campaign_status_v1(p_campaign_id);
  select coalesce(jsonb_object_agg(state,n),'{}'::jsonb) into v_jobs
  from (select state,count(*) n from penta_runtime.flow_jobs_v1 where campaign_id=p_campaign_id group by state) s;
  select coalesce(jsonb_object_agg(state,n),'{}'::jsonb) into v_outbox
  from (select state,count(*) n from penta_runtime.dispatch_outbox_v1 where campaign_id=p_campaign_id group by state) s;
  select coalesce(jsonb_object_agg(target_adapter_key,jsonb_build_object(
    'supported',supported,'eligible',eligible,'state',state
  )),'{}'::jsonb) into v_targets
  from penta_runtime.factory_target_adapters_v1;
  select coalesce(jsonb_object_agg(route_key,jsonb_build_object(
    'enabled',enabled,'provider_claim_enabled',provider_claim_enabled,
    'target_adapter_key',target_adapter_key,'release_channel',release_channel
  )),'{}'::jsonb) into v_routes
  from penta_runtime.factory_routes_v1 where campaign_id=p_campaign_id;
  select count(*) into v_route_violations
  from penta_runtime.factory_routes_v1
  where campaign_id=p_campaign_id and (enabled or provider_claim_enabled);
  select coalesce(jsonb_object_agg(state,n),'{}'::jsonb) into v_provider
  from (select state,count(*) n from public.ct_factory_provider_jobs
        where adapter_key='ct.adapter.github.actions.v1' group by state) s;
  select enabled into v_github_enabled from public.ct_factory_provider_adapters
  where adapter_key='ct.adapter.github.actions.v1';
  select count(*) into v_github_runnable from public.ct_factory_provider_jobs
  where adapter_key='ct.adapter.github.actions.v1' and state in ('queued','claimed');
  select coalesce(jsonb_build_object(
    'ceiling_units',ceiling_units,'reserved_units',reserved_units,
    'accounted_units',accounted_units,'cash_or_provider_cost_minor',cash_or_provider_cost_minor,
    'state',state
  ),'{}'::jsonb) into v_units
  from penta_runtime.cost_unit_budgets_v1 where campaign_id=p_campaign_id;
  select coalesce(jsonb_object_agg(component_key,jsonb_build_object(
    'enabled',enabled,'implementation_state',implementation_state,'contract',stable_contract_id
  )),'{}'::jsonb) into v_components
  from penta_runtime.component_registry_v1
  where component_key in ('penta.load','penta.balancer','penta.costs');

  if v_github_enabled is distinct from false then
    v_exceptions:=v_exceptions||jsonb_build_array(jsonb_build_object(
      'group','provider_containment',
      'code',case when v_github_enabled is null then 'github_adapter_missing' else 'github_adapter_enabled' end
    ));
  end if;
  if v_github_runnable>0 then
    v_exceptions:=v_exceptions||jsonb_build_array(jsonb_build_object('group','provider_containment','code','github_jobs_runnable','count',v_github_runnable));
  end if;
  if not coalesce((v_campaign->>'runtime_active')::boolean,false) then
    v_exceptions:=v_exceptions||jsonb_build_array(jsonb_build_object('group','activation','code','runtime_not_activated'));
  end if;
  if coalesce((v_jobs->>'hold')::bigint,0)>0 then
    v_exceptions:=v_exceptions||jsonb_build_array(jsonb_build_object('group','flow_jobs','code','held_jobs','count',(v_jobs->>'hold')::bigint));
  end if;
  if v_route_violations>0 then
    v_exceptions:=v_exceptions||jsonb_build_array(jsonb_build_object(
      'group','factory_routes','code','immutable_route_flag_violation','count',v_route_violations
    ));
  end if;

  v_provider_lane:=case
    when v_github_enabled is false and v_github_runnable=0 and v_route_violations=0
      then 'HOLD'
    else 'CONTAINMENT_VIOLATION'
  end;

  v_raw:=jsonb_build_object(
    'flow_jobs_by_state',v_jobs,'dispatch_outbox_by_state',v_outbox,
    'github_provider_jobs_by_state',v_provider,
    'github_provider_adapter_present',v_github_enabled is not null,
    'github_provider_adapter_enabled',v_github_enabled,
    'github_provider_runnable',v_github_runnable,
    'target_adapters',v_targets,'factory_routes',v_routes,
    'route_flag_violations',v_route_violations,
    'internal_unit_budget',v_units,'components',v_components
  );
  v_summary:=jsonb_build_object(
    'campaign',v_campaign,'exception_group_count',jsonb_array_length(v_exceptions),
    'provider_lane',v_provider_lane,'cash_or_provider_cost_minor',0,
    'certification_effect',false,'production_promotion_effect',false
  );
  v_scope:=jsonb_build_object(
    'source_tables',jsonb_build_array(
      'penta_runtime.flow_jobs_v1','penta_runtime.dispatch_outbox_v1',
      'penta_runtime.factory_target_adapters_v1','penta_runtime.factory_routes_v1',
      'penta_runtime.cost_unit_budgets_v1',
      'public.ct_factory_provider_jobs','public.ct_factory_provider_adapters'
    ),
    'raw_records_preserved_in_source_tables',true,
    'report_contains_exact_counts_not_destructive_consolidation',true
  );
  v_material:=jsonb_build_object('summary',v_summary,'raw_counts',v_raw,'exceptions',v_exceptions,'scope',v_scope);
  v_sha:=encode(extensions.digest(convert_to(v_material::text,'UTF8'),'sha256'),'hex');
  v_report_key:=p_campaign_id||':'||v_sha;
  insert into penta_runtime.consolidated_reports_v1(
    report_key,campaign_id,material_sha256,summary,raw_counts,exception_groups,evidence_scope
  ) values (v_report_key,p_campaign_id,v_sha,v_summary,v_raw,v_exceptions,v_scope)
  on conflict (campaign_id,material_sha256) do nothing returning report_id into v_id;
  v_inserted:=found;
  if not v_inserted then
    select report_id into v_id from penta_runtime.consolidated_reports_v1
    where campaign_id=p_campaign_id and material_sha256=v_sha;
  end if;
  return jsonb_build_object(
    'report_id',v_id,'campaign_id',p_campaign_id,'material_sha256',v_sha,
    'inserted',v_inserted,'deduplicated',not v_inserted,
    'summary',v_summary,'exception_groups',v_exceptions
  );
end;
$$;

create or replace function penta_runtime.flow_tick_v1(
  p_campaign_id text,
  p_worker_id text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog'
as $$
declare
  v_status jsonb;
  v_reap jsonb;
  v_report jsonb;
  v_dispatched jsonb:='[]'::jsonb;
  j penta_runtime.flow_jobs_v1%rowtype;
  o jsonb;
  v_err_sha text;
begin
  v_reap:=penta_runtime.reap_flow_jobs_v1(p_campaign_id);
  v_status:=penta_runtime.campaign_status_v1(p_campaign_id);
  if coalesce((v_status->>'runtime_active')::boolean,false) then
    perform penta_runtime.capture_load_snapshot_v1(p_campaign_id,r.route_key)
    from penta_runtime.factory_routes_v1 r
    join penta_runtime.runtime_activation_receipts_v1 a on a.campaign_id=r.campaign_id
    where r.campaign_id=p_campaign_id and r.route_key=any(a.activated_route_keys);
    for j in select * from penta_runtime.claim_candidates_v1(p_campaign_id,p_worker_id,4,300)
    loop
      begin
        o:=penta_runtime.enqueue_dispatch_outbox_v1(j.job_id,p_worker_id,j.fencing_token);
        v_dispatched:=v_dispatched||jsonb_build_array(o);
      exception when others then
        v_err_sha:=encode(extensions.digest(convert_to(
          (j.job_id::text||':'||j.fencing_token::text||':'||sqlstate||':'||sqlerrm),'UTF8'
        ),'sha256'),'hex');
        perform penta_runtime.release_flow_lease_v1(j.job_id,p_worker_id,j.fencing_token,
          left(sqlstate||':'||sqlerrm,1000),60);
        v_dispatched:=v_dispatched||jsonb_build_array(jsonb_build_object(
          'job_id',j.job_id,'dispatched',false,'error_evidence_sha256',v_err_sha
        ));
      end;
    end loop;
  end if;
  v_report:=penta_runtime.capture_consolidated_report_v1(p_campaign_id);
  return jsonb_build_object(
    'campaign_status',v_status,'reap',v_reap,
    'dispatches',v_dispatched,'report',v_report,
    'provider_lane',v_report#>>'{summary,provider_lane}'
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- Narrow RPC surface.  New mutable tables expose SELECT only to service_role;
-- transitions are owned by these exact SECURITY DEFINER functions.
-- ---------------------------------------------------------------------------

revoke all on function penta_runtime.campaign_status_v1(text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.reject_row_mutation_v1() from public, anon, authenticated, service_role;
revoke all on function penta_runtime.protect_flow_founder_directive_v1() from public, anon, authenticated, service_role;
revoke all on function penta_runtime.assert_runtime_active_v1(text,text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.hold_campaign_v1(text,text,text,text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.reserve_units_v1(text,uuid,text,text,bigint,text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.release_units_v1(text,text,text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.account_units_v1(text,bigint,text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.select_route_v1(text,text,text[]) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.capture_load_snapshot_v1(text,text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.admit_candidate_v1(text,text,text,text,text,text,text,text,text[],text,text,integer,bigint,timestamptz,timestamptz,integer,jsonb) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.claim_candidates_v1(text,text,integer,integer) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.enqueue_dispatch_outbox_v1(uuid,text,bigint) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.release_flow_lease_v1(uuid,text,bigint,text,integer) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.reap_flow_jobs_v1(text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.record_cost_forecast_v1(text,text,integer,text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.capture_consolidated_report_v1(text) from public, anon, authenticated, service_role;
revoke all on function penta_runtime.flow_tick_v1(text,text) from public, anon, authenticated, service_role;

grant execute on function penta_runtime.campaign_status_v1(text) to service_role;
grant execute on function penta_runtime.hold_campaign_v1(text,text,text,text) to service_role;
grant execute on function penta_runtime.capture_load_snapshot_v1(text,text) to service_role;
grant execute on function penta_runtime.admit_candidate_v1(text,text,text,text,text,text,text,text,text[],text,text,integer,bigint,timestamptz,timestamptz,integer,jsonb) to service_role;
grant execute on function penta_runtime.claim_candidates_v1(text,text,integer,integer) to service_role;
grant execute on function penta_runtime.enqueue_dispatch_outbox_v1(uuid,text,bigint) to service_role;
grant execute on function penta_runtime.release_flow_lease_v1(uuid,text,bigint,text,integer) to service_role;
grant execute on function penta_runtime.reap_flow_jobs_v1(text) to service_role;
grant execute on function penta_runtime.record_cost_forecast_v1(text,text,integer,text) to service_role;
grant execute on function penta_runtime.capture_consolidated_report_v1(text) to service_role;
grant execute on function penta_runtime.flow_tick_v1(text,text) to service_role;

comment on table penta_runtime.d3_campaign_bindings_v1 is
  'Immutable nonrenewing fourteen-day Founder D3 release authorization binding; never substitutes independent evidence.';
comment on table penta_runtime.runtime_activation_receipts_v1 is
  'Append-only exact-head activation seam. This implementation migration inserts no activation receipt.';
comment on table penta_runtime.flow_jobs_v1 is
  'Isolated PentaQueue ledger; deliberately separate from generic jobs_v1 and its legacy maintenance dispatcher.';
comment on table penta_runtime.factory_target_adapters_v1 is
  'Versioned target adapter compatibility registry. Every v1 adapter begins HOLD and ineligible.';
comment on table penta_runtime.dispatch_outbox_v1 is
  'Effect-free dispatch intent outbox. Initial v1 only writes HOLD entries and has no target consumer.';
comment on table penta_runtime.cost_unit_budgets_v1 is
  'Internal resource-unit PentaBudget; not price, currency, provider spend, treasury or accounting truth.';
comment on column penta_runtime.d3_campaign_bindings_v1.max_cost_minor is
  'Immutable cash/provider-cost ceiling. It is zero for this campaign.';
comment on function penta_runtime.flow_tick_v1(text,text) is
  'Manual-only v1 tick. No cron is installed; without exact activation it only reaps and reports, and any dispatch intent remains HOLD without external effect.';

-- Intentionally absent: cron.schedule, pg_net, provider enablement, native
-- factory table consumer, certification receipt, production promotion, money
-- movement, rights mutation, credential mutation and raw-secret access.
