-- PentaPR terminal-provider schema bridge v1.
--
-- Production readback of the canonical penta-institutional-pr-terminal-provider Edge Function
-- returned HTTP 409 / CLAIM_REJECTED because its default Supabase RPC route resolves functions
-- in `public`, while the canonical claim/result implementations live in `integration_control`.
-- This compatibility bridge exposes only service-role-only delegating wrappers; business logic,
-- wake-token validation, exact-head enforcement, DAIL append/readback and terminal authority stay
-- inside the canonical integration_control functions.
--
-- No provider/customer write authority is added by these wrappers. They only make the already-
-- authorized internal provider executor able to reach the existing guarded RPCs through the
-- schema contract it currently uses.

create or replace function public.penta_pr_closeout_claim_v1(
  p_action_id uuid,
  p_wake_token text,
  p_worker_id text
)
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','integration_control','public'
as $function$
  select integration_control.penta_pr_closeout_claim_v1(
    p_action_id,
    p_wake_token,
    p_worker_id
  );
$function$;

create or replace function public.penta_pr_closeout_result_v1(
  p_action_id uuid,
  p_success boolean,
  p_http_status integer,
  p_provider_state text,
  p_object_ref text,
  p_request_sha256 text,
  p_response_sha256 text,
  p_readback_pass boolean,
  p_receipt jsonb,
  p_error_code text,
  p_pr_number bigint default null,
  p_base_ref text default null,
  p_head_sha text default null,
  p_source_branch text default null
)
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','integration_control','public'
as $function$
  select integration_control.penta_pr_closeout_result_v1(
    p_action_id,
    p_success,
    p_http_status,
    p_provider_state,
    p_object_ref,
    p_request_sha256,
    p_response_sha256,
    p_readback_pass,
    p_receipt,
    p_error_code,
    p_pr_number,
    p_base_ref,
    p_head_sha,
    p_source_branch
  );
$function$;

revoke all on function public.penta_pr_closeout_claim_v1(uuid,text,text) from public,anon,authenticated;
grant execute on function public.penta_pr_closeout_claim_v1(uuid,text,text) to service_role;
revoke all on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text) from public,anon,authenticated;
grant execute on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text) to service_role;

comment on function public.penta_pr_closeout_claim_v1(uuid,text,text) is
'Service-role-only schema bridge to integration_control.penta_pr_closeout_claim_v1 for the canonical terminal-provider Edge Function. Wake-token and claimability enforcement remain canonical.';
comment on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text) is
'Service-role-only schema bridge to integration_control.penta_pr_closeout_result_v1 for exact provider result/readback settlement. No terminal authority is created here.';
