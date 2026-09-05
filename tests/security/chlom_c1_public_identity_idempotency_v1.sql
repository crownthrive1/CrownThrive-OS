-- CHLOM C1 public identity / DID idempotency acceptance v1
-- Runs transactionally and leaves no durable canary state.

begin;

-- Contract must contain an explicit transaction-scoped serialization primitive.
do $test$
declare
  v_def text;
begin
  select pg_get_functiondef('chlom_identity.ensure_public_identity(text,text,jsonb)'::regprocedure)
    into v_def;
  if position('pg_advisory_xact_lock' in v_def) = 0 then
    raise exception 'FAIL: C1 issuer lacks transaction-scoped subject serialization';
  end if;
  if position('hashtextextended' in v_def) = 0 then
    raise exception 'FAIL: C1 issuer lock is not deterministically keyed by subject';
  end if;
end
$test$;

-- Least-privilege boundary must remain service-role only.
do $test$
begin
  if has_function_privilege('public', 'chlom_identity.ensure_public_identity(text,text,jsonb)', 'EXECUTE') then
    raise exception 'FAIL: PUBLIC can execute C1 identity issuer';
  end if;
  if has_function_privilege('anon', 'chlom_identity.ensure_public_identity(text,text,jsonb)', 'EXECUTE') then
    raise exception 'FAIL: anon can execute C1 identity issuer';
  end if;
  if has_function_privilege('authenticated', 'chlom_identity.ensure_public_identity(text,text,jsonb)', 'EXECUTE') then
    raise exception 'FAIL: authenticated can execute C1 identity issuer';
  end if;
  if not has_function_privilege('service_role', 'chlom_identity.ensure_public_identity(text,text,jsonb)', 'EXECUTE') then
    raise exception 'FAIL: service_role lost C1 identity issuer execute';
  end if;
end
$test$;

-- Unknown/empty identities must fail closed.
do $test$
begin
  begin
    perform chlom_identity.ensure_public_identity('', null, '{}'::jsonb);
    raise exception 'FAIL: empty subject unexpectedly accepted';
  exception when others then
    if sqlerrm = 'FAIL: empty subject unexpectedly accepted' then raise; end if;
    if position('invalid_subject_id' in sqlerrm) = 0 then
      raise exception 'FAIL: unexpected empty-subject error: %', sqlerrm;
    end if;
  end;

  begin
    perform chlom_identity.ensure_public_identity('ct.test.c1.missing.subject', null, '{}'::jsonb);
    raise exception 'FAIL: unknown subject unexpectedly accepted';
  exception when others then
    if sqlerrm = 'FAIL: unknown subject unexpectedly accepted' then raise; end if;
    if position('unknown_subject' in sqlerrm) = 0 then
      raise exception 'FAIL: unexpected unknown-subject error: %', sqlerrm;
    end if;
  end;
end
$test$;

-- Sequential replay proves durable idempotency; the advisory-lock contract above
-- closes the concurrent SELECT->INSERT race for the same subject.
do $test$
declare
  v_subject text := 'ct.test.chlom.c1.identity.idempotency.v1';
  v_first jsonb;
  v_second jsonb;
  v_count integer;
begin
  insert into chlom_identity.subjects(
    subject_id, subject_kind, canonical_name, source_ref,
    authority_state, visibility, metadata
  ) values (
    v_subject, 'other', 'CHLOM C1 Idempotency Canary',
    'test:chlom-c1-public-identity-idempotency-v1',
    'research_candidate', 'internal',
    jsonb_build_object('test_only', true)
  ) on conflict (subject_id) do update
    set source_ref = excluded.source_ref,
        metadata = chlom_identity.subjects.metadata || excluded.metadata,
        updated_at = now();

  v_first := chlom_identity.ensure_public_identity(
    v_subject,
    'CHLOM C1 Idempotency Canary',
    jsonb_build_object('test_only', true)
  );
  v_second := chlom_identity.ensure_public_identity(
    v_subject,
    'ignored-on-replay',
    jsonb_build_object('replay', true)
  );

  if v_first->>'public_id' is distinct from v_second->>'public_id' then
    raise exception 'FAIL: replay changed public_id';
  end if;
  if v_first->>'did_uri' is distinct from v_second->>'did_uri' then
    raise exception 'FAIL: replay changed DID';
  end if;
  if coalesce(v_first->>'public_id','') !~ '^ctid_[0-9a-f]{32}$' then
    raise exception 'FAIL: invalid public_id format';
  end if;
  if coalesce(v_first->>'did_uri','') <> 'did:chlom:' || (v_first->>'public_id') then
    raise exception 'FAIL: DID/public_id binding mismatch';
  end if;

  select count(*) into v_count
    from chlom_identity.public_identity_records
   where subject_id = v_subject;
  if v_count <> 1 then
    raise exception 'FAIL: expected exactly one durable identity row, got %', v_count;
  end if;
end
$test$;

-- Fingerprinting remains deterministic and domain-separating by input bytes.
do $test$
declare
  v_a text := chlom_identity.fingerprint_text('CHLOM C1 canonical identity');
  v_b text := chlom_identity.fingerprint_text('CHLOM C1 canonical identity');
  v_c text := chlom_identity.fingerprint_text('CHLOM C1 canonical identity.');
begin
  if v_a is distinct from v_b then
    raise exception 'FAIL: identical canonical text produced different fingerprints';
  end if;
  if v_a = v_c then
    raise exception 'FAIL: distinct canonical text produced identical fingerprint';
  end if;
  if v_a !~ '^ctfp:v1:sha256:[0-9a-f]{64}$' then
    raise exception 'FAIL: fingerprint format drift';
  end if;
end
$test$;

rollback;
