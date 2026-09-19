begin;

create or replace function public.penta_pr_closeout_claim_v1(
  p_action_id uuid,
  p_wake_token text,
  p_worker_id text
)
returns jsonb
language sql
security definer
set search_path to 'pg_catalog', 'integration_control'
as $fn$
  select integration_control.penta_pr_closeout_claim_v1(
    p_action_id,
    p_wake_token,
    p_worker_id
  );
$fn$;

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
set search_path to 'pg_catalog', 'integration_control'
as $fn$
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
$fn$;

revoke all on function public.penta_pr_closeout_claim_v1(uuid,text,text)
  from public, anon, authenticated;
revoke all on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text)
  from public, anon, authenticated;

grant execute on function public.penta_pr_closeout_claim_v1(uuid,text,text)
  to service_role;
grant execute on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text)
  to service_role;

comment on function public.penta_pr_closeout_claim_v1(uuid,text,text) is
  'Service-role RPC bridge to the governed PentaPR closeout claim implementation. Preserves wake-token validation, lease semantics and existing authority checks; creates no provider-write or merge authority.';
comment on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text) is
  'Service-role RPC bridge to the governed PentaPR closeout result implementation. Preserves PentaChange authorization, exact provider evidence, DAIL append and lifecycle routing; creates no new authority.';

commit;
