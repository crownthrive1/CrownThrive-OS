-- DAIL evidence spine v2
--
-- Additive extension of the live CHLOM DAIL chain. This migration deliberately
-- fails closed when the live v1/v1.1 substrate is absent or materially different;
-- it never creates a replacement chain and never rewrites historic events.
--
-- External provider HMAC verification is transactional evidence. Because HMAC
-- uses a shared secret, it is not public-key nonrepudiation and does not by itself
-- constitute an independent immutable anchor.

begin;

do $preflight$
declare
  v_missing text[];
begin
  if to_regclass('chlom_runtime.dail_events') is null then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: chlom_runtime.dail_events is absent; refusing to create a replacement chain';
  end if;

  if to_regclass('chlom_runtime.dail_integrity_corrections') is null then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: documented legacy correction ledger is absent';
  end if;

  if to_regclass('vault.decrypted_secrets') is null then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: Supabase Vault decrypted_secrets view is absent';
  end if;

  select array_agg(required.column_name order by required.column_name)
    into v_missing
  from (
    values
      ('sequence_id'), ('event_id'), ('event_type'), ('schema_version'),
      ('actor_ref'), ('actor_did'), ('agent_id'), ('source_system'),
      ('entity_type'), ('entity_id'), ('entity_version'), ('correlation_id'),
      ('causation_id'), ('authority_basis'), ('approval_id'),
      ('visibility_class'), ('payload'), ('payload_sha256'),
      ('previous_event_hash'), ('event_hash'), ('chain_anchor_state'),
      ('signature_ref'), ('created_at')
  ) as required(column_name)
  where not exists (
    select 1
    from information_schema.columns c
    where c.table_schema = 'chlom_runtime'
      and c.table_name = 'dail_events'
      and c.column_name = required.column_name
  );

  if v_missing is not null then
    raise exception using
      errcode = '55000',
      message = format('DAIL v2 preflight failed: missing live columns %s', v_missing::text);
  end if;

  if not exists (
    select 1
    from information_schema.columns c
    where c.table_schema = 'chlom_runtime'
      and c.table_name = 'dail_events'
      and c.column_name = 'sequence_id'
      and c.data_type = 'bigint'
      and c.is_identity = 'YES'
      and c.identity_generation = 'ALWAYS'
  ) then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: sequence_id is not the expected bigint GENERATED ALWAYS identity';
  end if;

  if to_regprocedure(
    'chlom_runtime.append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text)'
  ) is null then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: live v1/v1.1 append function is absent';
  end if;

  if pg_get_functiondef(
    'chlom_runtime.append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text)'::regprocedure
  ) not like '%pg_advisory_xact_lock(hashtext(''chlom_runtime.dail.global.v1''))%' then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: legacy writer does not use the canonical chain lock';
  end if;

  if to_regprocedure('chlom_runtime.verify_dail_chain()') is null then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: live chain verifier is absent';
  end if;

  if exists (
    select 1
    from pg_proc p
    where p.oid in (
      'chlom_runtime.append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text)'::regprocedure,
      'chlom_runtime.verify_dail_chain()'::regprocedure
    )
      and (p.prorettype <> 'jsonb'::regtype or not p.prosecdef)
  ) then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: inherited writer/verifier security or return contract drifted';
  end if;

  if not exists (
    select 1
    from pg_index i
    where i.indrelid = 'chlom_runtime.dail_events'::regclass
      and i.indisunique
      and i.indpred is null
      and i.indexprs is null
      and i.indkey::smallint[] @> array[
        (
          select a.attnum::smallint
          from pg_attribute a
          where a.attrelid = i.indrelid and a.attname = 'event_id'
        )
      ]::smallint[]
  ) then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: event_id is not protected by a unique index';
  end if;

  if not coalesce((chlom_runtime.verify_dail_chain()->>'ok')::boolean, false) then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: inherited ledger verification did not pass';
  end if;
end
$preflight$;

create or replace function chlom_runtime.reject_append_only_mutation_v2()
returns trigger
language plpgsql
security invoker
set search_path = 'pg_catalog', 'chlom_runtime'
as $function$
begin
  raise exception using
    errcode = '55000',
    message = format(
      'append-only ledger mutation rejected: %s on %I.%I',
      tg_op,
      tg_table_schema,
      tg_table_name
    );
end
$function$;

create or replace function chlom_runtime.append_factory_continuation_v2(
  p_factory_id text,
  p_run_id text,
  p_request_id text,
  p_stream_id text,
  p_lane text,
  p_ordinal bigint,
  p_attempt integer,
  p_state text,
  p_worker_id text,
  p_claim_id text,
  p_fencing_token bigint,
  p_idempotency_key text,
  p_input_digest_sha256 text,
  p_compiler_version text,
  p_authority_ref text,
  p_security_state text,
  p_security_verifier_id text,
  p_security_receipt_ref text,
  p_security_receipt_sha256 text,
  p_test_state text,
  p_test_verifier_id text,
  p_test_receipt_ref text,
  p_test_receipt_sha256 text,
  p_next_action text,
  p_output_digest_sha256 text default null,
  p_artifact_digest_sha256 text default null,
  p_lease_acquired_at timestamptz default null,
  p_lease_until timestamptz default null,
  p_available_at timestamptz default null,
  p_correlation_id text default null,
  p_causation_id text default null,
  p_provider_operation text default null,
  p_provider_idempotency_key text default null,
  p_provider_request_ref text default null,
  p_provider_request_digest text default null,
  p_provider_response_sha256 text default null,
  p_provider_readback_state text default 'not_applicable',
  p_provider_readback_receipt_ref text default null,
  p_readback_digest text default null,
  p_rollback_ref text default null,
  p_rollback_digest_sha256 text default null,
  p_error_class text default null,
  p_retry_count integer default 0,
  p_retryable boolean default false,
  p_next_retry_at timestamptz default null,
  p_started_at timestamptz default null,
  p_completed_at timestamptz default null,
  p_approval_id text default null
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog', 'extensions', 'chlom_runtime'
set "TimeZone" = 'UTC'
as $function$
declare
  v_continuation_id uuid := gen_random_uuid();
  v_processing_id uuid := gen_random_uuid();
  v_checkpoint_id text;
  v_dail_idempotency_key text;
  v_source_event_id text;
  v_processing_idempotency_key text;
  v_predecessor_checkpoint_id text;
  v_previous_event_hash text;
  v_content jsonb;
  v_content_digest text;
  v_dail_payload jsonb;
  v_dail jsonb;
  v_event_hash text;
  v_receipt_hash text;
  v_created_at timestamptz := clock_timestamp();
  v_processing_created_at timestamptz;
  v_processing_hash text;
  v_existing record;
begin
  if p_factory_id is null or length(p_factory_id) not between 1 and 255
     or p_run_id is null or length(p_run_id) not between 1 and 255
     or p_request_id is null or length(p_request_id) not between 1 and 255
     or p_stream_id is null or length(p_stream_id) not between 1 and 255
     or p_lane is null or length(p_lane) not between 1 and 128
     or p_worker_id is null or length(p_worker_id) not between 1 and 255
     or p_claim_id is null or length(p_claim_id) not between 1 and 255
     or p_idempotency_key is null or length(p_idempotency_key) not between 1 and 512
     or p_compiler_version is null or length(p_compiler_version) not between 1 and 128
     or p_authority_ref is null or length(p_authority_ref) not between 1 and 255
     or p_next_action is null or length(p_next_action) not between 1 and 2000
     or p_ordinal < 0 or p_attempt <= 0 or p_fencing_token <= 0
     or p_retry_count < 0 then
    raise exception using errcode = '22023', message = 'invalid factory continuation identity or sequencing field';
  end if;

  if p_state not in ('checkpointed', 'ready', 'running', 'held', 'failed', 'superseded')
     or p_security_state not in ('not_run', 'pending', 'pass', 'fail', 'held')
     or p_test_state not in ('not_run', 'pending', 'pass', 'fail', 'held')
     or p_provider_readback_state not in ('not_applicable', 'not_performed', 'pass', 'fail') then
    raise exception using errcode = '22023', message = 'invalid factory continuation state';
  end if;

  if p_input_digest_sha256 !~ '^[0-9a-f]{64}$'
     or (p_output_digest_sha256 is not null and p_output_digest_sha256 !~ '^[0-9a-f]{64}$')
     or (p_artifact_digest_sha256 is not null and p_artifact_digest_sha256 !~ '^[0-9a-f]{64}$')
     or (p_provider_response_sha256 is not null and p_provider_response_sha256 !~ '^[0-9a-f]{64}$')
     or (p_provider_request_digest is not null and p_provider_request_digest !~ '^[0-9a-f]{64}$')
     or (p_readback_digest is not null and p_readback_digest !~ '^[0-9a-f]{64}$')
     or (p_rollback_digest_sha256 is not null and p_rollback_digest_sha256 !~ '^[0-9a-f]{64}$')
     or (p_security_receipt_sha256 is not null and p_security_receipt_sha256 !~ '^[0-9a-f]{64}$')
     or (p_test_receipt_sha256 is not null and p_test_receipt_sha256 !~ '^[0-9a-f]{64}$') then
    raise exception using errcode = '22023', message = 'invalid factory continuation digest';
  end if;

  if (
    p_security_state in ('pass', 'fail', 'held')
    and (
      p_security_verifier_id is null or p_security_receipt_ref is null
      or p_security_receipt_sha256 is null
    )
  ) or (
    p_test_state in ('pass', 'fail', 'held')
    and (
      p_test_verifier_id is null or p_test_receipt_ref is null
      or p_test_receipt_sha256 is null
    )
  ) then
    raise exception using
      errcode = '23502',
      message = 'completed assurance decisions require verifier identities and immutable receipt digests';
  end if;

  if (p_security_state = 'pass' and p_security_verifier_id = p_worker_id)
     or (p_test_state = 'pass' and p_test_verifier_id = p_worker_id)
     or (
       p_security_state = 'pass' and p_test_state = 'pass'
       and p_security_verifier_id = p_test_verifier_id
     ) then
    raise exception using
      errcode = '55000',
      message = 'factory producer, security verifier and test verifier must be distinct';
  end if;

  if (p_provider_operation is null and p_provider_readback_state <> 'not_applicable')
     or (p_provider_operation is not null and p_provider_readback_state = 'not_applicable') then
    raise exception using errcode = '22023', message = 'provider readback state must remain separate and match provider-operation presence';
  end if;
  if p_provider_operation is not null and (
    p_provider_idempotency_key is null or p_provider_request_ref is null
    or p_provider_request_digest is null
  ) then
    raise exception using
      errcode = '23502',
      message = 'provider operations require idempotency and request evidence references';
  end if;
  if p_provider_readback_state = 'pass' and (
    p_provider_response_sha256 is null or p_provider_readback_receipt_ref is null
    or p_readback_digest is null
  ) then
    raise exception using
      errcode = '23502',
      message = 'provider readback pass requires response and readback receipt evidence';
  end if;

  if (p_lease_acquired_at is null) <> (p_lease_until is null) then
    raise exception using errcode = '22023', message = 'factory lease timestamps must be supplied as a pair';
  end if;
  if p_state = 'running' and (
    p_lease_acquired_at is null
    or p_lease_until <= clock_timestamp()
  ) then
    raise exception using errcode = '55000', message = 'running factory work requires a current lease';
  end if;

  if (p_retryable and p_next_retry_at is null)
     or (not p_retryable and p_next_retry_at is not null)
     or (p_lease_acquired_at is not null and p_lease_until is not null and p_lease_until <= p_lease_acquired_at)
     or (p_started_at is not null and p_completed_at is not null and p_completed_at < p_started_at) then
    raise exception using errcode = '22023', message = 'invalid factory continuation time window';
  end if;

  v_checkpoint_id := 'fc2:' || encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
          'factory_id', p_factory_id,
          'run_id', p_run_id,
          'stream_id', p_stream_id,
          'lane', p_lane,
          'ordinal', p_ordinal,
          'attempt', p_attempt
        )),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );
  v_source_event_id := 'fc2:' || encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
          'factory_id', p_factory_id,
          'idempotency_key', p_idempotency_key
        )),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );
  v_dail_idempotency_key := v_source_event_id;
  v_processing_idempotency_key := 'fp2:' || substr(v_source_event_id, 5);
  v_content := jsonb_build_object(
    'contract_version', 'ct.factory-continuation.v2',
    'schema_version', '2.0.0',
    'canonicalization_version', 'ct-json-sort-v1',
    'factory_id', p_factory_id,
    'run_id', p_run_id,
    'request_id', p_request_id,
    'stream_id', p_stream_id,
    'lane', p_lane,
    'ordinal', p_ordinal,
    'attempt', p_attempt,
    'state', p_state,
    'checkpoint_id', v_checkpoint_id,
    'worker_id', p_worker_id,
    'claim_id', p_claim_id,
    'fencing_token', p_fencing_token,
    'idempotency_key', p_idempotency_key,
    'input_digest_sha256', p_input_digest_sha256,
    'output_digest_sha256', p_output_digest_sha256,
    'artifact_digest_sha256', p_artifact_digest_sha256,
    'compiler_version', p_compiler_version,
    'authority_ref', p_authority_ref,
    'approval_id', p_approval_id,
    'correlation_id', coalesce(p_correlation_id, p_request_id),
    'causation_id', p_causation_id,
    'provider_operation', p_provider_operation,
    'provider_idempotency_key', p_provider_idempotency_key,
    'provider_request_ref', p_provider_request_ref,
    'provider_request_digest', p_provider_request_digest,
    'provider_response_sha256', p_provider_response_sha256,
    'provider_readback_state', p_provider_readback_state,
    'provider_readback_receipt_ref', p_provider_readback_receipt_ref,
    'readback_digest', p_readback_digest,
    'rollback_ref', p_rollback_ref,
    'rollback_digest_sha256', p_rollback_digest_sha256,
    'error_class', p_error_class,
    'retryable', p_retryable,
    'retry_count', p_retry_count,
    'security_state', p_security_state,
    'security_verifier_id', p_security_verifier_id,
    'security_receipt_ref', p_security_receipt_ref,
    'security_receipt_sha256', p_security_receipt_sha256,
    'test_state', p_test_state,
    'test_verifier_id', p_test_verifier_id,
    'test_receipt_ref', p_test_receipt_ref,
    'test_receipt_sha256', p_test_receipt_sha256,
    'next_action', p_next_action
  );
  -- Lease, availability, retry and wall-clock timestamps are intentionally
  -- excluded from content_digest_sha256. They remain committed by receipt_sha256.
  v_content_digest := encode(
    extensions.digest(
      convert_to(chlom_runtime.canonical_jsonb_v1(v_content), 'UTF8'),
      'sha256'
    ),
    'hex'
  );

  perform pg_advisory_xact_lock(
    hashtext('chlom_runtime.factory-fence.v2:' || p_factory_id || ':' || p_stream_id || ':' || p_lane)
  );

  select f.*
    into v_existing
  from chlom_runtime.factory_continuation_receipts_v2 f
  where f.factory_id = p_factory_id
    and f.idempotency_key = p_idempotency_key;

  if found then
    if v_existing.content_digest_sha256 = v_content_digest then
      return jsonb_build_object(
        'ok', true,
        'duplicate', true,
        'continuation_receipt_id', v_existing.continuation_receipt_id,
        'checkpoint_id', v_existing.checkpoint_id,
        'event_hash', v_existing.event_hash,
        'receipt_sha256', v_existing.receipt_sha256,
        'dail_event_id', v_existing.dail_event_id,
        'dail_event_hash', v_existing.dail_event_hash
      );
    end if;
    raise exception using errcode = '23505', message = 'factory continuation idempotency conflict';
  end if;

  select f.checkpoint_id, f.event_hash
    into v_predecessor_checkpoint_id, v_previous_event_hash
  from chlom_runtime.factory_continuation_receipts_v2 f
  where f.factory_id = p_factory_id
    and f.stream_id = p_stream_id
    and f.lane = p_lane
  order by f.ordinal desc, f.attempt desc, f.created_at desc
  limit 1;

  v_dail_payload := v_content || jsonb_build_object(
    'continuation_receipt_id', v_continuation_id,
    'content_digest_sha256', v_content_digest,
    'predecessor_checkpoint_id', v_predecessor_checkpoint_id,
    'lease_acquired_at', p_lease_acquired_at,
    'lease_until', p_lease_until,
    'available_at', p_available_at,
    'next_retry_at', p_next_retry_at,
    'started_at', p_started_at,
    'completed_at', p_completed_at
  );

  v_dail := chlom_runtime.append_dail_event_v2(
    p_event_type => 'factory.continuation.checkpointed',
    p_entity_type => 'factory_continuation',
    p_entity_id => v_continuation_id::text,
    p_source_system => 'crownthrive.factory',
    p_trust_domain => 'crownthrive.control-plane',
    p_evidence_class => 'E1_INTERNAL_HASHED',
    p_idempotency_key => v_dail_idempotency_key,
    p_payload => v_dail_payload,
    p_source_event_id => v_source_event_id,
    p_actor_ref => p_worker_id,
    p_agent_id => p_worker_id,
    p_entity_version => p_compiler_version,
    p_correlation_id => coalesce(p_correlation_id, p_request_id),
    p_causation_id => p_causation_id,
    p_authority_basis => p_authority_ref,
    p_approval_id => p_approval_id,
    p_visibility_class => 'internal',
    p_payload_ref => 'factory-continuation:' || v_continuation_id::text,
    p_chain_anchor_state => 'unanchored'
  );

  v_event_hash := encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
          'receipt_format', 'ct.factory-continuation-chain.v2',
          'canonicalization_version', 'ct-json-sort-v1',
          'continuation_receipt_id', v_continuation_id,
          'content_digest_sha256', v_content_digest,
          'previous_event_hash', v_previous_event_hash,
          'dail_event_id', v_dail->>'event_id',
          'dail_event_hash', v_dail->>'event_hash'
        )),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  v_receipt_hash := encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
          'receipt_format', 'ct.factory-continuation-receipt.v2',
          'canonicalization_version', 'ct-json-sort-v1',
          'continuation_receipt_id', v_continuation_id,
          'content_digest_sha256', v_content_digest,
          'previous_event_hash', v_previous_event_hash,
          'event_hash', v_event_hash,
          'dail_event_id', v_dail->>'event_id',
          'dail_event_hash', v_dail->>'event_hash',
          'lease_acquired_at', p_lease_acquired_at,
          'lease_until', p_lease_until,
          'available_at', p_available_at,
          'next_retry_at', p_next_retry_at,
          'started_at', p_started_at,
          'completed_at', p_completed_at,
          'created_at', to_char(v_created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
        )),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into chlom_runtime.factory_continuation_receipts_v2 (
    continuation_receipt_id, dail_event_id, dail_event_hash,
    contract_version, schema_version, canonicalization_version,
    factory_id, run_id, request_id, stream_id, lane, ordinal, attempt, state,
    checkpoint_id, predecessor_checkpoint_id, worker_id, claim_id, fencing_token,
    lease_acquired_at, lease_until, available_at, idempotency_key,
    input_digest_sha256, output_digest_sha256, artifact_digest_sha256,
    compiler_version, authority_ref, correlation_id, causation_id,
    previous_event_hash, event_hash,
    provider_operation, provider_idempotency_key, provider_request_ref, provider_request_digest,
    provider_response_sha256, provider_readback_state, provider_readback_receipt_ref, readback_digest,
    rollback_ref, rollback_digest_sha256, error_class, retry_count, retryable, next_retry_at,
    security_state, security_verifier_id, security_receipt_ref, security_receipt_sha256,
    test_state, test_verifier_id, test_receipt_ref, test_receipt_sha256,
    next_action, content_digest_sha256,
    started_at, completed_at, approval_id, receipt_sha256, created_at
  ) values (
    v_continuation_id, (v_dail->>'event_id')::uuid, v_dail->>'event_hash',
    'ct.factory-continuation.v2', '2.0.0', 'ct-json-sort-v1',
    p_factory_id, p_run_id, p_request_id, p_stream_id, p_lane, p_ordinal, p_attempt, p_state,
    v_checkpoint_id, v_predecessor_checkpoint_id, p_worker_id, p_claim_id, p_fencing_token,
    p_lease_acquired_at, p_lease_until, p_available_at, p_idempotency_key,
    p_input_digest_sha256, p_output_digest_sha256, p_artifact_digest_sha256,
    p_compiler_version, p_authority_ref, coalesce(p_correlation_id, p_request_id), p_causation_id,
    v_previous_event_hash, v_event_hash,
    p_provider_operation, p_provider_idempotency_key, p_provider_request_ref, p_provider_request_digest,
    p_provider_response_sha256, p_provider_readback_state, p_provider_readback_receipt_ref, p_readback_digest,
    p_rollback_ref, p_rollback_digest_sha256, p_error_class, p_retry_count, p_retryable, p_next_retry_at,
    p_security_state, p_security_verifier_id, p_security_receipt_ref, p_security_receipt_sha256,
    p_test_state, p_test_verifier_id, p_test_receipt_ref, p_test_receipt_sha256,
    p_next_action, v_content_digest,
    p_started_at, p_completed_at, p_approval_id, v_receipt_hash, v_created_at
  );

  v_processing_created_at := clock_timestamp();
  v_processing_hash := encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
          'receipt_format', 'dail.processing.v2',
          'canonicalization_version', 'ct-json-sort-v1',
          'processing_receipt_id', v_processing_id,
          'dail_event_id', v_dail->>'event_id',
          'dail_event_hash', v_dail->>'event_hash',
          'source_system', 'crownthrive.factory',
          'source_event_id', v_source_event_id,
          'consumer_id', 'ct.penta.mesh.factory-continuation.v2',
          'processing_state', 'queued',
          'attempt_no', 1,
          'idempotency_key', v_processing_idempotency_key,
          'created_at', to_char(v_processing_created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
        )),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into chlom_runtime.processing_receipts_v2 (
    processing_receipt_id, dail_event_id, dail_event_hash, source_system,
    source_event_id, consumer_id, processing_state, attempt_no,
    idempotency_key, receipt_sha256, created_at
  ) values (
    v_processing_id, (v_dail->>'event_id')::uuid, v_dail->>'event_hash', 'crownthrive.factory',
    v_source_event_id, 'ct.penta.mesh.factory-continuation.v2',
    'queued', 1, v_processing_idempotency_key,
    v_processing_hash, v_processing_created_at
  );

  return jsonb_build_object(
    'ok', true,
    'duplicate', false,
    'continuation_receipt_id', v_continuation_id,
    'checkpoint_id', v_checkpoint_id,
    'content_digest_sha256', v_content_digest,
    'previous_event_hash', v_previous_event_hash,
    'event_hash', v_event_hash,
    'receipt_sha256', v_receipt_hash,
    'dail_event_id', v_dail->>'event_id',
    'dail_event_hash', v_dail->>'event_hash',
    'processing_receipt_id', v_processing_id,
    'processing_state', 'queued'
  );
end
$function$;

create or replace function chlom_runtime.ingest_verified_external_event_v2(
  p_provider text,
  p_source_event_id text,
  p_provider_event_type text,
  p_provider_object_type text,
  p_provider_object_id text,
  p_api_version text,
  p_livemode boolean,
  p_pending_webhooks integer,
  p_provider_request_ref text,
  p_provider_account_ref text,
  p_raw_body_sha256 text,
  p_signed_payload_sha256 text,
  p_signature_header_sha256 text,
  p_signature_timestamp bigint,
  p_signature_tolerance_seconds integer,
  p_secret_version_ref text,
  p_verifier_id text,
  p_verifier_tool_version text,
  p_verifier_trust_domain text,
  p_producer_trust_domain text,
  p_admission_mac text,
  p_received_at timestamptz
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog', 'extensions', 'chlom_runtime'
set "TimeZone" = 'UTC'
as $function$
declare
  v_ingress_id uuid := gen_random_uuid();
  v_verification_id uuid := gen_random_uuid();
  v_processing_id uuid := gen_random_uuid();
  v_ingress_created_at timestamptz := clock_timestamp();
  v_verified_at timestamptz;
  v_processing_created_at timestamptz;
  v_environment text;
  v_ingress_hash text;
  v_verification_hash text;
  v_processing_hash text;
  v_dail jsonb;
  v_payload jsonb;
  -- record avoids making function creation depend on companion table ordering;
  -- the migration creates the table before this function can be invoked.
  v_existing_ingress record;
  v_existing_verification_id uuid;
  v_existing_event_id uuid;
  v_existing_event_hash text;
  v_existing_sequence_id bigint;
  v_admission_key text;
  v_expected_admission_mac text;
  v_limitation constant text :=
    'Shared-secret HMAC proves possession of the endpoint secret and payload integrity; it is not public-key nonrepudiation or an external immutable anchor.';
begin
  if p_provider <> 'stripe' then
    raise exception using errcode = '22023', message = 'unsupported external HMAC provider';
  end if;

  if p_source_event_id is null or length(p_source_event_id) not between 1 and 255
     or p_provider_event_type is null or length(p_provider_event_type) not between 1 and 160
     or p_provider_object_type is null or length(p_provider_object_type) not between 1 and 100
     or p_provider_object_id is null or length(p_provider_object_id) not between 1 and 255
     or p_livemode is null or p_pending_webhooks is null or p_received_at is null
     or p_verifier_id is null or length(p_verifier_id) not between 1 and 255
     or p_verifier_tool_version is null or length(p_verifier_tool_version) not between 1 and 128
     or p_verifier_trust_domain is null or length(p_verifier_trust_domain) not between 1 and 128
     or p_producer_trust_domain is null or length(p_producer_trust_domain) not between 1 and 128
     or (p_provider_request_ref is not null and length(p_provider_request_ref) > 255)
     or p_verifier_trust_domain = p_producer_trust_domain then
    raise exception using errcode = '22023', message = 'invalid external evidence identity or trust-domain separation';
  end if;

  if p_raw_body_sha256 !~ '^[0-9a-f]{64}$'
     or p_signed_payload_sha256 !~ '^[0-9a-f]{64}$'
     or p_signature_header_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '22023', message = 'invalid external evidence digest';
  end if;

  if p_secret_version_ref is null
     or length(p_secret_version_ref) not between 1 and 200
     or p_secret_version_ref ~* 'whsec_' then
    raise exception using errcode = '22023', message = 'invalid or secret-bearing verifier key version reference';
  end if;

  if p_admission_mac is null or p_admission_mac !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '28000', message = 'dedicated ingress admission proof is invalid';
  end if;

  select s.decrypted_secret
    into v_admission_key
  from vault.decrypted_secrets s
  where s.name = 'dail_external_ingress_admission_hmac_key_v2'
  order by s.created_at desc
  limit 1;

  if v_admission_key is null or length(v_admission_key) < 32 then
    raise exception using
      errcode = '55000',
      message = 'dedicated ingress admission verifier is not configured';
  end if;

  v_expected_admission_mac := encode(
    extensions.hmac(
      convert_to(
        'dail-external-ingress-v2|' || p_source_event_id || '|' ||
        p_raw_body_sha256 || '|' || p_signature_timestamp::text || '|' ||
        p_secret_version_ref,
        'UTF8'
      ),
      convert_to(v_admission_key, 'UTF8'),
      'sha256'
    ),
    'hex'
  );
  if v_expected_admission_mac <> p_admission_mac then
    raise exception using errcode = '28000', message = 'dedicated ingress admission proof is invalid';
  end if;

  if p_signature_tolerance_seconds <> 300
     or abs(extract(epoch from p_received_at)::bigint - p_signature_timestamp) > 300
     or abs(extract(epoch from clock_timestamp()) - extract(epoch from p_received_at)) > 300 then
    raise exception using errcode = '22023', message = 'external signature timestamp is outside the accepted 300 second window';
  end if;

  if p_pending_webhooks is not null and p_pending_webhooks not between 0 and 100000 then
    raise exception using errcode = '22023', message = 'invalid pending_webhooks value';
  end if;

  v_environment := case when p_livemode then 'live' else 'test' end;
  perform pg_advisory_xact_lock(
    hashtext('chlom_runtime.external-event.v2:' || p_provider || ':' || p_source_event_id)
  );

  select i.*
    into v_existing_ingress
  from chlom_runtime.external_ingress_receipts_v2 i
  where i.provider = p_provider
    and i.source_event_id = p_source_event_id;

  if found then
    if v_existing_ingress.raw_body_sha256 <> p_raw_body_sha256 then
      raise exception using
        errcode = '23505',
        message = 'provider event identifier was replayed with a different raw body';
    end if;

    select v.verification_receipt_id,
           d.event_id,
           d.event_hash,
           d.sequence_id
      into v_existing_verification_id,
           v_existing_event_id,
           v_existing_event_hash,
           v_existing_sequence_id
    from chlom_runtime.external_verification_receipts_v2 v
    join chlom_runtime.dail_events d
      on d.verification_receipt_id = v.verification_receipt_id
    where v.ingress_receipt_id = v_existing_ingress.ingress_receipt_id
    order by v.created_at, d.sequence_id
    limit 1;

    if not found then
      raise exception using
        errcode = '55000',
        message = 'existing external ingress receipt has no atomic DAIL verification projection';
    end if;

    return jsonb_build_object(
      'ok', true,
      'duplicate', true,
      'ingress_receipt_id', v_existing_ingress.ingress_receipt_id,
      'verification_receipt_id', v_existing_verification_id,
      'event_id', v_existing_event_id,
      'event_hash', v_existing_event_hash,
      'sequence_id', v_existing_sequence_id,
      'processing_state', 'already_queued'
    );
  end if;

  v_ingress_hash := encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
          'receipt_format', 'dail.external-ingress.v2',
          'canonicalization_version', 'ct-json-sort-v1',
          'ingress_receipt_id', v_ingress_id,
          'provider', p_provider,
          'source_event_id', p_source_event_id,
          'provider_event_type', p_provider_event_type,
          'provider_account_ref', p_provider_account_ref,
          'environment', v_environment,
          'producer_trust_domain', p_producer_trust_domain,
          'raw_body_sha256', p_raw_body_sha256,
          'signature_header_sha256', p_signature_header_sha256,
          'signature_timestamp', p_signature_timestamp,
          'received_at', to_char(
            p_received_at at time zone 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
          ),
          'ingress_state', 'received',
          'created_at', to_char(
            v_ingress_created_at at time zone 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
          )
        )),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into chlom_runtime.external_ingress_receipts_v2 (
    ingress_receipt_id,
    provider,
    source_event_id,
    provider_event_type,
    provider_account_ref,
    environment,
    producer_trust_domain,
    raw_body_sha256,
    signature_header_sha256,
    signature_timestamp,
    received_at,
    ingress_state,
    receipt_sha256,
    created_at
  ) values (
    v_ingress_id,
    p_provider,
    p_source_event_id,
    p_provider_event_type,
    p_provider_account_ref,
    v_environment,
    p_producer_trust_domain,
    p_raw_body_sha256,
    p_signature_header_sha256,
    p_signature_timestamp,
    p_received_at,
    'received',
    v_ingress_hash,
    v_ingress_created_at
  );

  v_verified_at := clock_timestamp();
  v_verification_hash := encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
          'receipt_format', 'dail.external-verification.v2',
          'canonicalization_version', 'ct-json-sort-v1',
          'verification_receipt_id', v_verification_id,
          'ingress_receipt_id', v_ingress_id,
          'ingress_receipt_sha256', v_ingress_hash,
          'provider', p_provider,
          'verifier_id', p_verifier_id,
          'verifier_trust_domain', p_verifier_trust_domain,
          'producer_trust_domain', p_producer_trust_domain,
          'algorithm', 'hmac-sha256',
          'secret_version_ref', p_secret_version_ref,
          'signature_timestamp', p_signature_timestamp,
          'tolerance_seconds', p_signature_tolerance_seconds,
          'verifier_tool_version', p_verifier_tool_version,
          'verification_state', 'verified',
          'evidence_tier', 'E4_EXTERNAL_SYMMETRIC_VERIFIED',
          'provider_readback_state', 'not_performed',
          'provider_readback_receipt_ref', null,
          'signed_payload_sha256', p_signed_payload_sha256,
          'limitation', v_limitation,
          'verified_at', to_char(
            v_verified_at at time zone 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
          )
        )),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into chlom_runtime.external_verification_receipts_v2 (
    verification_receipt_id,
    ingress_receipt_id,
    provider,
    verifier_id,
    verifier_trust_domain,
    producer_trust_domain,
    algorithm,
    secret_version_ref,
    signature_timestamp,
    tolerance_seconds,
    verifier_tool_version,
    verification_state,
    evidence_tier,
    provider_readback_state,
    provider_readback_receipt_ref,
    signed_payload_sha256,
    receipt_sha256,
    limitation,
    verified_at,
    created_at
  ) values (
    v_verification_id,
    v_ingress_id,
    p_provider,
    p_verifier_id,
    p_verifier_trust_domain,
    p_producer_trust_domain,
    'hmac-sha256',
    p_secret_version_ref,
    p_signature_timestamp,
    p_signature_tolerance_seconds,
    p_verifier_tool_version,
    'verified',
    'E4_EXTERNAL_SYMMETRIC_VERIFIED',
    'not_performed',
    null,
    p_signed_payload_sha256,
    v_verification_hash,
    v_limitation,
    v_verified_at,
    v_verified_at
  );

  v_payload := jsonb_build_object(
    'provider', p_provider,
    'provider_event_id', p_source_event_id,
    'provider_event_type', p_provider_event_type,
    'provider_object', jsonb_build_object(
      'type', p_provider_object_type,
      'id', p_provider_object_id
    ),
    'api_version', p_api_version,
    'livemode', p_livemode,
    'pending_webhooks', p_pending_webhooks,
    'provider_request_ref', p_provider_request_ref,
    'provider_account_ref', p_provider_account_ref,
    'raw_body_sha256', p_raw_body_sha256,
    'ingress_receipt', jsonb_build_object(
      'id', v_ingress_id,
      'sha256', v_ingress_hash
    ),
    'verification_receipt', jsonb_build_object(
      'id', v_verification_id,
      'sha256', v_verification_hash,
      'algorithm', 'hmac-sha256',
      'evidence_tier', 'E4_EXTERNAL_SYMMETRIC_VERIFIED',
      'provider_readback_state', 'not_performed',
      'public_key_nonrepudiation', false,
      'externally_anchored', false
    )
  );

  v_dail := chlom_runtime.append_dail_event_v2(
    p_event_type => 'external.stripe.event.verified',
    p_entity_type => 'stripe_object:' || p_provider_object_type,
    p_entity_id => p_provider_object_id,
    p_source_system => p_provider,
    p_trust_domain => p_producer_trust_domain,
    p_evidence_class => 'E4_EXTERNAL_SYMMETRIC_VERIFIED',
    p_idempotency_key => 'stripe:' || encode(
      extensions.digest(
        convert_to(p_provider || chr(31) || p_source_event_id, 'UTF8'),
        'sha256'
      ),
      'hex'
    ),
    p_payload => v_payload,
    p_source_event_id => p_source_event_id,
    p_actor_ref => 'stripe:webhook',
    p_agent_id => p_verifier_id,
    p_entity_version => p_api_version,
    p_correlation_id => coalesce(p_provider_request_ref, p_source_event_id),
    p_authority_basis =>
      'Externally originated provider event with exact-body Stripe HMAC verification; no institutional authority expansion.',
    p_visibility_class => 'internal',
    p_verification_receipt_id => v_verification_id,
    p_payload_ref => 'dail-ingress-receipt:' || v_ingress_id::text,
    p_chain_anchor_state => 'unanchored',
    p_signature_ref => 'dail-verification-receipt:' || v_verification_id::text
  );

  v_processing_created_at := clock_timestamp();
  v_processing_hash := encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
          'receipt_format', 'dail.processing.v2',
          'canonicalization_version', 'ct-json-sort-v1',
          'processing_receipt_id', v_processing_id,
          'dail_event_id', v_dail->>'event_id',
          'dail_event_hash', v_dail->>'event_hash',
          'source_system', p_provider,
          'source_event_id', p_source_event_id,
          'consumer_id', 'ct.schedule.external-evidence-relay.hourly.v1',
          'processing_state', 'queued',
          'attempt_no', 1,
          'idempotency_key', p_provider || ':' || p_source_event_id || ':external-evidence-relay:v1',
          'created_at', to_char(
            v_processing_created_at at time zone 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
          )
        )),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into chlom_runtime.processing_receipts_v2 (
    processing_receipt_id,
    dail_event_id,
    dail_event_hash,
    source_system,
    source_event_id,
    consumer_id,
    processing_state,
    attempt_no,
    idempotency_key,
    receipt_sha256,
    created_at
  ) values (
    v_processing_id,
    (v_dail->>'event_id')::uuid,
    v_dail->>'event_hash',
    p_provider,
    p_source_event_id,
    'ct.schedule.external-evidence-relay.hourly.v1',
    'queued',
    1,
    p_provider || ':' || p_source_event_id || ':external-evidence-relay:v1',
    v_processing_hash,
    v_processing_created_at
  );

  return jsonb_build_object(
    'ok', true,
    'duplicate', false,
    'ingress_receipt_id', v_ingress_id,
    'ingress_receipt_sha256', v_ingress_hash,
    'verification_receipt_id', v_verification_id,
    'verification_receipt_sha256', v_verification_hash,
    'event_id', v_dail->>'event_id',
    'event_hash', v_dail->>'event_hash',
    'sequence_id', v_dail->'sequence_id',
    'processing_receipt_id', v_processing_id,
    'processing_state', 'queued',
    'chain_anchor_state', 'unanchored',
    'public_key_nonrepudiation', false
  );
end
$function$;

alter table chlom_runtime.dail_events
  add column if not exists chain_id text not null default 'ct.dail.global.v1',
  add column if not exists source_event_id text,
  add column if not exists trust_domain text,
  add column if not exists evidence_class text,
  add column if not exists idempotency_key text,
  add column if not exists verification_receipt_id uuid,
  add column if not exists correction_of_event_id uuid,
  add column if not exists supersedes_event_id uuid,
  add column if not exists payload_ref text;

do $column_shape$
begin
  if exists (
    select 1
    from information_schema.columns c
    join (
      values
        ('chain_id', 'text'),
        ('source_event_id', 'text'),
        ('trust_domain', 'text'),
        ('evidence_class', 'text'),
        ('idempotency_key', 'text'),
        ('verification_receipt_id', 'uuid'),
        ('correction_of_event_id', 'uuid'),
        ('supersedes_event_id', 'uuid'),
        ('payload_ref', 'text')
    ) as expected(column_name, udt_name)
      on expected.column_name = c.column_name
    where c.table_schema = 'chlom_runtime'
      and c.table_name = 'dail_events'
      and c.udt_name <> expected.udt_name
  ) then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 preflight failed: one or more additive columns have an incompatible type';
  end if;
end
$column_shape$;

alter table chlom_runtime.dail_events
  add constraint dail_events_v2_evidence_class_check
  check (
    evidence_class is null
    or evidence_class in (
      'E0_INTERNAL_ASSERTION',
      'E1_INTERNAL_HASHED',
      'E2_SEPARATE_WORKLOAD_VERIFIED',
      'E3_EXTERNAL_UNVERIFIED',
      'E4_EXTERNAL_SYMMETRIC_VERIFIED',
      'E5_EXTERNAL_ASYMMETRIC_ATTESTED',
      'E6_INDEPENDENTLY_ANCHORED'
    )
  ) not valid;

alter table chlom_runtime.dail_events
  add constraint dail_events_v2_required_shape_check
  check (
    schema_version <> '2.0.0'
    or (
      chain_id = 'ct.dail.global.v1'
      and actor_ref is not null
      and authority_basis is not null
      and correlation_id is not null
      and source_system is not null
      and trust_domain is not null
      and evidence_class is not null
      and idempotency_key is not null
    )
  ) not valid;

alter table chlom_runtime.dail_events
  validate constraint dail_events_v2_evidence_class_check,
  validate constraint dail_events_v2_required_shape_check;

create table chlom_runtime.external_ingress_receipts_v2 (
  ingress_receipt_id uuid primary key default gen_random_uuid(),
  provider text not null,
  source_event_id text not null,
  provider_event_type text not null,
  provider_account_ref text,
  environment text not null,
  producer_trust_domain text not null,
  raw_body_sha256 text not null,
  signature_header_sha256 text not null,
  signature_timestamp bigint not null,
  received_at timestamptz not null,
  ingress_state text not null default 'received',
  receipt_sha256 text not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint external_ingress_receipts_v2_provider_check
    check (provider ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
  constraint external_ingress_receipts_v2_source_event_id_check
    check (length(source_event_id) between 1 and 255),
  constraint external_ingress_receipts_v2_environment_check
    check (environment in ('test', 'live')),
  constraint external_ingress_receipts_v2_trust_domain_check
    check (length(producer_trust_domain) between 1 and 255),
  constraint external_ingress_receipts_v2_raw_body_hash_check
    check (raw_body_sha256 ~ '^[0-9a-f]{64}$'),
  constraint external_ingress_receipts_v2_signature_header_hash_check
    check (signature_header_sha256 ~ '^[0-9a-f]{64}$'),
  constraint external_ingress_receipts_v2_state_check
    check (ingress_state = 'received'),
  constraint external_ingress_receipts_v2_receipt_hash_check
    check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  constraint external_ingress_receipts_v2_provider_event_unique
    unique (provider, source_event_id),
  constraint external_ingress_receipts_v2_receipt_hash_unique
    unique (receipt_sha256)
);

create table chlom_runtime.external_verification_receipts_v2 (
  verification_receipt_id uuid primary key default gen_random_uuid(),
  ingress_receipt_id uuid not null
    references chlom_runtime.external_ingress_receipts_v2(ingress_receipt_id),
  provider text not null,
  verifier_id text not null,
  verifier_trust_domain text not null,
  producer_trust_domain text not null,
  algorithm text not null,
  secret_version_ref text not null,
  signature_timestamp bigint not null,
  tolerance_seconds integer not null,
  verifier_tool_version text not null,
  verification_state text not null,
  evidence_tier text not null,
  provider_readback_state text not null,
  provider_readback_receipt_ref text,
  signed_payload_sha256 text not null,
  receipt_sha256 text not null,
  limitation text not null,
  verified_at timestamptz not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint external_verification_receipts_v2_provider_check
    check (provider ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
  constraint external_verification_receipts_v2_separation_check
    check (verifier_trust_domain <> producer_trust_domain),
  constraint external_verification_receipts_v2_algorithm_check
    check (algorithm = 'hmac-sha256'),
  constraint external_verification_receipts_v2_secret_ref_check
    check (
      length(secret_version_ref) between 1 and 200
      and secret_version_ref !~* 'whsec_'
    ),
  constraint external_verification_receipts_v2_tolerance_check
    check (tolerance_seconds = 300),
  constraint external_verification_receipts_v2_state_check
    check (verification_state = 'verified'),
  constraint external_verification_receipts_v2_evidence_tier_check
    check (evidence_tier = 'E4_EXTERNAL_SYMMETRIC_VERIFIED'),
  constraint external_verification_receipts_v2_provider_readback_state_check
    check (provider_readback_state in ('not_performed', 'verified', 'failed')),
  constraint external_verification_receipts_v2_signed_payload_hash_check
    check (signed_payload_sha256 ~ '^[0-9a-f]{64}$'),
  constraint external_verification_receipts_v2_receipt_hash_check
    check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  constraint external_verification_receipts_v2_receipt_hash_unique
    unique (receipt_sha256)
);

create table chlom_runtime.external_anchor_receipts_v2 (
  anchor_receipt_id uuid primary key default gen_random_uuid(),
  dail_event_id uuid not null references chlom_runtime.dail_events(event_id),
  dail_event_hash text not null,
  anchor_provider text not null,
  anchor_trust_domain text not null,
  anchor_type text not null,
  external_anchor_ref text not null,
  anchor_artifact_sha256 text not null,
  anchor_state text not null,
  observed_at timestamptz not null,
  receipt_sha256 text not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint external_anchor_receipts_v2_event_hash_check
    check (dail_event_hash ~ '^[0-9a-f]{64}$'),
  constraint external_anchor_receipts_v2_artifact_hash_check
    check (anchor_artifact_sha256 ~ '^[0-9a-f]{64}$'),
  constraint external_anchor_receipts_v2_state_check
    check (anchor_state in ('candidate', 'verified', 'rejected', 'superseded')),
  constraint external_anchor_receipts_v2_receipt_hash_check
    check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  constraint external_anchor_receipts_v2_external_ref_unique
    unique (anchor_provider, external_anchor_ref),
  constraint external_anchor_receipts_v2_receipt_hash_unique
    unique (receipt_sha256)
);

create table chlom_runtime.processing_receipts_v2 (
  processing_receipt_id uuid primary key default gen_random_uuid(),
  dail_event_id uuid not null references chlom_runtime.dail_events(event_id),
  dail_event_hash text not null,
  source_system text not null,
  source_event_id text not null,
  consumer_id text not null,
  processing_state text not null,
  attempt_no integer not null default 1,
  predecessor_receipt_id uuid references chlom_runtime.processing_receipts_v2(processing_receipt_id),
  idempotency_key text not null,
  artifact_ref text,
  artifact_sha256 text,
  error_code text,
  error_detail_sha256 text,
  receipt_sha256 text not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint processing_receipts_v2_event_hash_check
    check (dail_event_hash ~ '^[0-9a-f]{64}$'),
  constraint processing_receipts_v2_state_check
    check (processing_state in ('queued', 'started', 'completed', 'failed', 'quarantined', 'superseded')),
  constraint processing_receipts_v2_attempt_check
    check (attempt_no > 0),
  constraint processing_receipts_v2_artifact_hash_check
    check (artifact_sha256 is null or artifact_sha256 ~ '^[0-9a-f]{64}$'),
  constraint processing_receipts_v2_error_hash_check
    check (error_detail_sha256 is null or error_detail_sha256 ~ '^[0-9a-f]{64}$'),
  constraint processing_receipts_v2_receipt_hash_check
    check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  constraint processing_receipts_v2_state_idempotency_unique
    unique (idempotency_key, attempt_no, processing_state),
  constraint processing_receipts_v2_receipt_hash_unique
    unique (receipt_sha256)
);

create table chlom_runtime.factory_continuation_receipts_v2 (
  continuation_receipt_id uuid primary key default gen_random_uuid(),
  dail_event_id uuid not null references chlom_runtime.dail_events(event_id),
  dail_event_hash text not null,
  contract_version text not null,
  schema_version text not null,
  canonicalization_version text not null,
  factory_id text not null,
  run_id text not null,
  request_id text not null,
  stream_id text not null,
  lane text not null,
  ordinal bigint not null,
  attempt integer not null,
  state text not null,
  checkpoint_id text not null,
  predecessor_checkpoint_id text,
  worker_id text not null,
  claim_id text not null,
  fencing_token bigint not null,
  lease_acquired_at timestamptz,
  lease_until timestamptz,
  available_at timestamptz,
  idempotency_key text not null,
  input_digest_sha256 text not null,
  output_digest_sha256 text,
  artifact_digest_sha256 text,
  compiler_version text not null,
  authority_ref text not null,
  correlation_id text,
  causation_id text,
  previous_event_hash text,
  event_hash text not null,
  provider_operation text,
  provider_idempotency_key text,
  provider_request_ref text,
  provider_request_digest text,
  provider_response_sha256 text,
  provider_readback_state text not null,
  provider_readback_receipt_ref text,
  readback_digest text,
  rollback_ref text,
  rollback_digest_sha256 text,
  error_class text,
  retry_count integer not null default 0,
  retryable boolean not null default false,
  next_retry_at timestamptz,
  security_state text not null,
  security_verifier_id text,
  security_receipt_ref text,
  security_receipt_sha256 text,
  test_state text not null,
  test_verifier_id text,
  test_receipt_ref text,
  test_receipt_sha256 text,
  next_action text not null,
  content_digest_sha256 text not null,
  started_at timestamptz,
  completed_at timestamptz,
  approval_id text,
  receipt_sha256 text not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint factory_continuation_receipts_v2_event_hash_check
    check (dail_event_hash ~ '^[0-9a-f]{64}$'),
  constraint factory_continuation_receipts_v2_contract_check
    check (
      contract_version = 'ct.factory-continuation.v2'
      and schema_version = '2.0.0'
      and canonicalization_version = 'ct-json-sort-v1'
    ),
  constraint factory_continuation_receipts_v2_ordinal_attempt_check
    check (ordinal >= 0 and attempt > 0 and fencing_token > 0),
  constraint factory_continuation_receipts_v2_state_check
    check (state in ('checkpointed', 'ready', 'running', 'held', 'failed', 'superseded')),
  constraint factory_continuation_receipts_v2_input_hash_check
    check (input_digest_sha256 ~ '^[0-9a-f]{64}$'),
  constraint factory_continuation_receipts_v2_output_hash_check
    check (output_digest_sha256 is null or output_digest_sha256 ~ '^[0-9a-f]{64}$'),
  constraint factory_continuation_receipts_v2_artifact_hash_check
    check (artifact_digest_sha256 is null or artifact_digest_sha256 ~ '^[0-9a-f]{64}$'),
  constraint factory_continuation_receipts_v2_receipt_chain_hash_check
    check (
      (previous_event_hash is null or previous_event_hash ~ '^[0-9a-f]{64}$')
      and event_hash ~ '^[0-9a-f]{64}$'
    ),
  constraint factory_continuation_receipts_v2_provider_hash_check
    check (
      (provider_request_digest is null or provider_request_digest ~ '^[0-9a-f]{64}$')
      and (provider_response_sha256 is null or provider_response_sha256 ~ '^[0-9a-f]{64}$')
      and (readback_digest is null or readback_digest ~ '^[0-9a-f]{64}$')
    ),
  constraint factory_continuation_receipts_v2_provider_readback_state_check
    check (provider_readback_state in ('not_applicable', 'not_performed', 'pass', 'fail')),
  constraint factory_continuation_receipts_v2_security_state_check
    check (security_state in ('not_run', 'pending', 'pass', 'fail', 'held')),
  constraint factory_continuation_receipts_v2_test_state_check
    check (test_state in ('not_run', 'pending', 'pass', 'fail', 'held')),
  constraint factory_continuation_receipts_v2_assurance_receipt_hash_check
    check (
      (security_receipt_sha256 is null or security_receipt_sha256 ~ '^[0-9a-f]{64}$')
      and (test_receipt_sha256 is null or test_receipt_sha256 ~ '^[0-9a-f]{64}$')
    ),
  constraint factory_continuation_receipts_v2_assurance_receipt_shape_check
    check (
      (
        security_state not in ('pass', 'fail', 'held')
        or (
          security_verifier_id is not null and security_receipt_ref is not null
          and security_receipt_sha256 is not null
        )
      )
      and (
        test_state not in ('pass', 'fail', 'held')
        or (
          test_verifier_id is not null and test_receipt_ref is not null
          and test_receipt_sha256 is not null
        )
      )
    ),
  constraint factory_continuation_receipts_v2_verifier_separation_check
    check (
      (security_state <> 'pass' or security_verifier_id <> worker_id)
      and (test_state <> 'pass' or test_verifier_id <> worker_id)
      and (
        security_state <> 'pass' or test_state <> 'pass'
        or security_verifier_id <> test_verifier_id
      )
    ),
  constraint factory_continuation_receipts_v2_provider_shape_check
    check (
      (
        provider_operation is null
        and provider_readback_state = 'not_applicable'
      )
      or (
        provider_operation is not null
        and provider_readback_state <> 'not_applicable'
        and provider_idempotency_key is not null
        and provider_request_ref is not null
        and provider_request_digest is not null
        and (
          provider_readback_state <> 'pass'
          or (
            provider_response_sha256 is not null
            and provider_readback_receipt_ref is not null
            and readback_digest is not null
          )
        )
      )
    ),
  constraint factory_continuation_receipts_v2_rollback_hash_check
    check (rollback_digest_sha256 is null or rollback_digest_sha256 ~ '^[0-9a-f]{64}$'),
  constraint factory_continuation_receipts_v2_content_hash_check
    check (content_digest_sha256 ~ '^[0-9a-f]{64}$'),
  constraint factory_continuation_receipts_v2_receipt_hash_check
    check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  constraint factory_continuation_receipts_v2_lease_window_check
    check (
      (lease_acquired_at is null and lease_until is null)
      or (
        lease_acquired_at is not null and lease_until is not null
        and lease_until > lease_acquired_at
      )
    ),
  constraint factory_continuation_receipts_v2_completion_window_check
    check (
      started_at is null
      or completed_at is null
      or completed_at >= started_at
    ),
  constraint factory_continuation_receipts_v2_retry_shape_check
    check (
      retry_count >= 0
      and (
        (retryable and next_retry_at is not null)
        or (not retryable and next_retry_at is null)
      )
    ),
  constraint factory_continuation_receipts_v2_checkpoint_unique
    unique (factory_id, run_id, checkpoint_id),
  constraint factory_continuation_receipts_v2_idempotency_unique
    unique (factory_id, idempotency_key),
  constraint factory_continuation_receipts_v2_lane_ordinal_attempt_unique
    unique (factory_id, run_id, stream_id, lane, ordinal, attempt),
  constraint factory_continuation_receipts_v2_event_hash_unique
    unique (event_hash),
  constraint factory_continuation_receipts_v2_receipt_hash_unique
    unique (receipt_sha256)
);

alter table chlom_runtime.dail_events
  add constraint dail_events_v2_verification_receipt_fkey
    foreign key (verification_receipt_id)
    references chlom_runtime.external_verification_receipts_v2(verification_receipt_id)
    not valid,
  add constraint dail_events_v2_correction_event_fkey
    foreign key (correction_of_event_id)
    references chlom_runtime.dail_events(event_id)
    not valid,
  add constraint dail_events_v2_supersedes_event_fkey
    foreign key (supersedes_event_id)
    references chlom_runtime.dail_events(event_id)
    not valid;

alter table chlom_runtime.dail_events
  validate constraint dail_events_v2_verification_receipt_fkey,
  validate constraint dail_events_v2_correction_event_fkey,
  validate constraint dail_events_v2_supersedes_event_fkey;

create unique index dail_events_v2_source_event_unique
  on chlom_runtime.dail_events(source_system, source_event_id)
  where source_event_id is not null;

create unique index dail_events_v2_idempotency_unique
  on chlom_runtime.dail_events(source_system, idempotency_key)
  where idempotency_key is not null;

create unique index dail_events_v2_verification_receipt_unique
  on chlom_runtime.dail_events(verification_receipt_id)
  where verification_receipt_id is not null;

create index external_verification_receipts_v2_ingress_idx
  on chlom_runtime.external_verification_receipts_v2(ingress_receipt_id);

create index external_anchor_receipts_v2_event_idx
  on chlom_runtime.external_anchor_receipts_v2(dail_event_id, observed_at desc);

create index processing_receipts_v2_event_idx
  on chlom_runtime.processing_receipts_v2(dail_event_id, created_at desc);

create index factory_continuation_receipts_v2_event_idx
  on chlom_runtime.factory_continuation_receipts_v2(dail_event_id, created_at desc);

alter table chlom_runtime.dail_events enable row level security;
alter table chlom_runtime.dail_events force row level security;
alter table chlom_runtime.dail_integrity_corrections enable row level security;
alter table chlom_runtime.dail_integrity_corrections force row level security;
alter table chlom_runtime.external_ingress_receipts_v2 enable row level security;
alter table chlom_runtime.external_ingress_receipts_v2 force row level security;
alter table chlom_runtime.external_verification_receipts_v2 enable row level security;
alter table chlom_runtime.external_verification_receipts_v2 force row level security;
alter table chlom_runtime.external_anchor_receipts_v2 enable row level security;
alter table chlom_runtime.external_anchor_receipts_v2 force row level security;
alter table chlom_runtime.processing_receipts_v2 enable row level security;
alter table chlom_runtime.processing_receipts_v2 force row level security;
alter table chlom_runtime.factory_continuation_receipts_v2 enable row level security;
alter table chlom_runtime.factory_continuation_receipts_v2 force row level security;

revoke all on table chlom_runtime.dail_events from public, anon, authenticated, service_role;
revoke all on table chlom_runtime.dail_integrity_corrections from public, anon, authenticated, service_role;
revoke all on table chlom_runtime.external_ingress_receipts_v2 from public, anon, authenticated, service_role;
revoke all on table chlom_runtime.external_verification_receipts_v2 from public, anon, authenticated, service_role;
revoke all on table chlom_runtime.external_anchor_receipts_v2 from public, anon, authenticated, service_role;
revoke all on table chlom_runtime.processing_receipts_v2 from public, anon, authenticated, service_role;
revoke all on table chlom_runtime.factory_continuation_receipts_v2 from public, anon, authenticated, service_role;

drop trigger if exists trg_dail_events_v2_reject_update_delete on chlom_runtime.dail_events;
create trigger trg_dail_events_v2_reject_update_delete
before update or delete on chlom_runtime.dail_events
for each row execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_dail_events_v2_reject_truncate on chlom_runtime.dail_events;
create trigger trg_dail_events_v2_reject_truncate
before truncate on chlom_runtime.dail_events
for each statement execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_dail_integrity_corrections_v2_reject_truncate on chlom_runtime.dail_integrity_corrections;
create trigger trg_dail_integrity_corrections_v2_reject_truncate
before truncate on chlom_runtime.dail_integrity_corrections
for each statement execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_dail_integrity_corrections_v2_reject_update_delete on chlom_runtime.dail_integrity_corrections;
create trigger trg_dail_integrity_corrections_v2_reject_update_delete
before update or delete on chlom_runtime.dail_integrity_corrections
for each row execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_external_ingress_receipts_v2_reject_update_delete on chlom_runtime.external_ingress_receipts_v2;
create trigger trg_external_ingress_receipts_v2_reject_update_delete
before update or delete on chlom_runtime.external_ingress_receipts_v2
for each row execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_external_ingress_receipts_v2_reject_truncate on chlom_runtime.external_ingress_receipts_v2;
create trigger trg_external_ingress_receipts_v2_reject_truncate
before truncate on chlom_runtime.external_ingress_receipts_v2
for each statement execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_external_verification_receipts_v2_reject_update_delete on chlom_runtime.external_verification_receipts_v2;
create trigger trg_external_verification_receipts_v2_reject_update_delete
before update or delete on chlom_runtime.external_verification_receipts_v2
for each row execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_external_verification_receipts_v2_reject_truncate on chlom_runtime.external_verification_receipts_v2;
create trigger trg_external_verification_receipts_v2_reject_truncate
before truncate on chlom_runtime.external_verification_receipts_v2
for each statement execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_external_anchor_receipts_v2_reject_update_delete on chlom_runtime.external_anchor_receipts_v2;
create trigger trg_external_anchor_receipts_v2_reject_update_delete
before update or delete on chlom_runtime.external_anchor_receipts_v2
for each row execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_external_anchor_receipts_v2_reject_truncate on chlom_runtime.external_anchor_receipts_v2;
create trigger trg_external_anchor_receipts_v2_reject_truncate
before truncate on chlom_runtime.external_anchor_receipts_v2
for each statement execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_processing_receipts_v2_reject_update_delete on chlom_runtime.processing_receipts_v2;
create trigger trg_processing_receipts_v2_reject_update_delete
before update or delete on chlom_runtime.processing_receipts_v2
for each row execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_processing_receipts_v2_reject_truncate on chlom_runtime.processing_receipts_v2;
create trigger trg_processing_receipts_v2_reject_truncate
before truncate on chlom_runtime.processing_receipts_v2
for each statement execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_factory_continuation_receipts_v2_reject_update_delete on chlom_runtime.factory_continuation_receipts_v2;
create trigger trg_factory_continuation_receipts_v2_reject_update_delete
before update or delete on chlom_runtime.factory_continuation_receipts_v2
for each row execute function chlom_runtime.reject_append_only_mutation_v2();

drop trigger if exists trg_factory_continuation_receipts_v2_reject_truncate on chlom_runtime.factory_continuation_receipts_v2;
create trigger trg_factory_continuation_receipts_v2_reject_truncate
before truncate on chlom_runtime.factory_continuation_receipts_v2
for each statement execute function chlom_runtime.reject_append_only_mutation_v2();

create or replace function chlom_runtime.enforce_factory_fencing_v2()
returns trigger
language plpgsql
security definer
set search_path = 'pg_catalog', 'chlom_runtime'
as $function$
declare
  v_latest record;
begin
  perform pg_advisory_xact_lock(
    hashtext(
      'chlom_runtime.factory-fence.v2:' || new.factory_id || ':' ||
      new.stream_id || ':' || new.lane
    )
  );

  select r.ordinal, r.attempt, r.fencing_token, r.checkpoint_id, r.event_hash
    into v_latest
  from chlom_runtime.factory_continuation_receipts_v2 r
  where r.factory_id = new.factory_id
    and r.stream_id = new.stream_id
    and r.lane = new.lane
  order by r.ordinal desc, r.attempt desc, r.created_at desc
  limit 1;

  if found then
    if new.fencing_token <> v_latest.fencing_token + 1 then
      raise exception using
        errcode = '55000',
        message = 'factory fencing token must advance exactly once from the latest checkpoint';
    end if;
    if new.previous_event_hash is distinct from v_latest.event_hash
       or new.predecessor_checkpoint_id is distinct from v_latest.checkpoint_id then
      raise exception using
        errcode = '55000',
        message = 'factory continuation predecessor does not match the latest checkpoint';
    end if;
    if not (
      (
        new.ordinal = v_latest.ordinal
        and new.attempt = v_latest.attempt + 1
      ) or (
        new.ordinal = v_latest.ordinal + 1
        and new.attempt = 1
      )
    ) then
      raise exception using
        errcode = '55000',
        message = 'factory continuation ordinal/attempt progression would fork or skip the stream';
    end if;
  elsif new.attempt <> 1 or new.fencing_token <> 1 or new.previous_event_hash is not null
        or new.predecessor_checkpoint_id is not null then
    raise exception using
      errcode = '55000',
      message = 'factory continuation genesis must use attempt one and no predecessor';
  end if;

  return new;
end
$function$;

drop trigger if exists trg_factory_continuation_receipts_v2_fencing on chlom_runtime.factory_continuation_receipts_v2;
create trigger trg_factory_continuation_receipts_v2_fencing
before insert on chlom_runtime.factory_continuation_receipts_v2
for each row execute function chlom_runtime.enforce_factory_fencing_v2();

-- ct-json-sort-v1 is deliberately narrow and deterministic: object keys use C
-- collation, separators are compact, arrays retain ordinal order, and JSON scalar
-- spellings come from jsonb. It matches sort_keys/compact UTF-8 JSON for the
-- string/integer/boolean/null envelopes used by DAIL v2.
-- Vector: {"a":[true,null,"é"],"b":2} -> {"a":[true,null,"é"],"b":2}
create or replace function chlom_runtime.canonical_jsonb_v1(p_value jsonb)
returns text
language plpgsql
immutable
strict
security invoker
set search_path = 'pg_catalog', 'chlom_runtime'
as $function$
declare
  v_type text := jsonb_typeof(p_value);
  v_result text;
begin
  if v_type = 'object' then
    select '{' || coalesce(
      string_agg(
        to_jsonb(e.key)::text || ':' || chlom_runtime.canonical_jsonb_v1(e.value),
        ',' order by e.key collate "C"
      ),
      ''
    ) || '}'
      into v_result
    from jsonb_each(p_value) as e(key, value);
    return v_result;
  elsif v_type = 'array' then
    select '[' || coalesce(
      string_agg(
        chlom_runtime.canonical_jsonb_v1(e.value),
        ',' order by e.ordinality
      ),
      ''
    ) || ']'
      into v_result
    from jsonb_array_elements(p_value) with ordinality as e(value, ordinality);
    return v_result;
  end if;

  return p_value::text;
end
$function$;

create or replace function chlom_runtime.jsonb_uses_portable_numbers_v1(p_value jsonb)
returns boolean
language plpgsql
immutable
strict
security invoker
set search_path = 'pg_catalog', 'chlom_runtime'
as $function$
declare
  v_type text := jsonb_typeof(p_value);
  v_ok boolean;
begin
  if v_type = 'number' then
    return p_value::text ~ '^-?(0|[1-9][0-9]*)$';
  elsif v_type = 'object' then
    select coalesce(bool_and(chlom_runtime.jsonb_uses_portable_numbers_v1(e.value)), true)
      into v_ok
    from jsonb_each(p_value) as e(key, value);
    return v_ok;
  elsif v_type = 'array' then
    select coalesce(bool_and(chlom_runtime.jsonb_uses_portable_numbers_v1(e.value)), true)
      into v_ok
    from jsonb_array_elements(p_value) as e(value);
    return v_ok;
  end if;
  return true;
end
$function$;

create or replace function chlom_runtime.dail_event_v2_preimage(
  p_chain_id text,
  p_sequence_id bigint,
  p_previous_event_hash text,
  p_event_id uuid,
  p_schema_version text,
  p_event_type text,
  p_actor_ref text,
  p_actor_did text,
  p_agent_id text,
  p_source_system text,
  p_source_event_id text,
  p_trust_domain text,
  p_evidence_class text,
  p_idempotency_key text,
  p_verification_receipt_id uuid,
  p_entity_type text,
  p_entity_id text,
  p_entity_version text,
  p_correlation_id text,
  p_causation_id text,
  p_authority_basis text,
  p_approval_id text,
  p_visibility_class text,
  p_payload_sha256 text,
  p_payload_ref text,
  p_correction_of_event_id uuid,
  p_supersedes_event_id uuid,
  p_chain_anchor_state text,
  p_signature_ref text,
  p_created_at_canonical text
)
returns jsonb
language sql
immutable
security invoker
set search_path = 'pg_catalog', 'chlom_runtime'
as $function$
  select jsonb_build_object(
    'preimage_format', 'dail.event.v2.canonical-jsonb',
    'canonicalization_version', 'ct-json-sort-v1',
    'chain_id', p_chain_id,
    'sequence_id', p_sequence_id,
    'previous_event_hash', p_previous_event_hash,
    'event_id', p_event_id,
    'schema_version', p_schema_version,
    'event_type', p_event_type,
    'actor_ref', p_actor_ref,
    'actor_did', p_actor_did,
    'agent_id', p_agent_id,
    'source_system', p_source_system,
    'source_event_id', p_source_event_id,
    'trust_domain', p_trust_domain,
    'evidence_class', p_evidence_class,
    'idempotency_key', p_idempotency_key,
    'verification_receipt_id', p_verification_receipt_id,
    'entity_type', p_entity_type,
    'entity_id', p_entity_id,
    'entity_version', p_entity_version,
    'correlation_id', p_correlation_id,
    'causation_id', p_causation_id,
    'authority_basis', p_authority_basis,
    'approval_id', p_approval_id,
    'visibility_class', p_visibility_class,
    'payload_sha256', p_payload_sha256,
    'payload_ref', p_payload_ref,
    'correction_of_event_id', p_correction_of_event_id,
    'supersedes_event_id', p_supersedes_event_id,
    'chain_anchor_state', p_chain_anchor_state,
    'signature_ref', p_signature_ref,
    'created_at', p_created_at_canonical
  )
$function$;

create or replace function chlom_runtime.append_dail_event_v2(
  p_event_type text,
  p_entity_type text,
  p_entity_id text,
  p_source_system text,
  p_trust_domain text,
  p_evidence_class text,
  p_idempotency_key text,
  p_payload jsonb default '{}'::jsonb,
  p_source_event_id text default null,
  p_actor_ref text default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_entity_version text default null,
  p_correlation_id text default null,
  p_causation_id text default null,
  p_authority_basis text default null,
  p_approval_id text default null,
  p_visibility_class text default 'internal',
  p_verification_receipt_id uuid default null,
  p_payload_ref text default null,
  p_correction_of_event_id uuid default null,
  p_supersedes_event_id uuid default null,
  p_chain_id text default 'ct.dail.global.v1',
  p_chain_anchor_state text default 'unanchored',
  p_signature_ref text default null
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog', 'extensions', 'chlom_runtime'
set "TimeZone" = 'UTC'
as $function$
declare
  v_schema_version constant text := '2.0.0';
  v_event_id uuid := gen_random_uuid();
  v_sequence_id bigint;
  v_previous_event_hash text;
  v_payload_sha256 text;
  v_event_hash text;
  v_created_at timestamptz := clock_timestamp();
  v_created_at_canonical text;
  v_preimage jsonb;
  v_existing chlom_runtime.dail_events%rowtype;
  v_verification chlom_runtime.external_verification_receipts_v2%rowtype;
  v_ingress chlom_runtime.external_ingress_receipts_v2%rowtype;
begin
  if p_chain_id <> 'ct.dail.global.v1' then
    raise exception using
      errcode = '22023',
      message = 'unsupported DAIL chain_id';
  end if;

  if p_event_type is null
     or p_event_type !~ '^[a-z0-9]+([._-][a-z0-9]+)+$'
     or length(p_event_type) > 160
     or p_entity_type is null
     or p_entity_type !~ '^[a-z0-9][a-z0-9._:-]{0,127}$'
     or p_entity_id is null or length(p_entity_id) not between 1 and 255
     or p_source_system is null or p_source_system !~ '^[a-z0-9][a-z0-9._:-]{0,127}$'
     or p_trust_domain is null or p_trust_domain !~ '^[a-z0-9][a-z0-9._:-]{0,127}$'
     or p_evidence_class is null or length(p_evidence_class) not between 1 and 128
     or p_idempotency_key is null or length(p_idempotency_key) not between 8 and 255
     or p_actor_ref is null or length(p_actor_ref) not between 1 and 255
     or p_authority_basis is null or length(p_authority_basis) not between 1 and 255
     or p_correlation_id is null or length(p_correlation_id) not between 1 and 255
     or (p_payload_ref is not null and length(p_payload_ref) > 2048)
     or (p_signature_ref is not null and length(p_signature_ref) > 2048) then
    raise exception using
      errcode = '22023',
      message = 'invalid required DAIL v2 identity or provenance field';
  end if;

  if p_evidence_class not in (
    'E0_INTERNAL_ASSERTION',
    'E1_INTERNAL_HASHED',
    'E2_SEPARATE_WORKLOAD_VERIFIED',
    'E3_EXTERNAL_UNVERIFIED',
    'E4_EXTERNAL_SYMMETRIC_VERIFIED',
    'E5_EXTERNAL_ASYMMETRIC_ATTESTED',
    'E6_INDEPENDENTLY_ANCHORED'
  ) then
    raise exception using errcode = '22023', message = 'unsupported DAIL evidence class';
  end if;

  if p_evidence_class in (
    'E2_SEPARATE_WORKLOAD_VERIFIED',
    'E5_EXTERNAL_ASYMMETRIC_ATTESTED',
    'E6_INDEPENDENTLY_ANCHORED'
  ) then
    raise exception using
      errcode = '0A000',
      message = 'E2/E5/E6 admission requires a dedicated authenticated verifier that is not deployed by this migration';
  end if;

  if p_source_event_id is not null and length(p_source_event_id) not between 1 and 255 then
    raise exception using
      errcode = '22023',
      message = 'invalid DAIL v2 source_event_id';
  end if;

  if p_visibility_class not in ('public', 'internal', 'confidential', 'restricted', 'sealed') then
    raise exception using errcode = '22023', message = 'invalid DAIL visibility class';
  end if;

  if p_chain_anchor_state <> 'unanchored' then
    raise exception using
      errcode = '0A000',
      message = 'generic DAIL admission cannot assert an anchor state; independent write/readback admission is required';
  end if;

  if p_signature_ref ~* 'whsec_' or p_payload_ref ~* 'whsec_' then
    raise exception using errcode = '22023', message = 'secret material is forbidden in DAIL references';
  end if;

  if not chlom_runtime.jsonb_uses_portable_numbers_v1(coalesce(p_payload, '{}'::jsonb)) then
    raise exception using
      errcode = '22023',
      message = 'DAIL v2 payload numbers must use the portable integer-only canonical JSON dialect';
  end if;

  v_payload_sha256 := encode(
    extensions.digest(
      convert_to(
        chlom_runtime.canonical_jsonb_v1(coalesce(p_payload, '{}'::jsonb)),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  perform pg_advisory_xact_lock(hashtext('chlom_runtime.dail.global.v1'));

  select d.*
    into v_existing
  from chlom_runtime.dail_events d
  where d.source_system = p_source_system
    and d.idempotency_key = p_idempotency_key
  order by d.sequence_id
  limit 1;

  if found then
    if v_existing.schema_version = v_schema_version
       and v_existing.event_type = p_event_type
       and v_existing.actor_ref is not distinct from p_actor_ref
       and v_existing.actor_did is not distinct from p_actor_did
       and v_existing.agent_id is not distinct from p_agent_id
       and v_existing.entity_type = p_entity_type
       and v_existing.entity_id = p_entity_id
       and v_existing.entity_version is not distinct from p_entity_version
       and v_existing.source_event_id is not distinct from p_source_event_id
       and v_existing.trust_domain = p_trust_domain
       and v_existing.evidence_class = p_evidence_class
       and v_existing.correlation_id is not distinct from p_correlation_id
       and v_existing.causation_id is not distinct from p_causation_id
       and v_existing.authority_basis is not distinct from p_authority_basis
       and v_existing.approval_id is not distinct from p_approval_id
       and v_existing.visibility_class = p_visibility_class
       and v_existing.verification_receipt_id is not distinct from p_verification_receipt_id
       and v_existing.payload_sha256 = v_payload_sha256
       and v_existing.payload_ref is not distinct from p_payload_ref
       and v_existing.correction_of_event_id is not distinct from p_correction_of_event_id
       and v_existing.supersedes_event_id is not distinct from p_supersedes_event_id
       and v_existing.chain_id = p_chain_id
       and v_existing.chain_anchor_state = p_chain_anchor_state
       and v_existing.signature_ref is not distinct from p_signature_ref then
      return jsonb_build_object(
        'duplicate', true,
        'sequence_id', v_existing.sequence_id,
        'event_id', v_existing.event_id,
        'event_hash', v_existing.event_hash,
        'previous_event_hash', v_existing.previous_event_hash,
        'schema_version', v_existing.schema_version,
        'chain_id', v_existing.chain_id,
        'created_at', v_existing.created_at
      );
    end if;

    raise exception using
      errcode = '23505',
      message = 'DAIL v2 idempotency conflict';
  end if;

  if p_source_event_id is not null then
    select d.*
      into v_existing
    from chlom_runtime.dail_events d
    where d.source_system = p_source_system
      and d.source_event_id = p_source_event_id
    order by d.sequence_id
    limit 1;

    if found then
      raise exception using
        errcode = '23505',
        message = 'DAIL v2 source event conflict';
    end if;
  end if;

  if p_verification_receipt_id is not null then
    select r.*
      into v_verification
    from chlom_runtime.external_verification_receipts_v2 r
    where r.verification_receipt_id = p_verification_receipt_id;

    if not found
       or v_verification.verification_state <> 'verified'
       or v_verification.provider <> p_source_system
       or v_verification.producer_trust_domain <> p_trust_domain
       or v_verification.evidence_tier <> p_evidence_class then
      raise exception using
        errcode = '23503',
        message = 'DAIL v2 verification receipt does not support the claimed provenance';
    end if;

    select i.*
      into v_ingress
    from chlom_runtime.external_ingress_receipts_v2 i
    where i.ingress_receipt_id = v_verification.ingress_receipt_id;

    if not found
       or p_evidence_class <> 'E4_EXTERNAL_SYMMETRIC_VERIFIED'
       or p_source_event_id is null
       or v_ingress.provider <> p_source_system
       or v_ingress.source_event_id <> p_source_event_id
       or p_payload->>'raw_body_sha256' is distinct from v_ingress.raw_body_sha256
       or p_payload->'ingress_receipt'->>'id' is distinct from v_ingress.ingress_receipt_id::text
       or p_payload->'ingress_receipt'->>'sha256' is distinct from v_ingress.receipt_sha256
       or p_payload->'verification_receipt'->>'id' is distinct from v_verification.verification_receipt_id::text
       or p_payload->'verification_receipt'->>'sha256' is distinct from v_verification.receipt_sha256 then
      raise exception using
        errcode = '23503',
        message = 'DAIL v2 external verification receipt is not bound to this exact ingress projection';
    end if;
  elsif p_evidence_class = 'E4_EXTERNAL_SYMMETRIC_VERIFIED' then
    raise exception using
      errcode = '23502',
      message = 'transactional provider HMAC evidence requires a verification receipt';
  end if;

  select d.event_hash
    into v_previous_event_hash
  from chlom_runtime.dail_events d
  order by d.sequence_id desc
  limit 1;

  v_sequence_id := nextval(
    pg_get_serial_sequence('chlom_runtime.dail_events', 'sequence_id')::regclass
  );
  v_created_at_canonical := to_char(
    v_created_at at time zone 'UTC',
    'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
  );

  v_preimage := chlom_runtime.dail_event_v2_preimage(
    p_chain_id,
    v_sequence_id,
    v_previous_event_hash,
    v_event_id,
    v_schema_version,
    p_event_type,
    p_actor_ref,
    p_actor_did,
    p_agent_id,
    p_source_system,
    p_source_event_id,
    p_trust_domain,
    p_evidence_class,
    p_idempotency_key,
    p_verification_receipt_id,
    p_entity_type,
    p_entity_id,
    p_entity_version,
    p_correlation_id,
    p_causation_id,
    p_authority_basis,
    p_approval_id,
    p_visibility_class,
    v_payload_sha256,
    p_payload_ref,
    p_correction_of_event_id,
    p_supersedes_event_id,
    p_chain_anchor_state,
    p_signature_ref,
    v_created_at_canonical
  );
  v_event_hash := encode(
    extensions.digest(
      convert_to(chlom_runtime.canonical_jsonb_v1(v_preimage), 'UTF8'),
      'sha256'
    ),
    'hex'
  );

  insert into chlom_runtime.dail_events (
    sequence_id,
    event_id,
    event_type,
    schema_version,
    actor_ref,
    actor_did,
    agent_id,
    source_system,
    source_event_id,
    trust_domain,
    evidence_class,
    idempotency_key,
    verification_receipt_id,
    chain_id,
    entity_type,
    entity_id,
    entity_version,
    correlation_id,
    causation_id,
    authority_basis,
    approval_id,
    visibility_class,
    payload,
    payload_sha256,
    payload_ref,
    correction_of_event_id,
    supersedes_event_id,
    previous_event_hash,
    event_hash,
    chain_anchor_state,
    signature_ref,
    created_at
  ) overriding system value
  values (
    v_sequence_id,
    v_event_id,
    p_event_type,
    v_schema_version,
    p_actor_ref,
    p_actor_did,
    p_agent_id,
    p_source_system,
    p_source_event_id,
    p_trust_domain,
    p_evidence_class,
    p_idempotency_key,
    p_verification_receipt_id,
    p_chain_id,
    p_entity_type,
    p_entity_id,
    p_entity_version,
    p_correlation_id,
    p_causation_id,
    p_authority_basis,
    p_approval_id,
    p_visibility_class,
    coalesce(p_payload, '{}'::jsonb),
    v_payload_sha256,
    p_payload_ref,
    p_correction_of_event_id,
    p_supersedes_event_id,
    v_previous_event_hash,
    v_event_hash,
    p_chain_anchor_state,
    p_signature_ref,
    v_created_at
  );

  return jsonb_build_object(
    'duplicate', false,
    'sequence_id', v_sequence_id,
    'event_id', v_event_id,
    'event_hash', v_event_hash,
    'previous_event_hash', v_previous_event_hash,
    'schema_version', v_schema_version,
    'chain_id', p_chain_id,
    'payload_sha256', v_payload_sha256,
    'canonical_created_at', v_created_at_canonical,
    'created_at', v_created_at
  );
end
$function$;

create or replace function chlom_runtime.verify_dail_chain()
returns jsonb
language plpgsql
stable
security definer
set search_path = 'pg_catalog', 'extensions', 'chlom_runtime'
set "TimeZone" = 'UTC'
set "DateStyle" = 'ISO, MDY'
as $function$
declare
  r record;
  c record;
  v_verification record;
  v_ingress record;
  v_previous_event_hash text := null;
  v_expected_payload_sha256 text;
  v_expected_event_hash text;
  v_expected_ingress_hash text;
  v_expected_verification_hash text;
  v_created_at_canonical text;
  v_preimage jsonb;
  v_checked bigint := 0;
  v_external_checked bigint := 0;
  v_failures jsonb := '[]'::jsonb;
  v_provenance_failures jsonb := '[]'::jsonb;
  v_corrected jsonb := '[]'::jsonb;
  v_correction_ok boolean;
  v_schema_supported boolean;
  v_verification_found boolean;
  v_ingress_found boolean;
begin
  for r in
    select *
    from chlom_runtime.dail_events
    order by sequence_id
  loop
    v_checked := v_checked + 1;
    v_schema_supported := true;
    v_expected_event_hash := null;
    if coalesce(r.schema_version, '1.0.0') = '2.0.0' then
      v_expected_payload_sha256 := encode(
        extensions.digest(
          convert_to(
            chlom_runtime.canonical_jsonb_v1(coalesce(r.payload, '{}'::jsonb)),
            'UTF8'
          ),
          'sha256'
        ),
        'hex'
      );
    else
      -- Historic v1/v1.1 payload digests intentionally retain PostgreSQL jsonb
      -- text semantics; changing them would rewrite the inherited chain.
      v_expected_payload_sha256 := encode(
        extensions.digest(
          convert_to(coalesce(r.payload, '{}'::jsonb)::text, 'UTF8'),
          'sha256'
        ),
        'hex'
      );
    end if;

    if coalesce(r.schema_version, '1.0.0') = '2.0.0' then
      v_created_at_canonical := to_char(
        r.created_at at time zone 'UTC',
        'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
      );
      v_preimage := chlom_runtime.dail_event_v2_preimage(
        r.chain_id,
        r.sequence_id,
        r.previous_event_hash,
        r.event_id,
        r.schema_version,
        r.event_type,
        r.actor_ref,
        r.actor_did,
        r.agent_id,
        r.source_system,
        r.source_event_id,
        r.trust_domain,
        r.evidence_class,
        r.idempotency_key,
        r.verification_receipt_id,
        r.entity_type,
        r.entity_id,
        r.entity_version,
        r.correlation_id,
        r.causation_id,
        r.authority_basis,
        r.approval_id,
        r.visibility_class,
        v_expected_payload_sha256,
        r.payload_ref,
        r.correction_of_event_id,
        r.supersedes_event_id,
        r.chain_anchor_state,
        r.signature_ref,
        v_created_at_canonical
      );
      v_expected_event_hash := encode(
        extensions.digest(
          convert_to(chlom_runtime.canonical_jsonb_v1(v_preimage), 'UTF8'),
          'sha256'
        ),
        'hex'
      );
    elsif coalesce(r.schema_version, '1.0.0') = '1.1.0' then
      v_created_at_canonical := to_char(
        r.created_at at time zone 'UTC',
        'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
      );
      v_expected_event_hash := encode(
        extensions.digest(
          convert_to(
            coalesce(v_previous_event_hash, 'GENESIS') || '|' ||
            r.event_id::text || '|' || r.schema_version || '|' || r.event_type || '|' ||
            r.entity_type || '|' || r.entity_id || '|' || coalesce(r.entity_version, '') || '|' ||
            coalesce(r.actor_did, r.actor_ref, '') || '|' || v_expected_payload_sha256 || '|' ||
            v_created_at_canonical,
            'UTF8'
          ),
          'sha256'
        ),
        'hex'
      );
    elsif coalesce(r.schema_version, '1.0.0') = '1.0.0' then
      v_expected_event_hash := encode(
        extensions.digest(
          convert_to(
            coalesce(v_previous_event_hash, 'GENESIS') || '|' ||
            r.event_id::text || '|' || r.event_type || '|' ||
            r.entity_type || '|' || r.entity_id || '|' || coalesce(r.entity_version, '') || '|' ||
            coalesce(r.actor_did, r.actor_ref, '') || '|' || v_expected_payload_sha256 || '|' ||
            r.created_at::text,
            'UTF8'
          ),
          'sha256'
        ),
        'hex'
      );
    else
      v_schema_supported := false;
    end if;

    v_correction_ok := false;
    if coalesce(r.schema_version, '1.0.0') in ('1.0.0', '1.1.0')
       and v_schema_supported
       and r.payload_sha256 is not distinct from v_expected_payload_sha256
       and r.previous_event_hash is not distinct from v_previous_event_hash
       and r.event_hash is distinct from v_expected_event_hash then
      select dic.*
        into c
      from chlom_runtime.dail_integrity_corrections dic
      where dic.event_id = r.event_id
        and dic.sequence_id = r.sequence_id
        and dic.original_event_hash = r.event_hash
        and dic.expected_event_hash = v_expected_event_hash
        and dic.payload_sha256 = v_expected_payload_sha256
        and dic.previous_event_hash is not distinct from v_previous_event_hash
        and dic.correction_state = 'accepted'
      order by dic.created_at desc
      limit 1;

      if found then
        v_correction_ok := true;
        v_corrected := v_corrected || jsonb_build_array(jsonb_build_object(
          'sequence_id', r.sequence_id,
          'event_id', r.event_id,
          'correction_id', c.correction_id,
          'defect_class', c.defect_class,
          'original_event_hash', r.event_hash,
          'expected_event_hash', v_expected_event_hash,
          'payload_hash_ok', true,
          'previous_hash_ok', true
        ));
      end if;
    end if;

    if not v_schema_supported
       or r.payload_sha256 is distinct from v_expected_payload_sha256
       or r.previous_event_hash is distinct from v_previous_event_hash
       or (r.event_hash is distinct from v_expected_event_hash and not v_correction_ok) then
      v_failures := v_failures || jsonb_build_array(jsonb_build_object(
        'sequence_id', r.sequence_id,
        'event_id', r.event_id,
        'schema_version', r.schema_version,
        'schema_supported', v_schema_supported,
        'payload_hash_ok', r.payload_sha256 = v_expected_payload_sha256,
        'previous_hash_ok', r.previous_event_hash is not distinct from v_previous_event_hash,
        'event_hash_ok', r.event_hash = v_expected_event_hash,
        'documented_correction', v_correction_ok
      ));
    end if;

    if coalesce(r.schema_version, '1.0.0') = '2.0.0'
       and r.evidence_class = 'E4_EXTERNAL_SYMMETRIC_VERIFIED' then
      v_external_checked := v_external_checked + 1;

      select ev.*
        into v_verification
      from chlom_runtime.external_verification_receipts_v2 ev
      where ev.verification_receipt_id = r.verification_receipt_id;
      v_verification_found := found;

      if v_verification_found then
        select ei.*
          into v_ingress
        from chlom_runtime.external_ingress_receipts_v2 ei
        where ei.ingress_receipt_id = v_verification.ingress_receipt_id;
        v_ingress_found := found;
      else
        v_ingress_found := false;
      end if;

      if v_ingress_found then
        v_expected_ingress_hash := encode(
          extensions.digest(
            convert_to(
              chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
                'receipt_format', 'dail.external-ingress.v2',
                'canonicalization_version', 'ct-json-sort-v1',
                'ingress_receipt_id', v_ingress.ingress_receipt_id,
                'provider', v_ingress.provider,
                'source_event_id', v_ingress.source_event_id,
                'provider_event_type', v_ingress.provider_event_type,
                'provider_account_ref', v_ingress.provider_account_ref,
                'environment', v_ingress.environment,
                'producer_trust_domain', v_ingress.producer_trust_domain,
                'raw_body_sha256', v_ingress.raw_body_sha256,
                'signature_header_sha256', v_ingress.signature_header_sha256,
                'signature_timestamp', v_ingress.signature_timestamp,
                'received_at', to_char(
                  v_ingress.received_at at time zone 'UTC',
                  'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                ),
                'ingress_state', v_ingress.ingress_state,
                'created_at', to_char(
                  v_ingress.created_at at time zone 'UTC',
                  'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                )
              )),
              'UTF8'
            ),
            'sha256'
          ),
          'hex'
        );

        v_expected_verification_hash := encode(
          extensions.digest(
            convert_to(
              chlom_runtime.canonical_jsonb_v1(jsonb_build_object(
                'receipt_format', 'dail.external-verification.v2',
                'canonicalization_version', 'ct-json-sort-v1',
                'verification_receipt_id', v_verification.verification_receipt_id,
                'ingress_receipt_id', v_verification.ingress_receipt_id,
                'ingress_receipt_sha256', v_ingress.receipt_sha256,
                'provider', v_verification.provider,
                'verifier_id', v_verification.verifier_id,
                'verifier_trust_domain', v_verification.verifier_trust_domain,
                'producer_trust_domain', v_verification.producer_trust_domain,
                'algorithm', v_verification.algorithm,
                'secret_version_ref', v_verification.secret_version_ref,
                'signature_timestamp', v_verification.signature_timestamp,
                'tolerance_seconds', v_verification.tolerance_seconds,
                'verifier_tool_version', v_verification.verifier_tool_version,
                'verification_state', v_verification.verification_state,
                'evidence_tier', v_verification.evidence_tier,
                'provider_readback_state', v_verification.provider_readback_state,
                'provider_readback_receipt_ref', v_verification.provider_readback_receipt_ref,
                'signed_payload_sha256', v_verification.signed_payload_sha256,
                'limitation', v_verification.limitation,
                'verified_at', to_char(
                  v_verification.verified_at at time zone 'UTC',
                  'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                )
              )),
              'UTF8'
            ),
            'sha256'
          ),
          'hex'
        );
      else
        v_expected_ingress_hash := null;
        v_expected_verification_hash := null;
      end if;

      if not v_verification_found
         or not v_ingress_found
         or v_verification.verification_state is distinct from 'verified'
         or v_verification.algorithm is distinct from 'hmac-sha256'
         or v_verification.evidence_tier is distinct from r.evidence_class
         or v_verification.provider is distinct from r.source_system
         or v_verification.producer_trust_domain is distinct from r.trust_domain
         or v_verification.verifier_trust_domain is not distinct from v_verification.producer_trust_domain
         or v_ingress.provider is distinct from r.source_system
         or v_ingress.source_event_id is distinct from r.source_event_id
         or v_ingress.receipt_sha256 is distinct from v_expected_ingress_hash
         or v_verification.receipt_sha256 is distinct from v_expected_verification_hash
         or r.payload->'ingress_receipt'->>'sha256' is distinct from v_ingress.receipt_sha256
         or r.payload->'verification_receipt'->>'sha256' is distinct from v_verification.receipt_sha256
         or r.payload->>'raw_body_sha256' is distinct from v_ingress.raw_body_sha256 then
        v_provenance_failures := v_provenance_failures || jsonb_build_array(jsonb_build_object(
          'sequence_id', r.sequence_id,
          'event_id', r.event_id,
          'source_system', r.source_system,
          'source_event_id', r.source_event_id,
          'verification_receipt_present', v_verification_found,
          'ingress_receipt_present', v_ingress_found,
          'ingress_receipt_hash_ok',
            case when v_ingress_found then v_ingress.receipt_sha256 = v_expected_ingress_hash else false end,
          'verification_receipt_hash_ok',
            case when v_verification_found and v_ingress_found
              then v_verification.receipt_sha256 = v_expected_verification_hash
              else false
            end,
          'trust_domains_separated',
            case when v_verification_found
              then v_verification.verifier_trust_domain <> v_verification.producer_trust_domain
              else false
            end
        ));
      end if;
    end if;

    -- Physical chain continuity always follows the immutable stored event hash,
    -- including the one documented legacy construction defect.
    v_previous_event_hash := r.event_hash;
  end loop;

  return jsonb_build_object(
    'ok', jsonb_array_length(v_failures) = 0
      and jsonb_array_length(v_provenance_failures) = 0,
    'integrity_state', case
      when jsonb_array_length(v_failures) > 0
        or jsonb_array_length(v_provenance_failures) > 0 then 'fail'
      when jsonb_array_length(v_corrected) > 0 then 'pass_with_documented_legacy_correction'
      else 'pass'
    end,
    'chain_id', 'ct.dail.global.v1',
    'checked_events', v_checked,
    'external_evidence_events_checked', v_external_checked,
    'head_hash', v_previous_event_hash,
    'failure_count', jsonb_array_length(v_failures),
    'provenance_failure_count', jsonb_array_length(v_provenance_failures),
    'corrected_event_count', jsonb_array_length(v_corrected),
    'failures', v_failures,
    'provenance_failures', v_provenance_failures,
    'corrected_events', v_corrected,
    'checked_at', clock_timestamp()
  );
end
$function$;

-- Public-schema projection for PostgREST discovery. This narrow SECURITY
-- DEFINER wrapper is executable only by service_role; the Edge verifier also
-- supplies a dedicated Vault-verified admission MAC before evidence is accepted.
create or replace function public.dail_ingest_verified_external_event_v2(
  p_provider text,
  p_source_event_id text,
  p_provider_event_type text,
  p_provider_object_type text,
  p_provider_object_id text,
  p_api_version text,
  p_livemode boolean,
  p_pending_webhooks integer,
  p_provider_request_ref text,
  p_provider_account_ref text,
  p_raw_body_sha256 text,
  p_signed_payload_sha256 text,
  p_signature_header_sha256 text,
  p_signature_timestamp bigint,
  p_signature_tolerance_seconds integer,
  p_secret_version_ref text,
  p_verifier_id text,
  p_verifier_tool_version text,
  p_verifier_trust_domain text,
  p_producer_trust_domain text,
  p_admission_mac text,
  p_received_at timestamptz
)
returns jsonb
language sql
security definer
set search_path = 'pg_catalog', 'chlom_runtime'
as $function$
  select chlom_runtime.ingest_verified_external_event_v2(
    p_provider,
    p_source_event_id,
    p_provider_event_type,
    p_provider_object_type,
    p_provider_object_id,
    p_api_version,
    p_livemode,
    p_pending_webhooks,
    p_provider_request_ref,
    p_provider_account_ref,
    p_raw_body_sha256,
    p_signed_payload_sha256,
    p_signature_header_sha256,
    p_signature_timestamp,
    p_signature_tolerance_seconds,
    p_secret_version_ref,
    p_verifier_id,
    p_verifier_tool_version,
    p_verifier_trust_domain,
    p_producer_trust_domain,
    p_admission_mac,
    p_received_at
  )
$function$;

-- Fail-closed cutover: once v2 columns and admission paths exist, the legacy
-- writer may no longer append rows that omit provenance, idempotency and
-- evidence classification. Callers must migrate before this held migration is
-- promoted; applying it prematurely will intentionally stop legacy writes.
create or replace function chlom_runtime.append_dail_event(
  p_event_type text,
  p_entity_type text,
  p_entity_id text,
  p_payload jsonb default '{}'::jsonb,
  p_actor_ref text default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_entity_version text default null,
  p_correlation_id text default null,
  p_causation_id text default null,
  p_authority_basis text default null,
  p_approval_id text default null,
  p_visibility_class text default 'internal'
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog', 'chlom_runtime'
as $function$
begin
  raise exception using
    errcode = '0A000',
    message = 'legacy DAIL append is retired; use a governed DAIL v2 admission path';
end
$function$;

revoke all on function chlom_runtime.append_dail_event(
  text, text, text, jsonb, text, text, text, text, text, text, text, text, text
) from public, anon, authenticated, service_role;

do $function_acl$
declare
  r record;
begin
  for r in
    select p.oid::regprocedure as function_identity
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where (
      n.nspname = 'chlom_runtime'
      and p.proname in (
        'reject_append_only_mutation_v2',
        'enforce_factory_fencing_v2',
        'canonical_jsonb_v1',
        'jsonb_uses_portable_numbers_v1',
        'dail_event_v2_preimage',
        'append_dail_event_v2',
        'ingest_verified_external_event_v2',
        'append_factory_continuation_v2',
        'verify_dail_chain'
      )
    ) or (
      n.nspname = 'public'
      and p.proname = 'dail_ingest_verified_external_event_v2'
    )
  loop
    execute format(
      'revoke all on function %s from public, anon, authenticated, service_role',
      r.function_identity
    );
  end loop;

  for r in
    select p.oid::regprocedure as function_identity
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where (
      n.nspname = 'chlom_runtime'
      and p.proname in (
        'append_dail_event_v2',
        'append_factory_continuation_v2',
        'verify_dail_chain'
      )
    ) or (
      n.nspname = 'public'
      and p.proname = 'dail_ingest_verified_external_event_v2'
    )
  loop
    execute format(
      'grant execute on function %s to service_role',
      r.function_identity
    );
  end loop;
end
$function_acl$;

do $postflight$
declare
  v_result jsonb;
begin
  v_result := chlom_runtime.verify_dail_chain();
  if not coalesce((v_result->>'ok')::boolean, false) then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 postflight failed: the inherited ledger no longer verifies';
  end if;
  if v_result->>'chain_id' <> 'ct.dail.global.v1' then
    raise exception using
      errcode = '55000',
      message = 'DAIL v2 postflight failed: canonical chain identity drifted';
  end if;
end
$postflight$;

comment on table chlom_runtime.external_verification_receipts_v2 is
  'Append-only symmetric-verification receipts. evidence_tier and provider_readback_state are independent dimensions; HMAC is not public-key nonrepudiation.';
comment on table chlom_runtime.external_anchor_receipts_v2 is
  'Append-only external-anchor receipt substrate. No anchor provider, admission RPC, scheduler, or production anchor is deployed by this migration.';
comment on table chlom_runtime.factory_continuation_receipts_v2 is
  'Append-only partial factory-continuation source with deterministic content digests, monotonic non-forking fencing, DAIL linkage, and separate provider-readback state. Claim/reclaim and authenticated terminal admission remain blocked.';
comment on function chlom_runtime.canonical_jsonb_v1(jsonb) is
  'ct-json-sort-v1 canonical UTF-8 JSON serializer used by DAIL v2 and receipt hashes.';
comment on function chlom_runtime.append_dail_event_v2(
  text, text, text, text, text, text, text, jsonb, text, text, text,
  text, text, text, text, text, text, text, uuid, text, uuid, uuid,
  text, text, text
) is
  'Service-only DAIL v2 append. E2/E5/E6 and caller-asserted anchor states are rejected pending dedicated authenticated admission controls.';

-- Remaining explicit trust boundary: the postgres/table owner can bypass RLS
-- and administer triggers. Independent immutability requires a separately
-- controlled E6 anchor, which is intentionally not claimed here.

commit;
