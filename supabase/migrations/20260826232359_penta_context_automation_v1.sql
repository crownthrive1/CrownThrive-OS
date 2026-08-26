-- PentaContext v1.1 durable automated ingestion. Applied to production 20260826232359.
alter table public.penta_context_receipts_v1 drop constraint penta_context_receipts_v1_operation_check;
alter table public.penta_context_receipts_v1 add constraint penta_context_receipts_v1_operation_check check (operation = any (array['ingest','enqueue','process','query','maintenance','health','tombstone','dead_letter']::text[]));

create table public.penta_context_ingest_queue_v1 (
  job_id uuid primary key default gen_random_uuid(), idempotency_key text not null unique,
  scope_key text not null check (length(scope_key) between 2 and 128),
  source_type text not null check (source_type = any (array['github','drive','database','api','web','document','message','email','calendar','event','system','manual','other']::text[])),
  source_ref text not null check (length(btrim(source_ref)) > 0),
  content text not null check (length(btrim(content)) > 0 and length(content) <= 500000), title text, summary text,
  tags text[] not null default '{}'::text[], metadata jsonb not null default '{}'::jsonb,
  classification text not null default 'internal' check (classification = any (array['public','internal','confidential','restricted']::text[])),
  importance numeric(5,4) not null default 0.5000 check (importance between 0 and 1), confidence numeric(5,4) not null default 0.7000 check (confidence between 0 and 1),
  observed_at timestamptz not null default now(), expires_at timestamptz, actor_ref text not null default 'penta.context.queue',
  priority smallint not null default 50 check (priority between 0 and 100), status text not null default 'queued' check (status = any (array['queued','processing','retry','completed','dead_letter']::text[])),
  attempt_count integer not null default 0 check (attempt_count >= 0), max_attempts integer not null default 5 check (max_attempts between 1 and 20), next_attempt_at timestamptz not null default now(),
  locked_at timestamptz, locked_by text, context_id uuid references public.penta_context_records_v1(context_id) on delete restrict, source_id uuid references public.penta_context_sources_v1(source_id) on delete restrict,
  fingerprint_sha256 text check (fingerprint_sha256 is null or fingerprint_sha256 ~ '^[0-9a-f]{64}$'), last_error text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(), completed_at timestamptz,
  check (expires_at is null or expires_at > created_at)
);
create index penta_context_queue_worker_idx on public.penta_context_ingest_queue_v1(status,next_attempt_at,priority desc,created_at) where status in ('queued','retry');
create index penta_context_queue_scope_idx on public.penta_context_ingest_queue_v1(scope_key,created_at desc);
create index penta_context_queue_context_idx on public.penta_context_ingest_queue_v1(context_id) where context_id is not null;
create index penta_context_queue_source_idx on public.penta_context_ingest_queue_v1(source_id) where source_id is not null;
create trigger penta_context_queue_touch_v1 before update on public.penta_context_ingest_queue_v1 for each row execute function public.penta_context_touch_updated_at_v1();

create or replace function public.penta_context_enqueue_v1(p_scope_key text,p_source_type text,p_source_ref text,p_content text,p_title text default null,p_summary text default null,p_tags text[] default '{}'::text[],p_metadata jsonb default '{}'::jsonb,p_classification text default 'internal',p_importance numeric default 0.5,p_confidence numeric default 0.7,p_observed_at timestamptz default now(),p_expires_at timestamptz default null,p_actor_ref text default 'penta.context.queue',p_priority integer default 50,p_idempotency_key text default null)
returns jsonb language plpgsql set search_path=pg_catalog,public,extensions as $$
declare v_scope text:=lower(btrim(p_scope_key)); v_type text:=lower(btrim(p_source_type)); v_class text:=lower(btrim(p_classification)); v_content text; v_meta jsonb; v_tags text[]; v_key text; v_job uuid; v_inserted boolean; v_input_sha text;
begin
 if v_scope='' or length(v_scope)>128 then raise exception 'invalid scope_key'; end if;
 if v_type <> all(array['github','drive','database','api','web','document','message','email','calendar','event','system','manual','other']::text[]) then raise exception 'invalid source_type'; end if;
 if v_class <> all(array['public','internal','confidential','restricted']::text[]) then raise exception 'invalid classification'; end if;
 if p_content is null or length(btrim(p_content))=0 or length(p_content)>500000 then raise exception 'invalid content length'; end if;
 if p_importance<0 or p_importance>1 or p_confidence<0 or p_confidence>1 then raise exception 'importance/confidence out of range'; end if;
 if p_priority<0 or p_priority>100 then raise exception 'priority out of range'; end if;
 if p_expires_at is not null and p_expires_at<=now() then raise exception 'expires_at must be future'; end if;
 v_content:=public.penta_context_redact_v1(p_content); v_meta:=public.penta_context_sanitize_metadata_v1(coalesce(p_metadata,'{}'::jsonb));
 select coalesce(array_agg(distinct lower(btrim(x))) filter(where btrim(x)<>''),'{}'::text[]) into v_tags from unnest(coalesce(p_tags,'{}'::text[])) x;
 v_input_sha:=encode(extensions.digest(concat_ws(E'\n',v_scope,v_type,btrim(p_source_ref),v_content),'sha256'),'hex'); v_key:=coalesce(nullif(btrim(p_idempotency_key),''),'ctxq:'||v_input_sha);
 insert into public.penta_context_ingest_queue_v1(idempotency_key,scope_key,source_type,source_ref,content,title,summary,tags,metadata,classification,importance,confidence,observed_at,expires_at,actor_ref,priority)
 values(v_key,v_scope,v_type,btrim(p_source_ref),v_content,case when p_title is null then null else public.penta_context_redact_v1(p_title) end,case when p_summary is null then null else public.penta_context_redact_v1(p_summary) end,v_tags,v_meta,v_class,p_importance,p_confidence,coalesce(p_observed_at,now()),p_expires_at,coalesce(nullif(p_actor_ref,''),'penta.context.queue'),p_priority)
 on conflict(idempotency_key) do nothing returning job_id into v_job;
 v_inserted:=v_job is not null; if v_job is null then select job_id into v_job from public.penta_context_ingest_queue_v1 where idempotency_key=v_key; end if;
 insert into public.penta_context_receipts_v1(operation,scope_key,actor_ref,idempotency_key,input_sha256,evidence) values('enqueue',v_scope,coalesce(nullif(p_actor_ref,''),'penta.context.queue'),'enqueue:'||v_key,v_input_sha,jsonb_build_object('job_id',v_job,'inserted',v_inserted,'priority',p_priority,'authority_created',false)) on conflict(operation,idempotency_key) do nothing;
 return jsonb_build_object('job_id',v_job,'idempotency_key',v_key,'inserted',v_inserted,'status','queued','authority_created',false);
end; $$;

create or replace function public.penta_context_process_queue_v1(p_limit integer default 50,p_worker_ref text default 'penta.context.worker') returns jsonb language plpgsql set search_path=pg_catalog,public as $$
declare r record; v_result jsonb; v_done integer:=0; v_retry integer:=0; v_dead integer:=0; v_attempt integer;
begin
 for r in select * from public.penta_context_ingest_queue_v1 where status in('queued','retry') and next_attempt_at<=now() order by priority desc,next_attempt_at,created_at for update skip locked limit greatest(1,least(coalesce(p_limit,50),200)) loop
  update public.penta_context_ingest_queue_v1 set status='processing',locked_at=now(),locked_by=p_worker_ref where job_id=r.job_id;
  begin
   v_result:=public.penta_context_ingest_v1(r.scope_key,r.source_type,r.source_ref,r.content,r.title,r.summary,r.tags,r.metadata,r.classification,r.importance,r.confidence,r.observed_at,r.expires_at,r.actor_ref);
   update public.penta_context_ingest_queue_v1 set status='completed',attempt_count=attempt_count+1,context_id=(v_result->>'context_id')::uuid,source_id=(v_result->>'source_id')::uuid,fingerprint_sha256=v_result->>'fingerprint_sha256',last_error=null,completed_at=now(),locked_at=null,locked_by=null where job_id=r.job_id;
   insert into public.penta_context_receipts_v1(operation,scope_key,context_id,source_id,actor_ref,idempotency_key,output_sha256,evidence) values('process',r.scope_key,(v_result->>'context_id')::uuid,(v_result->>'source_id')::uuid,p_worker_ref,'process:'||r.idempotency_key,v_result->>'fingerprint_sha256',jsonb_build_object('job_id',r.job_id,'attempt',r.attempt_count+1,'authority_created',false)) on conflict(operation,idempotency_key) do nothing; v_done:=v_done+1;
  exception when others then
   v_attempt:=r.attempt_count+1;
   if v_attempt>=r.max_attempts then
    update public.penta_context_ingest_queue_v1 set status='dead_letter',attempt_count=v_attempt,last_error=left(public.penta_context_redact_v1(sqlerrm),1000),locked_at=null,locked_by=null where job_id=r.job_id;
    insert into public.penta_context_receipts_v1(operation,scope_key,actor_ref,idempotency_key,passed,evidence) values('dead_letter',r.scope_key,p_worker_ref,'dead:'||r.idempotency_key,false,jsonb_build_object('job_id',r.job_id,'attempts',v_attempt,'error',left(public.penta_context_redact_v1(sqlerrm),500),'authority_created',false)) on conflict(operation,idempotency_key) do nothing; v_dead:=v_dead+1;
   else
    update public.penta_context_ingest_queue_v1 set status='retry',attempt_count=v_attempt,next_attempt_at=now()+make_interval(secs=>least(3600,60*(2^least(v_attempt,6))::int)),last_error=left(public.penta_context_redact_v1(sqlerrm),1000),locked_at=null,locked_by=null where job_id=r.job_id; v_retry:=v_retry+1;
   end if;
  end;
 end loop;
 return jsonb_build_object('completed',v_done,'retry',v_retry,'dead_letter',v_dead,'worker_ref',p_worker_ref,'authority_created',false);
end; $$;

create or replace function public.penta_context_queue_status_v1(p_scope_key text default null) returns jsonb language sql stable set search_path=pg_catalog,public as $$ select jsonb_build_object('system_key','penta.context','scope_key',p_scope_key,'queued',count(*) filter(where status='queued'),'processing',count(*) filter(where status='processing'),'retry',count(*) filter(where status='retry'),'completed',count(*) filter(where status='completed'),'dead_letter',count(*) filter(where status='dead_letter'),'oldest_pending_at',min(created_at) filter(where status in('queued','retry')),'checked_at',now(),'authority_created',false) from public.penta_context_ingest_queue_v1 where p_scope_key is null or scope_key=lower(btrim(p_scope_key)); $$;

alter table public.penta_context_ingest_queue_v1 enable row level security;
create policy penta_context_queue_explicit_client_deny_v1 on public.penta_context_ingest_queue_v1 for all to anon,authenticated using(false) with check(false);
revoke all on public.penta_context_ingest_queue_v1 from public,anon,authenticated; grant select,insert,update on public.penta_context_ingest_queue_v1 to service_role;
revoke execute on function public.penta_context_enqueue_v1(text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz,text,integer,text) from public,anon,authenticated;
revoke execute on function public.penta_context_process_queue_v1(integer,text) from public,anon,authenticated;
revoke execute on function public.penta_context_queue_status_v1(text) from public,anon,authenticated;
grant execute on function public.penta_context_enqueue_v1(text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz,text,integer,text) to service_role;
grant execute on function public.penta_context_process_queue_v1(integer,text) to service_role; grant execute on function public.penta_context_queue_status_v1(text) to service_role;
do $$ begin perform cron.unschedule('penta-context-ingest-worker-v1'); exception when others then null; end $$;
select cron.schedule('penta-context-ingest-worker-v1','* * * * *','select public.penta_context_process_queue_v1(50,''penta.mation'');');
with d as (select jsonb_build_object('system_key','penta.context','action','process_ingest_queue','schedule','* * * * *','function','public.penta_context_process_queue_v1','batch_size',50,'retry_backoff','exponential_capped_1h','dead_letter',true,'authority_created',false) definition)
insert into public.penta_mation_workflows(workflow_id,version,status,trigger_type,risk_class,authority_ref,owner_ref,definition,definition_sha256,schema_version) select 'penta.context.ingest-worker',1,'active','schedule','D1','penta.context:D1-ingest-worker','penta.context',definition,encode(extensions.digest(definition::text,'sha256'),'hex'),'1.0.0' from d on conflict(workflow_id,version) do update set status='active',definition=excluded.definition,definition_sha256=excluded.definition_sha256,updated_at=now();
update public.penta_system_registry set version='1.1.0',metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('automated_ingestion',true,'ingest_queue','public.penta_context_ingest_queue_v1','ingest_worker_schedule','* * * * *','retry_strategy','exponential_capped_1h','dead_letter',true,'source_control_sync_pending',true),last_verified_at=now(),updated_at=now() where system_key='penta.context';
