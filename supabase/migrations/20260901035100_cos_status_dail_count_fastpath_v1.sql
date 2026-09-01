-- CrownThrive COS V1 sprint status fast path.
-- Exact DAIL event/checkpointed counts are derived from the already-proven
-- checkpoint prefix plus the bounded uncheckpointed tail. This removes two
-- full-table counts from every status/certifier read without weakening truth.
-- Rollback: restore predecessor function digest from source history.

do $repair$
declare
  v_definition text;
  v_pre_sha text;
  v_post_sha text;
  v_max_checkpoint_end bigint;
  v_checkpoint_event_count bigint;
  v_membership_count bigint;
  v_events_through_checkpoint_end bigint;
  v_old_events constant text := $$'events',(select count(*) from chlom_runtime.dail_events)$$;
  v_new_events constant text := $$'events',((select coalesce(sum(event_count),0)::bigint from chlom_runtime.dail_epoch_checkpoints_v2)+v_checkpoint_remaining)$$;
  v_old_members constant text := $$'checkpointed_events',(select count(*) from chlom_runtime.dail_epoch_membership_v2)$$;
  v_new_members constant text := $$'checkpointed_events',(select coalesce(sum(event_count),0)::bigint from chlom_runtime.dail_epoch_checkpoints_v2)$$;
begin
  -- Re-prove the prefix invariant at mutation time.
  select coalesce(max(end_sequence_id),0),coalesce(sum(event_count),0)
    into v_max_checkpoint_end,v_checkpoint_event_count
  from chlom_runtime.dail_epoch_checkpoints_v2;
  select count(*) into v_membership_count from chlom_runtime.dail_epoch_membership_v2;
  select count(*) into v_events_through_checkpoint_end
  from chlom_runtime.dail_events where sequence_id<=v_max_checkpoint_end;
  if v_membership_count<>v_checkpoint_event_count
     or v_membership_count<>v_events_through_checkpoint_end then
    raise exception 'DAIL checkpoint prefix invariant not proven: membership %, checkpoint events %, events through end %',
      v_membership_count,v_checkpoint_event_count,v_events_through_checkpoint_end;
  end if;

  select pg_get_functiondef('public.cos_v1_status_v3()'::regprocedure) into v_definition;
  v_pre_sha:=encode(extensions.digest(v_definition,'sha256'),'hex');
  if v_pre_sha<>'57b428829cba9639146a2c4bd55400e925864c81373b51dc3783c7880261dfb4' then
    raise exception 'cos_v1_status_v3 predecessor drift: expected %, found %',
      '57b428829cba9639146a2c4bd55400e925864c81373b51dc3783c7880261dfb4',v_pre_sha;
  end if;
  if position(v_old_events in v_definition)=0 or position(v_old_members in v_definition)=0 then
    raise exception 'expected DAIL count status fragments absent';
  end if;
  v_definition:=replace(v_definition,v_old_events,v_new_events);
  v_definition:=replace(v_definition,v_old_members,v_new_members);
  execute v_definition;
  select encode(extensions.digest(pg_get_functiondef('public.cos_v1_status_v3()'::regprocedure),'sha256'),'hex') into v_post_sha;
  if v_post_sha=v_pre_sha then raise exception 'DAIL status count fast path made no change'; end if;
end
$repair$;

comment on function public.cos_v1_status_v3() is
  'COS V1 convergence/status v3. Exact DAIL counts derive from proven checkpoint prefix plus bounded tail; no full-history count in status path.';
