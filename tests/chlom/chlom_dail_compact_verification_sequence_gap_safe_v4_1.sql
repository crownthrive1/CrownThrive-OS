-- Contract regression for CHLOM DAIL compact verifier v4.1.
-- PostgreSQL sequence values are not transactional and must not be used as a
-- gapless integrity condition. Hash-chain linkage remains fail closed.

do $$
declare
  v_def text;
begin
  select pg_get_functiondef(p.oid)
  into v_def
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime'
    and p.proname='dail_verify_next_segment_v4'
    and pg_get_function_identity_arguments(p.oid)='p_max_events integer';

  if v_def is null then
    raise exception 'missing chlom_runtime.dail_verify_next_segment_v4(integer)';
  end if;

  if position('where e.sequence_id>v_cursor.verified_through_sequence_id' in v_def)=0 then
    raise exception 'verifier must select committed events after cursor, not dense integer range';
  end if;

  if position('limit p_max_events' in v_def)=0 then
    raise exception 'verifier must bound work by committed event count';
  end if;

  if position('lag(e.event_hash,1,v_cursor.verified_through_event_hash)' in v_def)=0 then
    raise exception 'verifier must bind first selected event to cursor event hash';
  end if;

  if position('dense_sequence_required' in v_def)=0 then
    raise exception 'verifier must emit explicit sequence-gap semantics';
  end if;

  if position('postgres_sequences_are_non_transactional' in v_def)=0 then
    raise exception 'verifier must preserve machine-readable gap rationale';
  end if;

  if position('v_expected_count:=(v_end-v_start+1)::integer' in v_def)>0 then
    raise exception 'legacy dense-sequence expected-count formula must be removed';
  end if;

  if position('where e.sequence_id between v_start-1 and v_end' in v_def)>0 then
    raise exception 'legacy dense integer range scan must be removed';
  end if;

  if position('v_link_failures=0' in v_def)=0
     or position('v_event_failures=0' in v_def)=0
     or position('v_payload_failures=0' in v_def)=0
     or position('v_boundary' in v_def)=0 then
    raise exception 'hash-chain/payload/boundary fail-closed predicates must remain';
  end if;

  if has_function_privilege('anon','chlom_runtime.dail_verify_next_segment_v4(integer)','EXECUTE') then
    raise exception 'anon must not execute DAIL verifier';
  end if;
  if has_function_privilege('authenticated','chlom_runtime.dail_verify_next_segment_v4(integer)','EXECUTE') then
    raise exception 'authenticated must not execute DAIL verifier';
  end if;
  if not has_function_privilege('service_role','chlom_runtime.dail_verify_next_segment_v4(integer)','EXECUTE') then
    raise exception 'service_role must retain DAIL verifier execution';
  end if;
end
$$;

-- Demonstrate the exact PostgreSQL sequence invariant that triggered the v4.0
-- false positive: an ordered committed set can have a sequence span larger than
-- its row count while remaining a valid ordered set.
do $$
declare
  v_count integer;
  v_min bigint;
  v_max bigint;
begin
  with committed(sequence_id) as (
    values (100::bigint),(101::bigint),(105::bigint),(106::bigint)
  )
  select count(*)::integer,min(sequence_id),max(sequence_id)
  into v_count,v_min,v_max
  from committed;

  if v_count<>(4) or (v_max-v_min+1)=v_count then
    raise exception 'regression fixture must contain legal sequence gaps';
  end if;
end
$$;
