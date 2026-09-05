-- ct.penta.pr-restack-owner-execution-surface.v1
-- Bounded exact-assignment executor for PR_RESTACK_CURRENT_MAIN handoffs.
-- No merge, predecessor close, certification, credential mutation, D3 action,
-- money movement, rights grant, vote/quorum effect, branch deletion, or authority expansion.

begin;

create table if not exists integration_control.penta_pr_restack_execution_receipts_v1 (
  assignment_id uuid primary key references integration_control.penta_assignment_contracts_v1(assignment_id),
  branch_name text not null unique,
  state text not null default 'RUNNING' check (state in ('RUNNING','HOLD','SUCCEEDED','FAILED')),
  hold_code text,
  provider_http_status integer,
  successor_pr_number bigint,
  successor_head_sha text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  completed_at timestamptz,
  check (successor_head_sha is null or successor_head_sha ~ '^[0-9a-f]{40}$')
);

alter table integration_control.penta_pr_restack_execution_receipts_v1 enable row level security;
alter table integration_control.penta_pr_restack_execution_receipts_v1 force row level security;
revoke all on integration_control.penta_pr_restack_execution_receipts_v1 from public, anon, authenticated;
grant select, insert, update on integration_control.penta_pr_restack_execution_receipts_v1 to service_role;

create or replace function integration_control.penta_pr_restack_execute_assignment_v1(p_assignment_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault,extensions,chlom_runtime,pg_temp
as $function$
declare
  a integration_control.penta_assignment_contracts_v1%rowtype;
  r integration_control.penta_pr_restack_execution_receipts_v1%rowtype;
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_repo constant text:='crownthrive1/CrownThrive-OS';
  v_owner constant text:='crownthrive1';
  v_token text;
  v_main extensions.http_response; v_pred extensions.http_response; v_files extensions.http_response;
  v_tree extensions.http_response; v_commit extensions.http_response; v_ref extensions.http_response;
  v_pr extensions.http_response; v_read extensions.http_response; v_existing extensions.http_response;
  v_main_body jsonb; v_pred_body jsonb; v_files_body jsonb; v_body jsonb; v_read_body jsonb;
  v_main_sha text; v_base_tree text; v_pred_head text; v_branch text; v_branch_q text;
  v_tree_entries jsonb; v_tree_sha text; v_successor_head text; v_pr_number bigint;
  v_event jsonb; v_status integer; v_hold text; v_changed integer;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:pr-restack:'||p_assignment_id::text,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','assignment_id',p_assignment_id,'authority_created',false);
  end if;

  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  if a.task_kind<>'PR_RESTACK_CURRENT_MAIN' then raise exception 'assignment_task_kind_forbidden'; end if;
  if a.source_repo is distinct from v_repo or a.source_pr_number is null or a.exact_head_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'exact_source_required';
  end if;
  if not a.provider_write_allowed then raise exception 'provider_write_forbidden'; end if;
  if a.risk_class not in ('D0','D1','D2') or a.authority_ceiling not in ('D0','D1','D2') then
    raise exception 'authority_ceiling_forbidden';
  end if;
  if a.d3_human_reserved is distinct from true or a.money_movement_allowed or a.credential_change_allowed or a.authority_expansion then
    raise exception 'assignment_guardrail_violation';
  end if;
  v_main_sha:=lower(coalesce(a.metadata->>'current_main_sha',''));
  if v_main_sha !~ '^[0-9a-f]{40}$' then raise exception 'assignment_current_main_required'; end if;
  v_branch:='penta/restack-pr'||a.source_pr_number::text||'-current-'||left(v_main_sha,7)||'-'||left(a.assignment_id::text,8);
  v_branch_q:=replace(v_branch,'/','%2F');

  insert into integration_control.penta_pr_restack_execution_receipts_v1(assignment_id,branch_name,state,evidence)
  values(a.assignment_id,v_branch,'RUNNING',jsonb_build_object(
    'contract','ct.penta.pr-terminalization-policy.v2','predecessor_preserved',true,
    'draft_successor_only',true,'merge_performed',false,'predecessor_close_performed',false,
    'certification_claimed',false,'D3_human_reserved',true,'authority_created',false))
  on conflict(assignment_id) do nothing;
  select * into r from integration_control.penta_pr_restack_execution_receipts_v1 where assignment_id=a.assignment_id for update;
  if r.state='SUCCEEDED' then
    return jsonb_build_object('state','SUCCEEDED_IDEMPOTENT','assignment_id',a.assignment_id,
      'successor_pr_number',r.successor_pr_number,'successor_head_sha',r.successor_head_sha,
      'branch_name',r.branch_name,'authority_created',false);
  end if;

  select decrypted_secret into v_token from vault.decrypted_secrets
  where name='APP_FACTORY_GITHUB_TOKEN' and nullif(decrypted_secret,'') is not null
  order by updated_at desc nulls last,created_at desc nulls last limit 1;
  if v_token is null then
    update integration_control.penta_pr_restack_execution_receipts_v1 set state='HOLD',hold_code='HOLD_GITHUB_PROVIDER_CREDENTIAL_UNAVAILABLE',updated_at=clock_timestamp() where assignment_id=a.assignment_id;
    return jsonb_build_object('state','HOLD','hold_code','HOLD_GITHUB_PROVIDER_CREDENTIAL_UNAVAILABLE','authority_created',false);
  end if;
  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','60000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','10000');

  -- Idempotent recovery if a prior attempt created the draft PR before receipt completion.
  select * into v_existing from chlom_runtime.dail_http_v1((
    'GET','https://api.github.com/repos/'||v_repo||'/pulls?state=open&head='||v_owner||':'||v_branch_q||'&base=main&per_page=10',
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],null,null
  )::extensions.http_request);
  if v_existing.status=200 and jsonb_typeof(coalesce(v_existing.content,'[]')::jsonb)='array' and jsonb_array_length(coalesce(v_existing.content,'[]')::jsonb)>0 then
    v_body:=(coalesce(v_existing.content,'[]')::jsonb)->0;
    v_pr_number:=nullif(v_body->>'number','')::bigint;
    v_successor_head:=v_body#>>'{head,sha}';
    if v_pr_number is not null and v_successor_head ~ '^[0-9a-f]{40}$' and coalesce((v_body->>'draft')::boolean,false) then
      update integration_control.penta_pr_restack_execution_receipts_v1
      set state='SUCCEEDED',successor_pr_number=v_pr_number,successor_head_sha=v_successor_head,provider_http_status=200,
          evidence=evidence||jsonb_build_object('idempotent_existing_successor',true,'provider_readback',true,'authority_created',false),completed_at=clock_timestamp(),updated_at=clock_timestamp()
      where assignment_id=a.assignment_id;
      perform extensions.http_reset_curlopt();
      return jsonb_build_object('state','SUCCEEDED','assignment_id',a.assignment_id,'successor_pr_number',v_pr_number,'successor_head_sha',v_successor_head,'branch_name',v_branch,'idempotent',true,'authority_created',false);
    end if;
  end if;

  select * into v_main from chlom_runtime.dail_http_v1((
    'GET','https://api.github.com/repos/'||v_repo||'/branches/main',
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],null,null
  )::extensions.http_request);
  if v_main.status<>200 then v_hold:='HOLD_GITHUB_MAIN_READBACK_FAILED'; v_status:=v_main.status; goto provider_hold; end if;
  v_main_body:=coalesce(v_main.content,'{}')::jsonb;
  if v_main_body#>>'{commit,sha}' is distinct from v_main_sha then v_hold:='HOLD_CURRENT_MAIN_DRIFT'; v_status:=200; goto provider_hold; end if;
  v_base_tree:=v_main_body#>>'{commit,commit,tree,sha}';
  if v_base_tree !~ '^[0-9a-f]{40}$' then v_hold:='HOLD_MAIN_TREE_READBACK_FAILED'; v_status:=200; goto provider_hold; end if;

  select * into v_pred from chlom_runtime.dail_http_v1((
    'GET','https://api.github.com/repos/'||v_repo||'/pulls/'||a.source_pr_number::text,
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],null,null
  )::extensions.http_request);
  if v_pred.status<>200 then v_hold:='HOLD_PREDECESSOR_READBACK_FAILED'; v_status:=v_pred.status; goto provider_hold; end if;
  v_pred_body:=coalesce(v_pred.content,'{}')::jsonb;
  if v_pred_body->>'state'<>'open' or coalesce((v_pred_body->>'merged')::boolean,false) then v_hold:='HOLD_PREDECESSOR_NOT_OPEN'; v_status:=200; goto provider_hold; end if;
  v_pred_head:=v_pred_body#>>'{head,sha}';
  if v_pred_head is distinct from a.exact_head_sha then v_hold:='HOLD_PREDECESSOR_HEAD_DRIFT'; v_status:=200; goto provider_hold; end if;

  select * into v_files from chlom_runtime.dail_http_v1((
    'GET','https://api.github.com/repos/'||v_repo||'/pulls/'||a.source_pr_number::text||'/files?per_page=100&page=1',
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],null,null
  )::extensions.http_request);
  if v_files.status<>200 then v_hold:='HOLD_PREDECESSOR_DIFF_READBACK_FAILED'; v_status:=v_files.status; goto provider_hold; end if;
  v_files_body:=coalesce(v_files.content,'[]')::jsonb;
  if jsonb_typeof(v_files_body)<>'array' or jsonb_array_length(v_files_body)=0 then v_hold:='HOLD_PREDECESSOR_ZERO_DELTA_RECLASSIFY'; v_status:=200; goto provider_hold; end if;
  if jsonb_array_length(v_files_body)>=100 then v_hold:='HOLD_RESTACK_DIFF_PAGINATION_REQUIRED'; v_status:=200; goto provider_hold; end if;
  v_changed:=jsonb_array_length(v_files_body);
  select jsonb_agg(jsonb_build_object('path',f->>'filename','mode','100644','type','blob','sha',case when f->>'status'='removed' then null else f->>'sha' end)) into v_tree_entries from jsonb_array_elements(v_files_body) f;

  select * into v_tree from chlom_runtime.dail_http_v1((
    'POST','https://api.github.com/repos/'||v_repo||'/git/trees',
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('Content-Type','application/json'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],
    'application/json',jsonb_build_object('base_tree',v_base_tree,'tree',v_tree_entries)::text
  )::extensions.http_request);
  if v_tree.status<>201 then v_hold:='HOLD_RESTACK_TREE_CREATE_FAILED'; v_status:=v_tree.status; goto provider_hold; end if;
  v_tree_sha:=(coalesce(v_tree.content,'{}')::jsonb)->>'sha';

  select * into v_commit from chlom_runtime.dail_http_v1((
    'POST','https://api.github.com/repos/'||v_repo||'/git/commits',
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('Content-Type','application/json'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],
    'application/json',jsonb_build_object('message','chore(pentapr): restack #'||a.source_pr_number::text||' on current main'||E'\n\nAssignment: '||a.assignment_id::text||E'\nPredecessor head: '||a.exact_head_sha||E'\nBase: '||v_main_sha||E'\nAuthority created: false','tree',v_tree_sha,'parents',jsonb_build_array(v_main_sha))::text
  )::extensions.http_request);
  if v_commit.status<>201 then v_hold:='HOLD_RESTACK_COMMIT_CREATE_FAILED'; v_status:=v_commit.status; goto provider_hold; end if;
  v_successor_head:=(coalesce(v_commit.content,'{}')::jsonb)->>'sha';

  select * into v_ref from chlom_runtime.dail_http_v1((
    'POST','https://api.github.com/repos/'||v_repo||'/git/refs',
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('Content-Type','application/json'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],
    'application/json',jsonb_build_object('ref','refs/heads/'||v_branch,'sha',v_successor_head)::text
  )::extensions.http_request);
  if v_ref.status<>201 then v_hold:='HOLD_RESTACK_BRANCH_CREATE_FAILED'; v_status:=v_ref.status; goto provider_hold; end if;

  select * into v_pr from chlom_runtime.dail_http_v1((
    'POST','https://api.github.com/repos/'||v_repo||'/pulls',
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('Content-Type','application/json'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],
    'application/json',jsonb_build_object('title','chore(pentapr): restack #'||a.source_pr_number::text||' on current main','head',v_branch,'base','main','draft',true,'maintainer_can_modify',true,
      'body','PR-v2 draft successor generated from exact governed assignment '||a.assignment_id::text||'. Predecessor #'||a.source_pr_number::text||' @ '||a.exact_head_sha||'; current main '||v_main_sha||'. Predecessor history is preserved. No inherited PASS/review/certificate/merge/deploy/D3/rights authority. Authority created: false.')::text
  )::extensions.http_request);
  if v_pr.status<>201 then v_hold:='HOLD_RESTACK_PR_CREATE_FAILED'; v_status:=v_pr.status; goto provider_hold; end if;
  v_pr_number:=nullif((coalesce(v_pr.content,'{}')::jsonb)->>'number','')::bigint;

  select * into v_read from chlom_runtime.dail_http_v1((
    'GET','https://api.github.com/repos/'||v_repo||'/pulls/'||v_pr_number::text,
    array[extensions.http_header('Authorization','Bearer '||v_token),extensions.http_header('Accept','application/vnd.github+json'),extensions.http_header('X-GitHub-Api-Version','2022-11-28'),extensions.http_header('User-Agent','CrownThrive-PentaPR-Restack/1.0')],null,null
  )::extensions.http_request);
  if v_read.status<>200 then v_hold:='HOLD_RESTACK_PR_READBACK_FAILED'; v_status:=v_read.status; goto provider_hold; end if;
  v_read_body:=coalesce(v_read.content,'{}')::jsonb;
  if v_read_body->>'state'<>'open' or not coalesce((v_read_body->>'draft')::boolean,false)
     or v_read_body#>>'{head,sha}' is distinct from v_successor_head or v_read_body#>>'{base,ref}' is distinct from 'main' then
    v_hold:='HOLD_RESTACK_PR_READBACK_FAILED'; v_status:=200; goto provider_hold;
  end if;

  update integration_control.penta_pr_restack_execution_receipts_v1
  set state='SUCCEEDED',hold_code=null,provider_http_status=200,successor_pr_number=v_pr_number,successor_head_sha=v_successor_head,
      evidence=evidence||jsonb_build_object('changed_files',v_changed,'base_main_sha',v_main_sha,'predecessor_head_sha',a.exact_head_sha,'provider_readback',true,'predecessor_preserved',true,'merge_performed',false,'predecessor_close_performed',false,'certification_claimed',false,'authority_created',false),
      completed_at=clock_timestamp(),updated_at=clock_timestamp()
  where assignment_id=a.assignment_id;
  v_event:=chlom_runtime.append_dail_event('penta.pr.restack.owner_execution.succeeded','penta_assignment',a.assignment_id::text,
    jsonb_build_object('source_repo',v_repo,'source_pr_number',a.source_pr_number,'predecessor_head_sha',a.exact_head_sha,'base_main_sha',v_main_sha,'successor_pr_number',v_pr_number,'successor_head_sha',v_successor_head,'successor_branch',v_branch,'changed_files',v_changed,'predecessor_preserved',true,'merge_performed',false,'predecessor_close_performed',false,'certification_claimed',false,'D3_human_reserved',true,'authority_created',false),
    'PentaPR/PentaMerge/PentaPM',null,'PentaPR','1.0.0','ctcorr:penta-pr-restack:'||a.assignment_id::text,null,'ct.penta.pr-terminalization-policy.v2',null,'internal');
  perform extensions.http_reset_curlopt();
  return jsonb_build_object('state','SUCCEEDED','assignment_id',a.assignment_id,'successor_pr_number',v_pr_number,'successor_head_sha',v_successor_head,'branch_name',v_branch,'changed_files',v_changed,'dail',v_event,'authority_created',false);

  <<provider_hold>>
  update integration_control.penta_pr_restack_execution_receipts_v1
  set state='HOLD',hold_code=v_hold,provider_http_status=v_status,evidence=evidence||jsonb_build_object('hold_code',v_hold,'provider_http_status',v_status,'observed_at',clock_timestamp(),'authority_created',false),updated_at=clock_timestamp()
  where assignment_id=a.assignment_id;
  perform extensions.http_reset_curlopt();
  return jsonb_build_object('state','HOLD','assignment_id',a.assignment_id,'hold_code',v_hold,'provider_http_status',v_status,'branch_name',v_branch,'authority_created',false);
exception when others then
  perform extensions.http_reset_curlopt();
  raise;
end
$function$;

create or replace function integration_control.penta_pr_restack_mobilize_v1(p_limit integer default 20)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control
as $function$
declare
  h record; v_limit integer:=greatest(1,least(coalesce(p_limit,20),100));
  v_result jsonb; v_seen uuid[]:='{}'::uuid[]; v_success integer:=0; v_holds integer:=0;
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role' then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:pr-restack-mobilize:v1',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','success',0,'holds',0,'authority_created',false);
  end if;
  for h in
    select x.handoff_key,x.discovery_key,x.risk_class,x.payload,
      nullif(x.payload->>'assignment_id','')::uuid as assignment_id
    from integration_control.penta_census_handoffs_v1 x
    where x.tag='assignment:PR_RESTACK_CURRENT_MAIN' and x.state in ('queued','failed') and x.risk_class in ('D0','D1','D2')
      and nullif(x.payload->>'assignment_id','') is not null
    order by x.created_at for update skip locked limit v_limit
  loop
    if h.assignment_id=any(v_seen) then continue; end if;
    v_seen:=array_append(v_seen,h.assignment_id);
    v_result:=integration_control.penta_pr_restack_execute_assignment_v1(h.assignment_id);
    if v_result->>'state' in ('SUCCEEDED','SUCCEEDED_IDEMPOTENT') then
      update integration_control.penta_census_handoffs_v1 set state='acknowledged',payload=payload||jsonb_build_object('restack_execution',v_result,'authority_created',false),updated_at=now()
      where discovery_key=h.discovery_key and tag='assignment:PR_RESTACK_CURRENT_MAIN' and risk_class in ('D0','D1','D2');
      v_success:=v_success+1;
    else
      update integration_control.penta_census_handoffs_v1 set state='failed',payload=payload||jsonb_build_object('restack_execution',v_result,'authority_created',false),updated_at=now()
      where discovery_key=h.discovery_key and tag='assignment:PR_RESTACK_CURRENT_MAIN' and risk_class in ('D0','D1','D2');
      v_holds:=v_holds+1;
    end if;
  end loop;
  return jsonb_build_object('state',case when v_holds>0 then 'SUCCESS_HOLD' else 'SUCCESS_PROGRESS' end,'assignments_seen',coalesce(array_length(v_seen,1),0),'success',v_success,'holds',v_holds,'D3_executed',false,'authority_created',false,'observed_at',clock_timestamp());
end
$function$;

comment on function integration_control.penta_pr_restack_execute_assignment_v1(uuid) is
  'Exact D0-D2 PR_RESTACK_CURRENT_MAIN provider executor. Draft successor only; predecessor terminalization, merge, review and certification remain separate.';
comment on function integration_control.penta_pr_restack_mobilize_v1(integer) is
  'Consumes only routed D0-D2 PR_RESTACK_CURRENT_MAIN Census handoffs and invokes the bounded exact-assignment provider executor once per assignment.';

commit;
