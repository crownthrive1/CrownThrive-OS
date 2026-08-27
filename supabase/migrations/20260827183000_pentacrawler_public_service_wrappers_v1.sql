-- PentaCrawler™ public service-role RPC boundary v1
-- Keeps the internal crm schema private while exposing only bounded runtime actions.

create or replace function public.penta_crawler_control_plane_v1()
returns jsonb
language sql
security definer
set search_path = pg_catalog, crm
as $$ select crm.outreach_control_plane_v1(); $$;

create or replace function public.penta_crawler_claim_v1(p_limit integer default 5)
returns jsonb
language sql
security definer
set search_path = pg_catalog, crm
as $$ select crm.contact_discovery_claim_v1(p_limit); $$;

create or replace function public.penta_crawler_complete_v1(
  p_queue_id uuid,
  p_observations jsonb default '[]'::jsonb,
  p_error text default null
)
returns jsonb
language sql
security definer
set search_path = pg_catalog, crm
as $$ select crm.contact_discovery_complete_v1(p_queue_id,p_observations,p_error); $$;

create or replace function public.penta_crawler_promote_v1(p_limit integer default 100)
returns jsonb
language sql
security definer
set search_path = pg_catalog, crm
as $$ select crm.promote_verified_prospects_v1(p_limit); $$;

create or replace function public.penta_crawler_commercial_authority_v1(
  p_principal_id text default 'ct.ops.agent.email-attention'
)
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, crm
as $$ select crm.commercial_send_authority_v1(p_principal_id); $$;

create or replace function public.penta_crawler_offer_ready_v1(
  p_offer_ref text default 'locticians.claimmonth50.v1'
)
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, crm
as $$ select crm.outreach_offer_ready_v1(p_offer_ref); $$;

create or replace function public.penta_crawler_scheduler_tick_v1()
returns jsonb
language sql
security definer
set search_path = pg_catalog, crm
as $$ select crm.outreach_scheduler_tick_v1(); $$;

revoke all on function public.penta_crawler_control_plane_v1() from public, anon, authenticated;
revoke all on function public.penta_crawler_claim_v1(integer) from public, anon, authenticated;
revoke all on function public.penta_crawler_complete_v1(uuid,jsonb,text) from public, anon, authenticated;
revoke all on function public.penta_crawler_promote_v1(integer) from public, anon, authenticated;
revoke all on function public.penta_crawler_commercial_authority_v1(text) from public, anon, authenticated;
revoke all on function public.penta_crawler_offer_ready_v1(text) from public, anon, authenticated;
revoke all on function public.penta_crawler_scheduler_tick_v1() from public, anon, authenticated;

grant execute on function public.penta_crawler_control_plane_v1() to service_role;
grant execute on function public.penta_crawler_claim_v1(integer) to service_role;
grant execute on function public.penta_crawler_complete_v1(uuid,jsonb,text) to service_role;
grant execute on function public.penta_crawler_promote_v1(integer) to service_role;
grant execute on function public.penta_crawler_commercial_authority_v1(text) to service_role;
grant execute on function public.penta_crawler_offer_ready_v1(text) to service_role;
grant execute on function public.penta_crawler_scheduler_tick_v1() to service_role;
