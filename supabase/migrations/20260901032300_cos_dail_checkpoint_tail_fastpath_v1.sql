-- CrownThrive COS V1 sprint performance repair.
-- Replaces two full-history DAIL anti-joins with the canonical checkpoint-tail invariant.
-- The migration proves the current membership is an exact prefix before changing either function.
-- Rollback: restore the predecessor function definitions captured by the guarded digests below.

do $repair$
declare
  v_status_definition text;
  v_checkpoint_definition text;
  v_status_pre_sha text;
  v_checkpoint_pre_sha text;
  v_status_post_sha text;
  v_checkpoint_post_sha text;
  v_max_checkpoint_end bigint;
  v_checkpoint_event_count bigint;
  v_membership_count bigint;
  v_events_through_checkpoint_end bigint;
  v_status_old constant text := $$  select count(*) into v_checkpoint_remaining from chlom_runtime.dail_events e
    where not exists(select 1 from chlom_runtime.dail_epoch_membership_v2 m where m.sequence_id=e.sequence_id);$$;
  v_status_new constant text := $$  select count(*) into v_checkpoint_remaining
  from chlom_runtime.dail_events e
  where e.sequence_id > coalesce(
    (select max(end_sequence_id) from chlom_runtime.dail_epoch_checkpoints_v2),
    0
  );$$;
  v_checkpoint_old constant text := $$    select e.sequence_id,e.event_hash
    from chlom_runtime.dail_events e
    where not exists(select 1 from chlom_runtime.dail_epoch_membership_v2 m where m.sequence_id=e.sequence_id)
    order by e.sequence_id
    limit p_max_events$$;
  v_checkpoint_new constant text := $$    select e.sequence_id,e.event_hash
    from chlom_runtime.dail_events e
    where e.sequence_id > coalesce(
      (select max(sequence_id) from chlom_runtime.dail_epoch_membership_v2),
      0
    )
    order by e.sequence_id
    limit p_max_events$$;
begin
  -- Prove the checkpoint membership is currently an exact prefix of committed DAIL events.
  select coalesce(max(end_sequence_id),0), coalesce(sum(event_count),0)
    into v_max_checkpoint_end, v_checkpoint_event_count
  from chlom_runtime.dail_epoch_checkpoints_v2;

  select count(*) into v_membership_count
  from chlom_runtime.dail_epoch_membership_v2;

  select count(*) into v_events_through_checkpoint_end
  from chlom_runtime.dail_events
  where sequence_id <= v_max_checkpoint_end;

  if v_membership_count <> v_checkpoint_event_count
     or v_membership_count <> v_events_through_checkpoint_end then
    raise exception 'DAIL checkpoint prefix invariant not proven: membership %, checkpoint events %, events through end %',
      v_membership_count, v_checkpoint_event_count, v_events_through_checkpoint_end;
  end if;

  select pg_get_functiondef('public.cos_v1_status_v3()'::regprocedure)
    into v_status_definition;
  select pg_get_functiondef('chlom_runtime.create_dail_epoch_checkpoint_v2(integer)'::regprocedure)
    into v_checkpoint_definition;

  v_status_pre_sha := encode(extensions.digest(v_status_definition,'sha256'),'hex');
  v_checkpoint_pre_sha := encode(extensions.digest(v_checkpoint_definition,'sha256'),'hex');

  if v_status_pre_sha <> '5505170f1cf843a722325d59f5e14d3b6425e60632ade7269881880b132acc96' then
    raise exception 'cos_v1_status_v3 predecessor drift: expected %, found %',
      '5505170f1cf843a722325d59f5e14d3b6425e60632ade7269881880b132acc96', v_status_pre_sha;
  end if;
  if v_checkpoint_pre_sha <> 'b91294d94aa7a79401758834364afae2ed75741e02eff947e8683ca700fe9985' then
    raise exception 'create_dail_epoch_checkpoint_v2 predecessor drift: expected %, found %',
      'b91294d94aa7a79401758834364afae2ed75741e02eff947e8683ca700fe9985', v_checkpoint_pre_sha;
  end if;

  if position(v_status_old in v_status_definition)=0 then
    raise exception 'COS checkpoint remaining anti-join fragment is absent';
  end if;
  if position(v_checkpoint_old in v_checkpoint_definition)=0 then
    raise exception 'DAIL checkpoint creator anti-join fragment is absent';
  end if;

  v_status_definition := replace(v_status_definition,v_status_old,v_status_new);
  v_checkpoint_definition := replace(v_checkpoint_definition,v_checkpoint_old,v_checkpoint_new);

  execute v_status_definition;
  execute v_checkpoint_definition;

  select encode(extensions.digest(pg_get_functiondef('public.cos_v1_status_v3()'::regprocedure),'sha256'),'hex')
    into v_status_post_sha;
  select encode(extensions.digest(pg_get_functiondef('chlom_runtime.create_dail_epoch_checkpoint_v2(integer)'::regprocedure),'sha256'),'hex')
    into v_checkpoint_post_sha;

  if v_status_post_sha=v_status_pre_sha or v_checkpoint_post_sha=v_checkpoint_pre_sha then
    raise exception 'DAIL checkpoint tail repair failed to change both guarded function digests';
  end if;
end
$repair$;

comment on function public.cos_v1_status_v3() is
  'COS V1 convergence/status v3. Checkpoint remaining count uses canonical attested checkpoint tail; full-history anti-join removed by sprint performance repair.';
comment on function chlom_runtime.create_dail_epoch_checkpoint_v2(integer) is
  'DAIL trust checkpoint v2. Candidate selection uses canonical append-only membership tail after migration-time prefix proof; bounded by p_max_events.';
