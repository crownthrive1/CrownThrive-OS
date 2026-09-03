-- CrownThrive PentaCensus security + context convergence v1
--
-- Bounded dependency repair for the current OS-readiness lane. The existing
-- context-only handoff repair must remain authoritative while the already-
-- production PentaSecurity identity gains an executable Pentas-v2 route.
-- This migration creates no D3, money, credential, rights, vote/quorum,
-- certification, provider-write, or merge authority.

insert into pentas.nodes_v2 (
  node_id,
  display_name,
  node_class,
  authority_ceiling,
  capabilities,
  topics,
  endpoint_kind,
  endpoint_ref,
  health_state,
  lifecycle_state,
  metadata,
  last_heartbeat_at,
  updated_at
)
select
  'ct.penta.security',
  i.canonical_name,
  'penta',
  'D2',
  array['security.review','security.provider-source-review','security.runtime-review','evidence.attest']::text[],
  array['security','identity','trust','evidence']::text[],
  'internal_sql',
  'penta_security.review_system_v1',
  case when i.activation_state='ACTIVE' and i.runtime_state='RUNTIME_PRESENT' then 'healthy' else 'degraded' end,
  'active',
  jsonb_build_object(
    'role','bounded security review and evidence coordination',
    'identity_key',i.identity_key,
    'source_maturity',i.maturity,
    'production_receipt_id',i.metadata->>'production_receipt_id',
    'independent_certification_id',i.metadata->>'independent_certification_id',
    'source_ref','ct.penta.census-security-context-convergence.v1',
    'authority_created',false,
    'd3_human_reserved',true
  ),
  clock_timestamp(),
  clock_timestamp()
from integration_control.penta_identity_registry_v1 i
where i.identity_key='penta.security'
  and i.current=true
  and i.active=true
  and i.maturity='production'
  and i.activation_state='ACTIVE'
  and i.runtime_state='RUNTIME_PRESENT'
order by i.updated_at desc
limit 1
on conflict (node_id) do update set
  display_name=excluded.display_name,
  node_class=excluded.node_class,
  authority_ceiling=excluded.authority_ceiling,
  capabilities=excluded.capabilities,
  topics=excluded.topics,
  endpoint_kind=excluded.endpoint_kind,
  endpoint_ref=excluded.endpoint_ref,
  health_state=excluded.health_state,
  lifecycle_state=excluded.lifecycle_state,
  metadata=pentas.nodes_v2.metadata || excluded.metadata,
  last_heartbeat_at=excluded.last_heartbeat_at,
  updated_at=excluded.updated_at;

do $do$
declare
  v_def text;
  v_old text := E'when ''penta.release'' then ''ct.penta.release''\n      else null';
  v_new text := E'when ''penta.release'' then ''ct.penta.release''\n      when ''penta.security'' then ''ct.penta.security''\n      else null';
begin
  v_def := pg_get_functiondef(
    'integration_control.penta_census_mobilize_safe_handoffs_v1(integer)'::regprocedure
  );

  -- Do not replace the current PentaContext semantics with the older mobilizer.
  if position('if h.target_ref=''penta.context'' then' in v_def) = 0 then
    raise exception 'PENTA_CONTEXT_ONLY_BRANCH_NOT_PRESENT';
  end if;

  if position('when ''penta.security'' then ''ct.penta.security''' in v_def) = 0 then
    if position(v_old in v_def) = 0 then
      raise exception 'PENTA_CENSUS_ROUTE_PATCH_ANCHOR_NOT_FOUND';
    end if;

    v_def := replace(v_def, v_old, v_new);
    execute v_def;
  end if;

  v_def := pg_get_functiondef(
    'integration_control.penta_census_mobilize_safe_handoffs_v1(integer)'::regprocedure
  );

  if position('if h.target_ref=''penta.context'' then' in v_def) = 0 then
    raise exception 'PENTA_CONTEXT_ONLY_BRANCH_REGRESSED';
  end if;

  if position('when ''penta.security'' then ''ct.penta.security''' in v_def) = 0 then
    raise exception 'PENTASECURITY_MOBILIZER_ROUTE_READBACK_FAILED';
  end if;
end
$do$;

comment on function integration_control.penta_census_mobilize_safe_handoffs_v1(integer) is
'PentaCensus bounded production mobilizer: preserves context-only PentaContext custody and adds canonical penta.security -> ct.penta.security D0-D2 routing without creating authority.';

do $do$
begin
  if not exists (
    select 1
    from pentas.nodes_v2
    where node_id='ct.penta.security'
      and lifecycle_state='active'
      and health_state in ('healthy','degraded')
      and authority_ceiling='D2'
      and endpoint_ref='penta_security.review_system_v1'
  ) then
    raise exception 'PENTASECURITY_NODE_REGISTRATION_READBACK_FAILED';
  end if;

  if position(
    'if h.target_ref=''penta.context'' then'
    in pg_get_functiondef('integration_control.penta_census_mobilize_safe_handoffs_v1(integer)'::regprocedure)
  ) = 0 then
    raise exception 'PENTA_CONTEXT_ONLY_ACCEPTANCE_FAILED';
  end if;

  if position(
    'when ''penta.security'' then ''ct.penta.security'''
    in pg_get_functiondef('integration_control.penta_census_mobilize_safe_handoffs_v1(integer)'::regprocedure)
  ) = 0 then
    raise exception 'PENTASECURITY_ROUTE_ACCEPTANCE_FAILED';
  end if;
end
$do$;
