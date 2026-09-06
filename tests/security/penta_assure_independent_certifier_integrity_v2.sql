-- Transactional acceptance/adversarial tests for
-- 20260830194000_penta_assure_independent_certifier_integrity_v2.sql
-- The test creates only certification rows inside this transaction and rolls them back.

begin;

do $test$
declare
  r jsonb;
  evidence jsonb := '["ct.evidence.test.independent-certifier"]'::jsonb;
  passing_checks jsonb := '[{"name":"deterministic-test","passed":true}]'::jsonb;
begin
  r := public.penta_assure_certify_v1('ct.test.assure.separated','ct.standard.assure.integrity.v2','D2',evidence,passing_checks,null,'{"certifier_id":"ct.agent.pentacertifier","originator_id":"ct.agent.originator","builder_ids":["ct.agent.builder"],"producer_ids":["ct.agent.producer"]}'::jsonb);
  if r->>'disposition' <> 'certified' or r->>'independence_state' <> 'separation_of_duties_satisfied' then raise exception 'POSITIVE_SEPARATION_CASE_FAILED: %', r; end if;

  r := public.penta_assure_certify_v1('ct.test.assure.self-cert','ct.standard.assure.integrity.v2','D2',evidence,passing_checks,null,'{"certifier_id":"ct.agent.same","originator_id":"ct.agent.same","builder_ids":["ct.agent.builder"]}'::jsonb);
  if r->>'disposition' <> 'hold' or r->>'independence_reason' <> 'self_certification_detected' then raise exception 'SELF_CERTIFICATION_WAS_NOT_HELD: %', r; end if;

  r := public.penta_assure_certify_v1('ct.test.assure.builder-cert','ct.standard.assure.integrity.v2','D2',evidence,passing_checks,null,'{"certifier_id":"ct.agent.builder","originator_id":"ct.agent.originator","builder_ids":["ct.agent.builder"]}'::jsonb);
  if r->>'disposition' <> 'hold' or r->>'independence_reason' <> 'certifier_is_builder' then raise exception 'BUILDER_SELF_CERTIFICATION_WAS_NOT_HELD: %', r; end if;

  r := public.penta_assure_certify_v1('ct.test.assure.producer-cert','ct.standard.assure.integrity.v2','D2',evidence,passing_checks,null,'{"certifier_id":"ct.agent.producer","originator_id":"ct.agent.originator","producer_ids":["ct.agent.producer"]}'::jsonb);
  if r->>'disposition' <> 'hold' or r->>'independence_reason' <> 'certifier_is_producer' then raise exception 'PRODUCER_SELF_CERTIFICATION_WAS_NOT_HELD: %', r; end if;

  r := public.penta_assure_certify_v1('ct.test.assure.missing-identities','ct.standard.assure.integrity.v2','D1',evidence,passing_checks,null,'{}'::jsonb);
  if r->>'disposition' <> 'hold' or r->>'independence_reason' <> 'missing_certifier_or_originator_identity' then raise exception 'MISSING_IDENTITIES_WERE_NOT_HELD: %', r; end if;

  r := public.penta_assure_certify_v1('ct.test.assure.bad-builder-shape','ct.standard.assure.integrity.v2','D2',evidence,passing_checks,null,'{"certifier_id":"ct.agent.pentacertifier","originator_id":"ct.agent.originator","builder_ids":"ct.agent.builder"}'::jsonb);
  if r->>'disposition' <> 'hold' or r->>'independence_reason' <> 'invalid_builder_identity_shape' then raise exception 'MALFORMED_BUILDER_SHAPE_WAS_NOT_HELD: %', r; end if;

  r := public.penta_assure_certify_v1('ct.test.assure.bad-check','ct.standard.assure.integrity.v2','D2',evidence,'[{"name":"adversarial","passed":"maybe"}]'::jsonb,null,'{"certifier_id":"ct.agent.pentacertifier","originator_id":"ct.agent.originator","builder_ids":["ct.agent.builder"]}'::jsonb);
  if r->>'disposition' <> 'hold' then raise exception 'MALFORMED_CHECK_WAS_NOT_HELD: %', r; end if;

  r := public.penta_assure_certify_v1('ct.test.assure.d3','ct.standard.assure.integrity.v2','D3',evidence,passing_checks,null,'{"certifier_id":"ct.agent.pentacertifier","originator_id":"ct.agent.originator","builder_ids":["ct.agent.builder"]}'::jsonb);
  if r->>'disposition' <> 'hold' or r->>'independence_reason' <> 'd3_human_reserved' then raise exception 'D3_WAS_NOT_HELD: %', r; end if;

  if has_function_privilege('anon','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamp with time zone,jsonb)','EXECUTE') then raise exception 'ANON_EXECUTE_MUST_BE_DENIED'; end if;
  if has_function_privilege('authenticated','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamp with time zone,jsonb)','EXECUTE') then raise exception 'AUTHENTICATED_EXECUTE_MUST_BE_DENIED'; end if;
  if not has_function_privilege('service_role','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamp with time zone,jsonb)','EXECUTE') then raise exception 'SERVICE_ROLE_EXECUTE_MUST_BE_RETAINED'; end if;
end
$test$;

rollback;