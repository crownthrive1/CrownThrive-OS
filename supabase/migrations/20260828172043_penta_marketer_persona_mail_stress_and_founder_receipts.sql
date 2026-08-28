create table if not exists integration_control.penta_marketer_persona_mail_test_v1 (
  evidence_id uuid primary key default gen_random_uuid(),
  run_id uuid not null,
  sequence_no integer not null check (sequence_no > 0),
  persona_id text not null references crm.penta_marketer_personas_v1(persona_id),
  agent_id text not null references crm.penta_marketer_agents_v2(agent_id),
  display_name text not null,
  role_title text not null,
  brand text not null,
  recipient text not null,
  work_id uuid references crm.penta_marketer_work_queue_v1(work_id),
  message_id uuid unique references public.penta_mail_outbox_v1(message_id),
  scheduled_at timestamptz not null,
  transport_state text not null default 'queued',
  provider_http_status integer,
  provider_message_id text,
  sent_at timestamptz,
  inbox_verified_at timestamptz,
  inbox_message_ref text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(run_id, persona_id)
);

alter table integration_control.penta_marketer_persona_mail_test_v1 enable row level security;
revoke all on integration_control.penta_marketer_persona_mail_test_v1 from public, anon, authenticated;
grant select, insert, update on integration_control.penta_marketer_persona_mail_test_v1 to service_role;
create index if not exists penta_marketer_persona_mail_test_v1_run_idx on integration_control.penta_marketer_persona_mail_test_v1(run_id, sequence_no);

create table if not exists integration_control.penta_mail_founder_receipt_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  source_message_id uuid not null unique references public.penta_mail_outbox_v1(message_id),
  receipt_message_id uuid unique references public.penta_mail_outbox_v1(message_id),
  founder_recipient text not null,
  source_recipient text not null,
  source_subject text not null,
  source_message_type text not null,
  source_persona_id text,
  source_agent_id text,
  source_provider_message_id text,
  source_sent_at timestamptz,
  cold_reach boolean not null default false,
  receipt_state text not null default 'queued',
  receipt_provider_message_id text,
  receipt_sent_at timestamptz,
  last_error text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table integration_control.penta_mail_founder_receipt_v1 enable row level security;
revoke all on integration_control.penta_mail_founder_receipt_v1 from public, anon, authenticated;
grant select, insert, update on integration_control.penta_mail_founder_receipt_v1 to service_role;
create index if not exists penta_mail_founder_receipt_v1_state_idx on integration_control.penta_mail_founder_receipt_v1(receipt_state, created_at);

create or replace function integration_control.penta_mail_founder_receipt_after_send_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control','crm'
as $$
declare
  v_founder text;
  v_receipt_id uuid;
  v_receipt_message uuid;
  v_persona text;
  v_agent text;
  v_display text;
  v_role text;
  v_cold boolean;
  v_subject text;
  v_body text;
begin
  if tg_op <> 'UPDATE' or new.state <> 'sent' or old.state = 'sent' then
    return new;
  end if;

  update integration_control.penta_marketer_persona_mail_test_v1
     set transport_state='sent',
         provider_http_status=new.provider_http_status,
         provider_message_id=new.provider_message_id,
         sent_at=new.sent_at,
         evidence=evidence||jsonb_build_object('provider_accepted',true,'transport_owner','PentaMail','copy_policy','ct.pentamailer.policy.universal-copy.v1'),
         updated_at=clock_timestamp()
   where message_id=new.message_id;

  update integration_control.penta_mail_founder_receipt_v1
     set receipt_state='sent',
         receipt_provider_message_id=new.provider_message_id,
         receipt_sent_at=new.sent_at,
         updated_at=clock_timestamp()
   where receipt_message_id=new.message_id;

  if lower(coalesce(new.metadata->>'skip_founder_receipt_trigger','false')) in ('true','1','yes')
     or lower(new.message_type)='founder_send_receipt' then
    return new;
  end if;

  v_founder:=public.penta_mail_notification_recipient_v1();
  v_persona:=coalesce(nullif(new.metadata->>'assigned_persona_id',''),'system');
  v_agent:=coalesce(nullif(new.metadata->>'assigned_agent_id',''),'system');
  v_display:=coalesce(nullif(new.metadata->>'assigned_display_name',''),nullif(new.metadata->>'from_name',''),'CrownThrive System');
  v_role:=coalesce(nullif(new.metadata->>'assigned_role_title',''),'System / Operational Sender');
  v_cold:=lower(coalesce(new.metadata->>'send_kind',''))='cold'
          or lower(new.message_type) in ('locticians_claim','sales_outreach','lead_nurture');

  insert into integration_control.penta_mail_founder_receipt_v1(
    source_message_id,founder_recipient,source_recipient,source_subject,source_message_type,
    source_persona_id,source_agent_id,source_provider_message_id,source_sent_at,cold_reach,receipt_state,evidence
  ) values(
    new.message_id,v_founder,new.recipient,new.subject,new.message_type,v_persona,v_agent,
    new.provider_message_id,new.sent_at,v_cold,'queued',
    jsonb_build_object('source_trigger_ref',new.trigger_ref,'campaign_ref',new.metadata->>'campaign_ref','transport_owner','PentaMail')
  ) on conflict(source_message_id) do nothing
  returning receipt_id into v_receipt_id;

  if v_receipt_id is null then
    return new;
  end if;

  v_subject:=left('[Executive Twin] Sent — '||new.subject,180);
  v_body:=concat_ws(E'\n',
    'Founder,',
    '',
    'PentaMail confirmed a provider-accepted outbound message.',
    '',
    'Sender persona: '||v_display,
    'Role: '||v_role,
    'Recipient: '||new.recipient,
    'Subject: '||new.subject,
    'Message type: '||new.message_type,
    'Cold reach: '||case when v_cold then 'YES' else 'NO' end,
    'Provider HTTP: '||coalesce(new.provider_http_status::text,'n/a'),
    'Provider message ID: '||coalesce(new.provider_message_id,'n/a'),
    'Sent at: '||coalesce(new.sent_at::text,clock_timestamp()::text),
    'Source message ID: '||new.message_id::text,
    '',
    'This is the non-recursive Executive Twin send receipt. The receipt itself is excluded from creating another receipt.',
    '',
    'V/R,',
    'Kavonte Executive Twin',
    'Founder Office Executive Twin',
    'CrownThrive, LLC'
  );

  v_receipt_message:=public.penta_mail_enqueue_v1(
    'founder_send_receipt','INFO',v_subject,v_body,
    'founder-send-receipt:'||new.message_id::text,
    jsonb_build_object(
      'trigger_ref','penta-mail:founder-send-receipt',
      'assigned_persona_id','ct.persona.crownthrive.executive-twin.kavonte.v1',
      'assigned_agent_id','ct.pentamarketer.agent.executive-twin',
      'assigned_display_name','Kavonte Executive Twin',
      'assigned_role_title','Founder Office Executive Twin',
      'founder_receipt_notification',true,
      'skip_founder_receipt_trigger',true,
      'source_message_id',new.message_id,
      'source_provider_message_id',new.provider_message_id,
      'send_kind','founder_receipt'
    ),
    v_founder
  );

  update integration_control.penta_mail_founder_receipt_v1
     set receipt_message_id=v_receipt_message,updated_at=clock_timestamp()
   where receipt_id=v_receipt_id;

  return new;
exception when others then
  if v_receipt_id is not null then
    update integration_control.penta_mail_founder_receipt_v1
       set receipt_state='failed',last_error=left(sqlerrm,1000),updated_at=clock_timestamp()
     where receipt_id=v_receipt_id;
  end if;
  return new;
end
$$;

revoke all on function integration_control.penta_mail_founder_receipt_after_send_v1() from public, anon, authenticated;
grant execute on function integration_control.penta_mail_founder_receipt_after_send_v1() to service_role;

drop trigger if exists penta_mail_founder_receipt_after_send_v1 on public.penta_mail_outbox_v1;
create trigger penta_mail_founder_receipt_after_send_v1
after update of state on public.penta_mail_outbox_v1
for each row
when (new.state='sent' and old.state is distinct from new.state)
execute function integration_control.penta_mail_founder_receipt_after_send_v1();

create or replace function crm.penta_marketer_queue_persona_intro_test_v1(
  p_recipient text default null,
  p_spacing_minutes integer default 20
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','integration_control'
as $$
declare
  v_founder text;
  v_run_id uuid:=gen_random_uuid();
  v_count integer;
  v_work_id uuid;
  v_message uuid;
  v_scheduled timestamptz;
  v_subject text;
  v_body text;
  v_dedupe text;
  r record;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;

  v_founder:=public.penta_mail_notification_recipient_v1();
  if p_recipient is not null and lower(btrim(p_recipient))<>lower(v_founder) then
    raise exception 'founder_test_recipient_required';
  end if;
  if coalesce(p_spacing_minutes,20) not between 15 and 60 then
    raise exception 'spacing_minutes_must_be_15_to_60';
  end if;

  select count(*) into v_count
  from crm.penta_marketer_personas_v1 p
  join crm.penta_marketer_agents_v2 a using(persona_id)
  where p.state='approved' and a.enabled and a.autonomous and a.state='active';

  if v_count=0 then raise exception 'no_active_personas'; end if;

  for r in
    select row_number() over(order by p.display_name,p.persona_id)::integer as seq,
           p.persona_id,p.display_name,p.role_title,p.brand,p.organization,p.disclosure,p.signature_template,
           a.agent_id,a.lane,a.primary_channel
    from crm.penta_marketer_personas_v1 p
    join crm.penta_marketer_agents_v2 a using(persona_id)
    where p.state='approved' and a.enabled and a.autonomous and a.state='active'
    order by p.display_name,p.persona_id
  loop
    v_work_id:=gen_random_uuid();
    v_scheduled:=clock_timestamp()+make_interval(mins => (r.seq-1)*p_spacing_minutes);
    v_dedupe:=left('persona-intro-test:'||v_run_id::text||':'||r.persona_id,240);
    v_subject:=left(format('[Persona Test %s/%s] %s — %s',lpad(r.seq::text,2,'0'),v_count,r.display_name,r.role_title),180);
    v_body:=concat_ws(E'\n',
      'Hello Kavonte,',
      '',
      'I’m '||r.display_name||', the '||r.role_title||' for '||r.brand||'.',
      'My PentaMarketer lane is '||r.lane||', and my registered primary channel is '||r.primary_channel||'.',
      '',
      coalesce(nullif(r.disclosure,''),'I am an AI-assisted CrownThrive operational persona working under CrownThrive governance and service standards.'),
      '',
      'This is a live PentaMarketer → PentaMail → Mailgun queue, identity, copy-policy, and reply-path stress test.',
      'Please reply when you see this message. Reply-To is governed through contact@crownthrive.com so the response can re-enter PentaMarketer intake.',
      '',
      'Test run: '||v_run_id::text,
      'Sequence: '||r.seq::text||' of '||v_count::text,
      'Persona ID: '||r.persona_id,
      'Agent ID: '||r.agent_id,
      '',
      'V/R,',
      r.display_name,
      r.role_title,
      coalesce(nullif(r.organization,''),'CrownThrive, LLC')
    );

    insert into crm.penta_marketer_work_queue_v1(
      work_id,dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,recipient,
      assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,authority_class,
      requires_founder_attention,state,payload
    ) values(
      v_work_id,v_dedupe,'penta-marketer-persona-test',v_run_id::text||':'||r.seq::text,'email',
      'persona_transport_test','persona_introduction_stress_test',left(v_subject,1000),v_founder,
      r.agent_id,r.persona_id,0,case when r.seq=1 then 60 else 20 end,'D1',false,'routed',
      jsonb_build_object('test_run_id',v_run_id,'sequence_no',r.seq,'scheduled_at',v_scheduled,'lane',r.lane,'primary_channel',r.primary_channel)
    );

    v_message:=public.penta_mail_enqueue_v1(
      'persona_intro_test',case when r.seq=1 then 'MEDIUM' else 'INFO' end,v_subject,v_body,v_dedupe,
      jsonb_build_object(
        'trigger_ref','penta-marketer:persona-intro-test',
        'origin_penta','PentaMarketer',
        'delivery_penta','PentaMail',
        'assigned_agent_id',r.agent_id,
        'assigned_persona_id',r.persona_id,
        'assigned_display_name',r.display_name,
        'assigned_role_title',r.role_title,
        'work_id',v_work_id,
        'persona_test_run_id',v_run_id,
        'persona_test_sequence',r.seq,
        'reply_expected',true,
        'reply_to','contact@crownthrive.com',
        'send_kind','persona_intro_test',
        'queue_spacing_minutes',p_spacing_minutes
      ),
      v_founder
    );

    update public.penta_mail_outbox_v1
       set available_at=v_scheduled,
           metadata=metadata||jsonb_build_object('scheduled_persona_test_at',v_scheduled),
           updated_at=clock_timestamp()
     where message_id=v_message;

    update crm.penta_marketer_work_queue_v1
       set penta_mail_message_id=v_message,state='queued',updated_at=clock_timestamp()
     where work_id=v_work_id;

    insert into integration_control.penta_marketer_persona_mail_test_v1(
      run_id,sequence_no,persona_id,agent_id,display_name,role_title,brand,recipient,work_id,message_id,scheduled_at,transport_state,evidence
    ) values(
      v_run_id,r.seq,r.persona_id,r.agent_id,r.display_name,r.role_title,r.brand,v_founder,v_work_id,v_message,v_scheduled,'queued',
      jsonb_build_object('transport_owner','PentaMail','control_plane','PentaMarketer','copy_policy','ct.pentamailer.policy.universal-copy.v1','reply_to','contact@crownthrive.com')
    );
  end loop;

  return jsonb_build_object(
    'ok',true,
    'run_id',v_run_id,
    'persona_count',v_count,
    'recipient',v_founder,
    'spacing_minutes',p_spacing_minutes,
    'first_scheduled_at',(select min(scheduled_at) from integration_control.penta_marketer_persona_mail_test_v1 where run_id=v_run_id),
    'last_scheduled_at',(select max(scheduled_at) from integration_control.penta_marketer_persona_mail_test_v1 where run_id=v_run_id),
    'transport_owner','PentaMail',
    'copy_policy','ct.pentamailer.policy.universal-copy.v1',
    'founder_receipt_trigger','integration_control.penta_mail_founder_receipt_after_send_v1'
  );
end
$$;

revoke all on function crm.penta_marketer_queue_persona_intro_test_v1(text,integer) from public, anon, authenticated;
grant execute on function crm.penta_marketer_queue_persona_intro_test_v1(text,integer) to service_role;

notify pgrst, 'reload schema';