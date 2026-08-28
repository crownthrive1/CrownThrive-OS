-- CrownThrive OS / PentaMarketer
-- Production convergence for the Locticians Sponsored Articles publisher.
-- Publisher reconcile work is created only when an actual eligible draft exists.
-- Text-only articles do not require image evidence; images require verified rights.
-- Brilliant Directories DELETE remains D3 / human-reserved.

create or replace function crm.penta_marketer_growth_factory_seed_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public'
as $function$
declare
  v_now timestamptz:=clock_timestamp();
  v_local timestamp:=v_now at time zone 'America/New_York';
  v_hour text;
  v_two_hour text;
  v_six_hour text;
  v_ten_min text;
  v_day text;
  v_inserted integer:=0;
  v_n integer;
  v_publish_candidates integer:=0;
  v_publish_ticks_reconciled integer:=0;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;

  v_hour:=to_char(date_trunc('hour',v_local),'YYYYMMDDHH24');
  v_two_hour:=to_char(
    date_trunc('hour',v_local)-make_interval(hours=>mod(extract(hour from v_local)::integer,2)),
    'YYYYMMDDHH24'
  );
  v_six_hour:=to_char(
    date_trunc('hour',v_local)-make_interval(hours=>mod(extract(hour from v_local)::integer,6)),
    'YYYYMMDDHH24'
  );
  v_ten_min:=to_char(
    date_trunc('hour',v_local)+make_interval(mins=>(extract(minute from v_local)::integer/10)*10),
    'YYYYMMDDHH24MI'
  );
  v_day:=to_char(v_local::date,'YYYYMMDD');

  insert into crm.penta_marketer_work_queue_v1(
    dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,
    assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,
    authority_class,requires_founder_attention,state,payload
  ) values (
    'locticians:seo-gap:'||v_six_hour,
    'penta-marketer-growth-factory',v_six_hour,'internal','content_research',
    'locticians_seo_gap_scan',
    'Inspect Locticians for empty/weak categories, stale content, location gaps, and search-intent opportunities. Produce evidence-backed candidates only.',
    'ct.pentamarketer.agent.research','ct.persona.locticians.research.devin.v1',
    65,45,'D1',false,'routed',
    jsonb_build_object(
      'brand','Locticians','member_id',5,
      'factory','ct.pentamarketer.locticians-growth.v1','cadence','6h',
      'image_rights_rule','required_when_image_present',
      'provider_write_authority',false
    )
  ) on conflict(dedupe_key) do nothing;
  get diagnostics v_n=row_count;
  v_inserted:=v_inserted+v_n;

  insert into crm.penta_marketer_work_queue_v1(
    dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,
    assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,
    authority_class,requires_founder_attention,state,payload
  ) values (
    'locticians:editorial-refresh:'||v_two_hour,
    'penta-marketer-growth-factory',v_two_hour,'internal','content_media',
    'seo_editorial_refresh',
    'Develop SEO-optimized editorial refresh candidates for Locticians using verified category/search gaps. Require image provenance when an image is selected.',
    'ct.pentamarketer.agent.community-editor','ct.persona.locticians.community-editor.jordan.v1',
    70,50,'D1',false,'routed',
    jsonb_build_object(
      'brand','Locticians','member_id',5,
      'factory','ct.pentamarketer.locticians-growth.v1','cadence','2h',
      'seo_experiment',true,
      'image_rights_rule','required_when_image_present',
      'provider_write_authority',false
    )
  ) on conflict(dedupe_key) do nothing;
  get diagnostics v_n=row_count;
  v_inserted:=v_inserted+v_n;

  select count(*)::integer into v_publish_candidates
  from public.chlom_article_drafts d
  join public.chlom_publication_work_items w on w.id=d.work_item_id
  where d.workflow_key='ct.pentamarketer.locticians-sponsored-articles.v1'
    and d.state in ('VERIFIED','QUEUED_FOR_PUBLICATION')
    and w.state in ('NEXT','IN_PROGRESS','NEEDS_REVIEW')
    and coalesce((d.source_basis->>'image_present')::boolean,false)=false
       or (
         d.workflow_key='ct.pentamarketer.locticians-sponsored-articles.v1'
         and d.state in ('VERIFIED','QUEUED_FOR_PUBLICATION')
         and w.state in ('NEXT','IN_PROGRESS','NEEDS_REVIEW')
         and coalesce((d.source_basis->>'image_present')::boolean,false)=true
         and d.source_basis->>'image_rights_state'='verified'
       );

  if v_publish_candidates>0 then
    insert into crm.penta_marketer_work_queue_v1(
      dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,
      assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,
      authority_class,requires_founder_attention,state,payload
    ) values (
      'locticians:publish-reconcile:'||v_ten_min,
      'penta-marketer-growth-factory',v_ten_min,'internal','content_publish',
      'locticians_publish_candidate',
      'Advance eligible Locticians content candidates through governed publication and destination readback; reconcile provider backlog before generating duplicates.',
      'ct.pentamarketer.agent.publisher','ct.persona.locticians.publisher.kiara.v1',
      75,65,'D2',false,'routed',
      jsonb_build_object(
        'brand','Locticians','member_id',5,
        'factory','ct.pentamarketer.locticians-growth.v1','cadence','10m',
        'eligible_candidate_count',v_publish_candidates,
        'destination_readback_required',true,
        'image_rights_rule','required_when_image_present',
        'provider_write_authority','bridge_only'
      )
    ) on conflict(dedupe_key) do nothing;
    get diagnostics v_n=row_count;
    v_inserted:=v_inserted+v_n;
  else
    update crm.penta_marketer_work_queue_v1 q
    set state='cancelled',
        payload=coalesce(q.payload,'{}'::jsonb)||jsonb_build_object(
          'reconciliation_action','no_eligible_publication_candidate',
          'eligible_candidate_count',0,
          'provider_write_executed',false,
          'image_rights_rule','required_when_image_present',
          'reconciled_at',v_now
        ),
        updated_at=v_now
    where q.purpose='locticians_publish_candidate'
      and q.assigned_persona_id='ct.persona.locticians.publisher.kiara.v1'
      and q.state in ('routed','queued');
    get diagnostics v_publish_ticks_reconciled=row_count;
  end if;

  insert into crm.penta_marketer_work_queue_v1(
    dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,
    assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,
    authority_class,requires_founder_attention,state,payload
  ) values (
    'locticians:newsletter:'||v_day,
    'penta-marketer-growth-factory',v_day,'internal','newsletter',
    'newsletter_nurture',
    'Prepare the current Locticians newsletter/nurture package from verified content and commercial evidence. Delivery audience must be relationship/consent scoped and suppression-cleared.',
    'ct.pentamarketer.agent.newsletter','ct.persona.locticians.newsletter.nia.v1',
    75,55,'D1',false,'routed',
    jsonb_build_object(
      'brand','Locticians','factory','ct.pentamarketer.locticians-growth.v1',
      'cadence','daily','delivery_transport','PentaMail',
      'cold_list_conversion_forbidden',true,'suppression_required',true
    )
  ) on conflict(dedupe_key) do nothing;
  get diagnostics v_n=row_count;
  v_inserted:=v_inserted+v_n;

  insert into crm.penta_marketer_work_queue_v1(
    dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,
    assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,
    authority_class,requires_founder_attention,state,payload
  ) values (
    'locticians:growth-opt:'||v_hour,
    'penta-marketer-growth-factory',v_hour,'internal','marketing_campaign',
    'growth_campaign_optimization',
    'Review cold outreach, newsletter, content distribution, SEO, conversion, complaint, suppression, and provider signals; optimize the governed growth mix toward the revenue target.',
    'ct.pentamarketer.agent.campaign','ct.persona.locticians.campaign.talia.v1',
    85,60,'D1',false,'routed',
    jsonb_build_object(
      'brand','Locticians','factory','ct.pentamarketer.locticians-growth.v1',
      'cadence','hourly','revenue_goal_usd',100000,
      'provider_write_authority',false,'no_invented_conversions',true
    )
  ) on conflict(dedupe_key) do nothing;
  get diagnostics v_n=row_count;
  v_inserted:=v_inserted+v_n;

  return jsonb_build_object(
    'status','ok',
    'inserted',v_inserted,
    'at',v_now,
    'factory','ct.pentamarketer.locticians-growth.v1',
    'eligible_publish_candidates',v_publish_candidates,
    'stale_publish_ticks_reconciled',v_publish_ticks_reconciled,
    'publish_tick_created',v_publish_candidates>0,
    'image_rights_rule','required_when_image_present',
    'd3_auto',false
  );
end
$function$;

comment on function crm.penta_marketer_growth_factory_seed_v1() is
'Locticians growth-factory seed. Research/editorial/newsletter/campaign lanes remain scheduled. Publisher reconcile work is created only when an actual verified or queued Locticians draft exists and image-rights evidence passes when an image is present; otherwise stale publisher ticks are reconciled to no-op.';
