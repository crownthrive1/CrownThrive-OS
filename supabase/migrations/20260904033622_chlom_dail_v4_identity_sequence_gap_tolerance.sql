-- Canonical source reconciliation for production-applied migration 20260904033622.
-- Runtime migration ledger name: chlom_dail_v4_identity_sequence_gap_tolerance.
-- Applied statement SHA-256: 2a204b88bb99e5ec01ccff5162c22f014c5d28010f8862e24639676a051b043d.
-- This source materializes current executable truth into protected-repo review; it does not
-- re-apply production when the migration version is already present and does not mutate
-- immutable DAIL events beyond the governed append-only correction evidence encoded below.

create table if not exists chlom_runtime.dail_verification_algorithm_corrections_v4 (
  correction_id uuid primary key default gen_random_uuid(),
  segment_id uuid not null unique references chlom_runtime.dail_verification_segments_v4(segment_id) on delete restrict,
  correction_state text not null check (correction_state in ('ACCEPTED','REJECTED','SUPERSEDED')),
  defect_class text not null,
  observed_event_count integer not null,
  requested_numeric_span integer not null,
  missing_identity_sequence_ids bigint[] not null default '{}'::bigint[],
  chain_integrity_failures integer not null default 0 check (chain_integrity_failures >= 0),
  authority_ref text not null,
  rationale text not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

alter table chlom_runtime.dail_verification_algorithm_corrections_v4 enable row level security;
alter table chlom_runtime.dail_verification_algorithm_corrections_v4 force row level security;
revoke all on chlom_runtime.dail_verification_algorithm_corrections_v4 from public,anon,authenticated;
grant all on chlom_runtime.dail_verification_algorithm_corrections_v4 to service_role;

drop trigger if exists dail_verification_algorithm_corrections_v4_append_only on chlom_runtime.dail_verification_algorithm_corrections_v4;
create trigger dail_verification_algorithm_corrections_v4_append_only
before update or delete on chlom_runtime.dail_verification_algorithm_corrections_v4
for each row execute function chlom_runtime.dail_reject_append_only_v4();

insert into chlom_runtime.dail_verification_algorithm_corrections_v4(
  segment_id,correction_state,defect_class,observed_event_count,requested_numeric_span,
  missing_identity_sequence_ids,chain_integrity_failures,authority_ref,rationale,evidence_sha256
)
select s.segment_id,'ACCEPTED','IDENTITY_SEQUENCE_GAPS_MISCLASSIFIED_AS_CHAIN_GAPS',
       s.event_count,s.expected_event_count,array[2152455::bigint,2152462::bigint,2154491::bigint],
       s.payload_hash_failures+s.predecessor_link_failures+s.event_hash_failures,
       'ct.ops.agent.dail-scaling-v4',
       'PostgreSQL identity values are monotonic but not gapless. The segment contained 4,997 valid chained events across a 5,000-value numeric span; all payload, event-hash, and predecessor-link checks passed. The rejected segment remains immutable evidence and is excluded from the certified segment chain.',
       encode(extensions.digest(convert_to(
         s.segment_id::text||'|IDENTITY_SEQUENCE_GAPS_MISCLASSIFIED_AS_CHAIN_GAPS|2152455,2152462,2154491|'||
         s.event_count::text||'|'||s.expected_event_count::text||'|'||
         s.payload_hash_failures::text||'|'||s.predecessor_link_failures::text||'|'||s.event_hash_failures::text,
         'UTF8'),'sha256'),'hex')
from chlom_runtime.dail_verification_segments_v4 s
where s.segment_id='cfcf6326-ac82-40f4-a0e6-eaf4557ea82b'::uuid
on conflict(segment_id) do nothing;

update chlom_runtime.dail_verification_cursors_v4
set cursor_state='ACTIVE',
    last_error=jsonb_build_object(
      'prior_hold_segment_id','cfcf6326-ac82-40f4-a0e6-eaf4557ea82b',
      'correction_state','ACCEPTED',
      'defect_class','IDENTITY_SEQUENCE_GAPS_MISCLASSIFIED_AS_CHAIN_GAPS',
      'cursor_advanced',false,
      'missing_identity_sequence_ids',jsonb_build_array(2152455,2152462,2154491)
    ),
    updated_at=clock_timestamp()
where cursor_key='canonical'
  and cursor_state='HOLD_INTEGRITY'
  and last_error->>'segment_id'='cfcf6326-ac82-40f4-a0e6-eaf4557ea82b';

create or replace function chlom_runtime.dail_verify_next_segment_v4(p_max_events integer default 5000)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','chlom_runtime','public'
set "TimeZone"='UTC'
as $$
declare
  v_cursor chlom_runtime.dail_verification_cursors_v4%rowtype;
  v_head_sequence bigint;
  v_head_hash text;
  v_start bigint;
  v_end bigint;
  v_expected_count integer;
  v_numeric_span bigint;
  v_identity_gap_count bigint;
  v_count integer;
  v_min_sequence bigint;
  v_max_sequence bigint;
  v_hashes text[];
  v_first_hash text;
  v_last_hash text;
  v_first_prior_hash text;
  v_previous_root text;
  v_root text;
  v_payload_failures integer;
  v_link_failures integer;
  v_event_failures integer;
  v_corrections integer;
  v_first_failure bigint;
  v_contiguous boolean;
  v_boundary boolean;
  v_state text;
  v_segment_id uuid;
  v_segment_key text;
  v_canonical jsonb;
  v_payload_sha text;
  v_signature text;
  v_started_at timestamptz:=clock_timestamp();
  v_duration_ms numeric(18,3);
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:dail:compact-verification:v4',0)) then
    return jsonb_build_object('ok',true,'state','DEFERRED_CONCURRENT_RUN','authority_created',false,'observed_at',clock_timestamp());
  end if;
  p_max_events:=greatest(100,least(coalesce(p_max_events,5000),10000));

  select * into v_cursor
  from chlom_runtime.dail_verification_cursors_v4
  where cursor_key='canonical'
  for update;
  if not found then
    return jsonb_build_object('ok',false,'state','HOLD_NO_V4_CURSOR','authority_created',false,'observed_at',clock_timestamp());
  end if;
  if v_cursor.cursor_state in ('HOLD_INTEGRITY','SUSPENDED') then
    return jsonb_build_object('ok',false,'state',v_cursor.cursor_state,'last_error',v_cursor.last_error,'authority_created',false,'observed_at',clock_timestamp());
  end if;

  select sequence_id,event_hash into v_head_sequence,v_head_hash
  from chlom_runtime.dail_events order by sequence_id desc limit 1;

  select min(sequence_id),max(sequence_id),count(*)::integer
  into v_start,v_end,v_expected_count
  from (
    select sequence_id
    from chlom_runtime.dail_events
    where sequence_id>v_cursor.verified_through_sequence_id
    order by sequence_id
    limit p_max_events
  ) q;

  if v_expected_count=0 then
    update chlom_runtime.dail_verification_cursors_v4
    set cursor_state='CAUGHT_UP',last_run_at=clock_timestamp(),updated_at=clock_timestamp(),last_error=null
    where cursor_key='canonical';
    return jsonb_build_object('ok',true,'state','CAUGHT_UP',
      'verified_through_sequence_id',v_cursor.verified_through_sequence_id,
      'head_sequence_id',v_head_sequence,'sequence_span_lag',greatest(v_head_sequence-v_cursor.verified_through_sequence_id,0),
      'authority_created',false,'observed_at',clock_timestamp());
  end if;

  v_numeric_span:=v_end-v_start+1;
  v_identity_gap_count:=v_numeric_span-v_expected_count;

  with source_rows as (
    select e.*,
           lag(e.event_hash) over(order by e.sequence_id) as prior_stored_hash
    from chlom_runtime.dail_events e
    where e.sequence_id between v_cursor.verified_through_sequence_id and v_end
  ), payload_calc as (
    select s.*,
           encode(extensions.digest(convert_to(coalesce(s.payload,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex') as expected_payload_sha256
    from source_rows s
  ), event_calc as (
    select p.*,
           chlom_runtime.dail_expected_event_hash_v4(
             p.prior_stored_hash,p.event_id,p.schema_version,p.event_type,p.entity_type,p.entity_id,
             p.entity_version,p.actor_did,p.actor_ref,p.expected_payload_sha256,p.created_at
           ) as expected_event_hash
    from payload_calc p
    where p.sequence_id>v_cursor.verified_through_sequence_id
  ), validated as (
    select e.*,
           exists(
             select 1
             from chlom_runtime.dail_integrity_corrections x
             where x.event_id=e.event_id
               and x.sequence_id=e.sequence_id
               and x.original_event_hash=e.event_hash
               and x.expected_event_hash=e.expected_event_hash
               and x.payload_sha256=e.expected_payload_sha256
               and x.previous_event_hash is not distinct from e.prior_stored_hash
               and x.correction_state='accepted'
           ) as documented_correction
    from event_calc e
  )
  select count(*)::integer,
         min(sequence_id),max(sequence_id),
         array_agg(event_hash order by sequence_id),
         (array_agg(event_hash order by sequence_id))[1],
         (array_agg(event_hash order by sequence_id desc))[1],
         (array_agg(prior_stored_hash order by sequence_id))[1],
         count(*) filter(where payload_sha256 is distinct from expected_payload_sha256)::integer,
         count(*) filter(where previous_event_hash is distinct from prior_stored_hash)::integer,
         count(*) filter(where event_hash is distinct from expected_event_hash and not documented_correction)::integer,
         count(*) filter(where documented_correction)::integer,
         min(sequence_id) filter(where payload_sha256 is distinct from expected_payload_sha256
                                  or previous_event_hash is distinct from prior_stored_hash
                                  or (event_hash is distinct from expected_event_hash and not documented_correction))
  into v_count,v_min_sequence,v_max_sequence,v_hashes,v_first_hash,v_last_hash,v_first_prior_hash,
       v_payload_failures,v_link_failures,v_event_failures,v_corrections,v_first_failure
  from validated;

  v_contiguous:=v_count=v_expected_count and v_min_sequence=v_start and v_max_sequence=v_end;
  v_boundary:=v_first_prior_hash is not distinct from v_cursor.verified_through_event_hash;
  v_state:=case when v_contiguous and v_boundary and v_payload_failures=0 and v_link_failures=0 and v_event_failures=0 then 'PASS' else 'HOLD' end;

  if v_cursor.last_segment_id is null then
    v_previous_root:=v_cursor.base_merkle_root_sha256;
  else
    select merkle_root_sha256 into v_previous_root
    from chlom_runtime.dail_verification_segments_v4
    where segment_id=v_cursor.last_segment_id and verification_state='PASS';
    if v_previous_root is null then
      v_state:='HOLD';
      v_first_failure:=coalesce(v_first_failure,v_start);
      v_previous_root:=v_cursor.base_merkle_root_sha256;
    end if;
  end if;

  v_root:=chlom_runtime.dail_merkle_root_v2(v_hashes);
  v_segment_key:='dail-v4:'||lpad(v_start::text,18,'0')||'-'||lpad(v_end::text,18,'0');
  v_duration_ms:=round(extract(epoch from (clock_timestamp()-v_started_at))*1000,3);
  v_canonical:=jsonb_build_object(
    'contract','ct.dail.compact-verification-segment.v4',
    'segment_key',v_segment_key,
    'start_sequence_id',v_start,
    'end_sequence_id',v_end,
    'event_count',v_count,
    'numeric_sequence_span',v_numeric_span,
    'identity_sequence_gap_count',v_identity_gap_count,
    'identity_sequence_gaps_permitted',true,
    'head_at_start_sequence_id',v_head_sequence,
    'head_at_start_event_hash',v_head_hash,
    'first_event_hash',v_first_hash,
    'last_event_hash',v_last_hash,
    'previous_segment_root_sha256',v_previous_root,
    'merkle_root_sha256',v_root,
    'selected_event_count_complete',v_contiguous,
    'boundary_hash_match',v_boundary,
    'payload_hash_failures',v_payload_failures,
    'predecessor_link_failures',v_link_failures,
    'event_hash_failures',v_event_failures,
    'documented_corrections',v_corrections,
    'verification_state',v_state,
    'hash_algorithm','SHA-256',
    'verification_mode','bounded_ordered_event_batch_no_membership_rewrite'
  );
  v_payload_sha:=public.penta_protocol_sha256_v1(v_canonical);
  v_signature:=public.pentas_hmac_sha256_v2(v_canonical);

  insert into chlom_runtime.dail_verification_segments_v4(
    segment_key,start_sequence_id,end_sequence_id,event_count,head_at_start_sequence_id,head_at_start_event_hash,
    first_event_hash,last_event_hash,previous_segment_root_sha256,merkle_root_sha256,expected_event_count,
    contiguous_sequence,boundary_hash_match,payload_hash_failures,predecessor_link_failures,event_hash_failures,
    documented_corrections,first_failure_sequence_id,verification_state,canonical_payload_sha256,signature_ref,
    signature_state,verification_duration_ms,evidence
  ) values(
    v_segment_key,v_start,v_end,v_count,v_head_sequence,v_head_hash,v_first_hash,v_last_hash,v_previous_root,v_root,
    v_expected_count,v_contiguous,v_boundary,v_payload_failures,v_link_failures,v_event_failures,v_corrections,
    v_first_failure,v_state,v_payload_sha,'vault://ct_pentas_v2_hmac_primary#'||v_signature,'verified',
    v_duration_ms,jsonb_build_object('canonical',v_canonical,'content_address','sha256:'||v_payload_sha,
      'numeric_sequence_span',v_numeric_span,'identity_sequence_gap_count',v_identity_gap_count,
      'identity_sequence_gaps_permitted',true,'mass_dail_event_update',false,
      'per_event_membership_write',false,'external_chain_transaction',false)
  ) returning segment_id into v_segment_id;

  if v_state='PASS' then
    insert into chlom_runtime.dail_anchor_intents_v4(
      segment_id,checkpoint_root_sha256,anchor_policy,intent_state,authority_ref,evidence
    ) values(
      v_segment_id,v_root,'ct.policy.chlom.anchor.chain-portable.v1','PRODUCTION_GATED',
      'CHLOM_D3_EXTERNAL_BROADCAST_SEPARATELY_CERTIFIED',
      jsonb_build_object('segment_key',v_segment_key,'raw_private_evidence_included',false,
        'public_chain_broadcast',false,'provider_receipt_required',true)
    );
    update chlom_runtime.dail_verification_cursors_v4
    set verified_through_sequence_id=v_end,verified_through_event_hash=v_last_hash,last_segment_id=v_segment_id,
        cursor_state=case when v_end>=v_head_sequence then 'CAUGHT_UP' else 'ACTIVE' end,
        last_error=null,last_run_at=clock_timestamp(),updated_at=clock_timestamp()
    where cursor_key='canonical';
  else
    update chlom_runtime.dail_verification_cursors_v4
    set cursor_state='HOLD_INTEGRITY',
        last_error=jsonb_build_object('segment_id',v_segment_id,'segment_key',v_segment_key,
          'first_failure_sequence_id',v_first_failure,'payload_hash_failures',v_payload_failures,
          'predecessor_link_failures',v_link_failures,'event_hash_failures',v_event_failures,
          'selected_event_count_complete',v_contiguous,'boundary_hash_match',v_boundary),
        last_run_at=clock_timestamp(),updated_at=clock_timestamp()
    where cursor_key='canonical';
  end if;

  return jsonb_build_object(
    'ok',v_state='PASS','state',case when v_state='PASS' then 'SEGMENT_ATTESTED' else 'HOLD_INTEGRITY' end,
    'segment_id',v_segment_id,'segment_key',v_segment_key,'start_sequence_id',v_start,'end_sequence_id',v_end,
    'event_count',v_count,'numeric_sequence_span',v_numeric_span,'identity_sequence_gap_count',v_identity_gap_count,
    'identity_sequence_gaps_permitted',true,'head_at_start_sequence_id',v_head_sequence,
    'sequence_span_lag',greatest(v_head_sequence-v_end,0),'merkle_root_sha256',v_root,
    'canonical_payload_sha256',v_payload_sha,'signature_state','verified',
    'payload_hash_failures',v_payload_failures,'predecessor_link_failures',v_link_failures,
    'event_hash_failures',v_event_failures,'documented_corrections',v_corrections,
    'verification_duration_ms',v_duration_ms,'mass_dail_event_update',false,
    'per_event_membership_write',false,'exact_antijoin_count',false,'authority_created',false,
    'observed_at',clock_timestamp()
  );
end
$$;

create or replace function chlom_runtime.dail_merkle_proof_v4(p_sequence_id bigint)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','chlom_runtime','extensions'
as $$
declare
  v_segment chlom_runtime.dail_verification_segments_v4%rowtype;
  v_index integer;
  v_hash text;
  v_layer text[];
  v_next text[];
  v_count integer;
  v_sibling integer;
  v_proof jsonb:='[]'::jsonb;
  i integer;
  v_left text;
  v_right text;
  v_recomputed_root text;
begin
  select * into v_segment
  from chlom_runtime.dail_verification_segments_v4 s
  where s.verification_state='PASS'
    and p_sequence_id between s.start_sequence_id and s.end_sequence_id
    and not exists(
      select 1 from chlom_runtime.dail_verification_algorithm_corrections_v4 c
      where c.segment_id=s.segment_id and c.correction_state='ACCEPTED'
    )
  order by s.end_sequence_id
  limit 1;
  if not found then
    return jsonb_build_object('ok',false,'reason','event_not_in_v4_verified_segment','sequence_id',p_sequence_id);
  end if;

  select count(*)::integer into v_index
  from chlom_runtime.dail_events
  where sequence_id between v_segment.start_sequence_id and p_sequence_id-1;
  select event_hash into v_hash
  from chlom_runtime.dail_events where sequence_id=p_sequence_id;
  if v_hash is null then
    return jsonb_build_object('ok',false,'reason','event_sequence_not_present','sequence_id',p_sequence_id,
      'segment_id',v_segment.segment_id);
  end if;

  select array_agg(event_hash order by sequence_id) into v_layer
  from chlom_runtime.dail_events
  where sequence_id between v_segment.start_sequence_id and v_segment.end_sequence_id;
  v_count:=coalesce(array_length(v_layer,1),0);
  if v_count<>v_segment.event_count then
    return jsonb_build_object('ok',false,'reason','segment_event_count_mismatch','sequence_id',p_sequence_id,
      'segment_id',v_segment.segment_id,'expected_count',v_segment.event_count,'observed_count',v_count);
  end if;
  v_recomputed_root:=chlom_runtime.dail_merkle_root_v2(v_layer);
  if v_recomputed_root is distinct from v_segment.merkle_root_sha256 then
    return jsonb_build_object('ok',false,'reason','segment_root_mismatch','sequence_id',p_sequence_id,
      'segment_id',v_segment.segment_id,'expected_root_sha256',v_segment.merkle_root_sha256,
      'observed_root_sha256',v_recomputed_root);
  end if;

  while v_count>1 loop
    v_sibling:=case when mod(v_index,2)=0 then v_index+1 else v_index-1 end;
    if v_sibling>=v_count then v_sibling:=v_index; end if;
    v_proof:=v_proof||jsonb_build_array(jsonb_build_object(
      'side',case when mod(v_index,2)=0 then 'right' else 'left' end,
      'sha256',v_layer[v_sibling+1]
    ));
    v_next:='{}'::text[];
    i:=1;
    while i<=v_count loop
      v_left:=v_layer[i];
      v_right:=case when i+1<=v_count then v_layer[i+1] else v_layer[i] end;
      v_next:=array_append(v_next,encode(extensions.digest(decode(v_left,'hex')||decode(v_right,'hex'),'sha256'),'hex'));
      i:=i+2;
    end loop;
    v_layer:=v_next;
    v_count:=array_length(v_layer,1);
    v_index:=floor(v_index/2.0)::integer;
  end loop;

  return jsonb_build_object(
    'ok',true,'contract','ct.dail.inclusion-proof.v4','sequence_id',p_sequence_id,
    'segment_id',v_segment.segment_id,'segment_key',v_segment.segment_key,
    'segment_start_sequence_id',v_segment.start_sequence_id,'segment_end_sequence_id',v_segment.end_sequence_id,
    'leaf_hash',v_hash,'merkle_root_sha256',v_segment.merkle_root_sha256,
    'previous_segment_root_sha256',v_segment.previous_segment_root_sha256,
    'canonical_payload_sha256',v_segment.canonical_payload_sha256,
    'signature_ref',v_segment.signature_ref,'signature_state',v_segment.signature_state,
    'proof',v_proof,'proof_length',jsonb_array_length(v_proof)
  );
end
$$;

create or replace function chlom_runtime.verify_dail_chain_v4()
returns jsonb
language plpgsql
stable
security definer
set search_path='pg_catalog','extensions','chlom_runtime'
as $$
declare
  v_cursor chlom_runtime.dail_verification_cursors_v4%rowtype;
  v_base chlom_runtime.dail_epoch_checkpoints_v2%rowtype;
  v_base_event_hash text;
  v_base_proof jsonb;
  v_head_sequence bigint;
  v_head_hash text;
  v_segment_count bigint;
  v_segment_events bigint;
  v_invalidated_segments bigint;
  v_hold_segments bigint;
  v_order_failures bigint;
  v_root_link_failures bigint;
  v_last_segment_end bigint;
  v_last_segment_id uuid;
  v_last_segment_hash text;
  v_cursor_event_hash text;
  v_prefix_ok boolean;
  v_caught_up boolean;
  v_started timestamptz:=clock_timestamp();
begin
  select * into v_cursor from chlom_runtime.dail_verification_cursors_v4 where cursor_key='canonical';
  if not found then
    return jsonb_build_object('ok',false,'integrity_state','HOLD_NO_V4_CURSOR','verification_mode','compact_segment_chain_v4',
      'full_chain_scan_executed',false,'checked_at',clock_timestamp());
  end if;
  select * into v_base from chlom_runtime.dail_epoch_checkpoints_v2 where checkpoint_id=v_cursor.base_checkpoint_id;
  if not found then
    return jsonb_build_object('ok',false,'integrity_state','HOLD_BASE_CHECKPOINT_MISSING','verification_mode','compact_segment_chain_v4',
      'full_chain_scan_executed',false,'checked_at',clock_timestamp());
  end if;
  select event_hash into v_base_event_hash from chlom_runtime.dail_events where sequence_id=v_base.end_sequence_id;
  begin
    v_base_proof:=chlom_runtime.dail_verify_merkle_proof_v2(v_base.end_sequence_id);
  exception when others then
    v_base_proof:=jsonb_build_object('ok',false,'error_class',sqlstate,
      'error_message_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'));
  end;

  select count(*) into v_invalidated_segments
  from chlom_runtime.dail_verification_algorithm_corrections_v4
  where correction_state='ACCEPTED';

  with certified as (
    select s.*
    from chlom_runtime.dail_verification_segments_v4 s
    where s.verification_state='PASS'
      and not exists(
        select 1 from chlom_runtime.dail_verification_algorithm_corrections_v4 c
        where c.segment_id=s.segment_id and c.correction_state='ACCEPTED'
      )
  ), ordered as (
    select s.*,
      lag(s.end_sequence_id) over(order by s.start_sequence_id) as prior_end_sequence_id,
      lag(s.merkle_root_sha256) over(order by s.start_sequence_id) as prior_merkle_root
    from certified s
  )
  select count(*),coalesce(sum(event_count),0),
         count(*) filter(where start_sequence_id<=coalesce(prior_end_sequence_id,v_base.end_sequence_id)),
         count(*) filter(where previous_segment_root_sha256 is distinct from coalesce(prior_merkle_root,v_base.merkle_root_sha256)),
         max(end_sequence_id),
         (array_agg(segment_id order by start_sequence_id desc))[1],
         (array_agg(last_event_hash order by start_sequence_id desc))[1]
  into v_segment_count,v_segment_events,v_order_failures,v_root_link_failures,
       v_last_segment_end,v_last_segment_id,v_last_segment_hash
  from ordered;

  select count(*) into v_hold_segments
  from chlom_runtime.dail_verification_segments_v4 s
  where s.verification_state='HOLD'
    and not exists(
      select 1 from chlom_runtime.dail_verification_algorithm_corrections_v4 c
      where c.segment_id=s.segment_id and c.correction_state='ACCEPTED'
    );

  select sequence_id,event_hash into v_head_sequence,v_head_hash
  from chlom_runtime.dail_events order by sequence_id desc limit 1;
  select event_hash into v_cursor_event_hash
  from chlom_runtime.dail_events where sequence_id=v_cursor.verified_through_sequence_id;

  v_prefix_ok:=
    v_base.checkpoint_state='attested'
    and v_base.signature_state='verified'
    and v_base_event_hash is not distinct from v_base.last_event_hash
    and coalesce((v_base_proof->>'ok')::boolean,false)
    and v_hold_segments=0
    and v_order_failures=0
    and v_root_link_failures=0
    and (
      (v_segment_count=0 and v_cursor.verified_through_sequence_id=v_base.end_sequence_id
       and v_cursor.verified_through_event_hash=v_base.last_event_hash)
      or
      (v_segment_count>0 and v_cursor.last_segment_id=v_last_segment_id
       and v_cursor.verified_through_sequence_id=v_last_segment_end
       and v_cursor.verified_through_event_hash=v_last_segment_hash
       and v_cursor_event_hash=v_last_segment_hash)
    );
  v_caught_up:=v_cursor.verified_through_sequence_id>=v_head_sequence;

  return jsonb_build_object(
    'ok',v_prefix_ok and v_caught_up,
    'verified_prefix_ok',v_prefix_ok,
    'caught_up_to_observed_head',v_caught_up,
    'integrity_state',case
      when not v_prefix_ok then 'HOLD_COMPACT_CHAIN_INTEGRITY'
      when v_caught_up then 'PASS_GLOBAL_COMPACT_CHAIN'
      else 'PASS_VERIFIED_PREFIX_CATCHUP_PENDING'
    end,
    'verification_mode','v2_attested_base_plus_v4_compact_ordered_event_segments',
    'base_checkpoint_id',v_base.checkpoint_id,
    'checkpoint_id',v_base.checkpoint_id,
    'checkpoint_end_sequence_id',v_base.end_sequence_id,
    'checkpoint_event_count',v_base.event_count,
    'checkpoint_merkle_root_sha256',v_base.merkle_root_sha256,
    'checkpoint_signature_state',v_base.signature_state,
    'checkpoint_state',v_base.checkpoint_state,
    'checkpoint_end_hash_match',v_base_event_hash is not distinct from v_base.last_event_hash,
    'checkpoint_end_inclusion_proof',v_base_proof,
    'v4_segment_count',v_segment_count,
    'v4_segment_event_count',v_segment_events,
    'v4_invalidated_algorithm_segment_count',v_invalidated_segments,
    'v4_unresolved_hold_segment_count',v_hold_segments,
    'v4_order_overlap_failures',v_order_failures,
    'v4_root_link_failures',v_root_link_failures,
    'identity_sequence_gaps_permitted',true,
    'verified_through_sequence_id',v_cursor.verified_through_sequence_id,
    'verified_through_event_hash',v_cursor.verified_through_event_hash,
    'tail_checked_events',v_segment_events,
    'current_max_sequence_id',v_head_sequence,
    'current_head_hash',v_head_hash,
    'head_hash',v_head_hash,
    'sequence_span_lag',greatest(v_head_sequence-v_cursor.verified_through_sequence_id,0),
    'remaining_count_mode','indexed_head_minus_cursor_sequence_span',
    'full_chain_scan_executed',false,
    'monolithic_tail_scan_executed',false,
    'per_event_membership_rewrite_executed',false,
    'duration_ms',round(extract(epoch from(clock_timestamp()-v_started))*1000,3),
    'checked_at',clock_timestamp()
  );
end
$$;

comment on table chlom_runtime.dail_verification_algorithm_corrections_v4 is
'Append-only algorithm correction evidence. Distinguishes verifier implementation defects from DAIL event-integrity defects.';
comment on function chlom_runtime.dail_verify_next_segment_v4(integer) is
'Batches by actual ordered DAIL events. PostgreSQL identity-sequence gaps are permitted; cryptographic predecessor links remain mandatory.';