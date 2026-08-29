-- Stagger the verified deadlock collision: the developer commerce reconciliation stays at minute 27;
-- the commercial release packager moves to minute 33 and becomes a PentaSELF-enforced invariant.
do $$
declare v_jobid bigint; v_command text;
begin
  select jobid,command into v_jobid,v_command from cron.job where jobname='crownthrive_commercial_release_packager_hourly' limit 1;
  if v_jobid is not null then
    perform cron.alter_job(v_jobid,schedule=>'33 * * * *',command=>v_command,active=>true);
    insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
    values('crownthrive_commercial_release_packager_hourly','33 * * * *',v_command,true,'D1',
      jsonb_build_object('owner','PentaSELF/PentaTime','prior_schedule','27 * * * *','collision_peer','developer_commerce_credit_reconcile_hourly','repair_reason','prevent recurring minute-27 deadlocks','authority_expansion',false))
    on conflict(jobname) do update set expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=true,risk_class='D1',metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=now();
  end if;
end $$;

-- Continuous healing and hourly healing reporting are themselves required jobs repaired by PentaSELF.
insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata) values
 ('ct-penta-self-continuous-healing-v1','1-59/2 * * * *','select public.penta_self_continuous_healing_tick_v1();',true,'D2',jsonb_build_object('owner','PentaSELF','contract','ct.penta.self.problem-ownership.v1','persistent',true)),
 ('penta-self-healing-hourly-v1','7 * * * *','select public.penta_self_hourly_report_v1();',true,'D1',jsonb_build_object('owner','PentaSELF/PentaMail','recipient','jones.usmc.kj@gmail.com','mandatory',true))
on conflict(jobname) do update set expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=true,risk_class=excluded.risk_class,metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=now();

do $$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-penta-self-continuous-healing-v1' limit 1;
  if v_jobid is null then perform cron.schedule('ct-penta-self-continuous-healing-v1','1-59/2 * * * *','select public.penta_self_continuous_healing_tick_v1();');
  else perform cron.alter_job(v_jobid,schedule=>'1-59/2 * * * *',command=>'select public.penta_self_continuous_healing_tick_v1();',active=>true); end if;
  select jobid into v_jobid from cron.job where jobname='penta-self-healing-hourly-v1' limit 1;
  if v_jobid is null then perform cron.schedule('penta-self-healing-hourly-v1','7 * * * *','select public.penta_self_hourly_report_v1();');
  else perform cron.alter_job(v_jobid,schedule=>'7 * * * *',command=>'select public.penta_self_hourly_report_v1();',active=>true); end if;
end $$;

-- Current independently observed problems are handed to PentaSELF immediately. External/D3 conditions remain fail-closed and persistently rechecked.
select penta_self.register_problem_v1('cron_failure','pg_cron','cron:crownthrive_commercial_release_packager_hourly','concurrency','critical','P1',
 'Commercial release packager deadlocked at minute 27','The commercial release packager and developer commerce reconciliation shared minute 27. The packager is staggered to minute 33 and must prove a later successful production run.',
 'PentaSELF/PentaTime','repair.commercial_packager_schedule.v1','D1','verification',true,null,
 jsonb_build_object('observed_at','2026-08-28T03:27:00Z','prior_schedule','27 * * * *','new_schedule','33 * * * *','collision_peer','developer_commerce_credit_reconcile_hourly','money_movement',false));

select penta_self.register_problem_v1('github_workflow','GitHub','github:run:33137524699','release','degraded','P1',
 'PentaRelease exact-head workflow failed on current main','Current main a12ce059d68a042665a1f1ec4d5f6e08bd69b478 has one failed PentaRelease Autonomous Release Awareness run. Release gates remain fail-closed; no bypass is authorized.',
 'PentaRelease/PentaBuild/PentaCertify','reconcile.release.via_pentarelease.v1','D2','detected',true,null,
 jsonb_build_object('head_sha','a12ce059d68a042665a1f1ec4d5f6e08bd69b478','run_id',33137524699,'gate_bypass',false,'provider_readback_required',true));

select penta_self.register_problem_v1('stripe_alert','Stripe','stripe:webhook:kjv-sermon-toolkit','provider_webhook','critical','P0',
 'KJV/Sermon Toolkit Stripe webhook returning HTTP 503','Stripe reported 185 failed deliveries. Provider retries were scheduled to stop September 1, 2026 at approximately 10:46 PM ET unless verified 2xx delivery is restored.',
 'PentaLiaison/PentaHook/PentaCertify','external.provider_recheck.v1','D2','blocked_external',true,'CERTIFIED_PROVIDER_ADAPTER_OR_SITE_REPAIR_REQUIRED',
 jsonb_build_object('attempts',185,'status_code',503,'provider_retry_deadline_et','2026-09-01T22:46:43-04:00','money_movement',false));

select penta_self.register_problem_v1('stripe_alert','Stripe','stripe:webhook:thrivetickets','provider_webhook','critical','P0',
 'ThriveTickets Stripe webhook returning HTTP 404','Stripe reported 191 failed deliveries. Provider retries were scheduled to stop September 1, 2026 at approximately 10:46 PM ET unless verified 2xx delivery is restored.',
 'PentaLiaison/PentaHook/PentaCertify','external.provider_recheck.v1','D2','blocked_external',true,'CERTIFIED_PROVIDER_ADAPTER_OR_SITE_REPAIR_REQUIRED',
 jsonb_build_object('attempts',191,'status_code',404,'provider_retry_deadline_et','2026-09-01T22:46:38-04:00','money_movement',false));

select penta_self.register_problem_v1('stripe_readback','Stripe','stripe:payout-rail:primary','payout','critical','P0',
 'Primary Stripe payout bank rail remains errored','Account-level payout capability is not independent proof of a functioning settlement rail. A provider recovery readback and bounded payout canary remain required.',
 'PentaLiaison/PentaCredentials/PentaSettle/PentaCertify','external.provider_recheck.v1','D2','blocked_external',true,'PROVIDER_OR_BANK_ACTION_AND_CERTIFIED_READBACK_REQUIRED',
 jsonb_build_object('account_capability_enabled',true,'bank_rail_state','errored','autonomous_money_movement',false));

select penta_self.register_problem_v1('evidence_gap','ThriveBase','thrivebase:stripe_event_receipts','provider_evidence','degraded','P1',
 'Stripe institutional event receipt ledger is empty','Successful event-driven fulfillment, entitlement, invoice, transfer, payout, and reconciliation ingestion is not institutionally proven until at least one verified receipt exists.',
 'PentaHook/PentaCertify/PentaLedger','external.provider_recheck.v1','D2','blocked_external',true,'END_TO_END_PROVIDER_EVENT_CANARY_REQUIRED',
 jsonb_build_object('receipt_count',(select count(*) from integration_control.stripe_event_receipts),'observed_at',now()));

select penta_self.register_problem_v1('evidence_gap','ThriveBase','thrivebase:paypal_webhook_receipts','provider_evidence','watch','P2',
 'PayPal end-to-end event receipt evidence is absent','PayPal OAuth and webhook-registration canaries passed, but end-to-end institutional event ingestion is not demonstrated by a receipt.',
 'PentaHook/PentaCertify/PentaLedger','external.provider_recheck.v1','D2','blocked_external',true,'END_TO_END_PROVIDER_EVENT_CANARY_REQUIRED',
 jsonb_build_object('receipt_count',(select count(*) from integration_control.paypal_webhook_receipts_v1),'observed_at',now()));

select penta_self.register_problem_v1('security_alert','GitGuardian','gitguardian:high-entropy-secret:0e967b1821','security','critical','P1',
 'GitGuardian high-entropy finding remains unresolved','The finding may be a false positive, but it remains unresolved until the provider records an explicit disposition. Raw secret material is not copied into PentaSELF evidence.',
 'PentaSecure/PentaCredentials/PentaCertify','external.provider_recheck.v1','D2','blocked_external',true,'GITGUARDIAN_PROVIDER_DISPOSITION_REQUIRED',
 jsonb_build_object('raw_secret_material_preserved',false,'provider_readback_required',true));

select penta_self.register_problem_v1('domain_alert','Vercel','vercel-domain:crownthrive.tech','domain','degraded','P1',
 'crownthrive.tech registrant email verification remains required','ICANN registrant verification is a provider/human action. PentaSELF retains the issue and rechecks it hourly without manufacturing identity or authority.',
 'PentaLiaison/PentaCredentials/Founder','external.human_action.v1','D3','blocked_d3',false,'HUMAN_REGISTRANT_EMAIL_VERIFICATION_REQUIRED',
 jsonb_build_object('domain','crownthrive.tech','d3_human_reserved',true));

select penta_self.register_problem_v1('projection_drift','Google Drive','drive:pentarelease-canonical-mirror','projection','degraded','P1',
 'Google Drive canonical release mirror trails GitHub','The Drive mirror reports v3.15.0.1 while GitHub has published v3.25.1.0. Human-readable projections must be regenerated from current canonical/provider evidence.',
 'PentaStatus/PentaScribe/PentaDocs','reconcile.projection.v1','D2','detected',true,null,
 jsonb_build_object('drive_version','v3.15.0.1','github_release','v3.25.1.0','authority_plane','projection_only'));

select penta_self.register_problem_v1('source_custody','Supabase/GitHub','custody:supabase-migrations','source_custody','critical','P1',
 'Supabase migration source custody remains on HOLD','Provider migration history remains ahead of fully reconstructable repository source. Ordered recovery, immutable placeholders where necessary, and non-production replay evidence remain required.',
 'PentaSerialized/PentaBuild/PentaCertify','reconcile.source_custody.v1','D2','detected',true,null,
 jsonb_build_object('provider_migration_count',(select count(*) from supabase_migrations.schema_migrations),'latest_provider_version',(select max(version) from supabase_migrations.schema_migrations),'production_history_rewrite',false));

select penta_self.register_problem_v1('projection_drift','crownthrive.com','public-phase-alignment','projection','degraded','P2',
 'Public rollout language and OS institutional phase remain conflated','The public ecosystem rollout may remain Phase 0, but it must be explicitly distinguished from CrownThrive OS canonical Phase 3 Execute and founder-declared Phase 3.5 convergence.',
 'PentaStatus/PentaScribe/PentaDocs','reconcile.projection.v1','D2','detected',true,null,
 jsonb_build_object('canonical_os_phase',3,'founder_operating_label','3.5','public_rollout_phase_requires_separate_field',true));

select penta_self.register_problem_v1('projection_drift','Google Sheets','sheets:pentamarketer-summary','projection','degraded','P2',
 'PentaMarketer summary contradicts its event ledger','Campaign Summary reports zero accepted sends while Targets and Events record an Outlook provider message. The append-only event ledger must drive the summary.',
 'PentaStatus/PentaScribe/PentaMarketer','reconcile.projection.v1','D2','detected,true,null,
 jsonb_build_object('summary_accepted_sends',0,'event_ledger_sends',1,'event_ledger_authoritative_for_projection',true));

select penta_self.register_problem_v1('catalog_drift','Stripe/Google Sheets','catalog:product-crosswalk','projection','degraded','P2',
 'Stripe products lack a complete governed candidate crosswalk','Stripe contains more than 100 active products while the 300-product candidate catalog remains commercial HOLD. Rights, price, tax, fulfillment, entitlement, accessibility, refund, brand, and release evidence require one canonical crosswalk.',
 'PentaGreen/PentaStatus/PentaScribe/PentaCertify','reconcile.projection.v1','D2','detected,true,null,
 jsonb_build_object('stripe_active_products','100+','candidate_catalog_rows',300,'candidate_catalog_state','HOLD'));

select penta_self.register_problem_v1('integration_gap','Gmail/Outlook','email:external-alert-ingestion','mail','degraded','P1',
 'External Gmail and Outlook alerts are not universally ingested into the institutional event fabric','PentaSELF can inspect every message that enters CrownThrive institutional event streams. PentaBuild/PentaCredentials must complete certified Gmail and Outlook inbound-alert adapters so external provider alerts cannot remain only in inbox or spam.',
 'PentaBuild/PentaCredentials/PentaMail/PentaLiaison",'repair.software.via_pentabuild.v1','D2','detected',true,null,
 jsonb_build_object('current_boundary','institutional_event_fabric','required_adapters',jsonb_build_array('Gmail inbound alert intake','Outlook inbox and spam alert intake'),'credential_manufacture',false));

select penta_self.register_problem_v1('self_observability','PentaSELF','pentaself:aggregate-health-masking','operational','critical','P1',
 'PentaSELF aggregate health could mask failed substeps','The prior aggregate state could remain healthy while an internal substep carried state=failed. Continuous intake now promotes every failed substep into durable problem ownership.',
 'PentaSELF/PentaStatus/PentaCertify','diagnose.generic.v1','D1','verification',true,null,
 jsonb_build_object('repair','latest cycle substeps independently inspected','aggregate_masking_prohibited',true));

-- Execute one bounded cycle now so the contract is proven before the migration returns.
select public.penta_self_continuous_healing_tick_v1();

revoke all on function penta_self.reject_append_only_mutation_v1() from public,anon,authenticated;
revoke all on function penta_self.problem_fingerprint_v1(text,text,text,text,text) from public,anon,authenticated;
revoke all on function penta_self.problem_category_v1(text,text,text,text,text) from public,anon,authenticated;
revoke all on function penta_self.problem_handler_for_v1(text,text,text,text,text) from public,anon,authenticated;
revoke all on function penta_self.message_is_problem_v1(text,text,text,text,jsonb) from public,anon,authenticated;
revoke all on function penta_self.register_problem_v1(text,text,text,text,text,text,text,text,text,text,text,text,boolean,text,jsonb,text) from public,anon,authenticated;
revoke all on function penta_self.message_intake_v1(uuid,integer) from public,anon,authenticated;
revoke all on function penta_self.problem_heal_cycle_v1(uuid,integer) from public,anon,authenticated;
revoke all on function penta_self.continuous_status_v1() from public,anon,authenticated;
revoke all on function penta_self.continuous_healing_tick_v1() from public,anon,authenticated;
revoke all on function public.penta_self_continuous_healing_tick_v1() from public,anon,authenticated;
revoke all on function public.penta_self_continuous_status_v1() from public,anon,authenticated;
revoke all on function public.penta_self_hourly_report_v1() from public,anon,authenticated;
grant execute on function public.penta_self_continuous_healing_tick_v1() to postgres,service_role;
grant execute on function public.penta_self_continuous_status_v1() to postgres,service_role;
grant execute on function public.penta_self_hourly_report_v1() to postgres,service_role;

do $$
begin
  perform pg_notify('pgrst','reload schema');
exception when others then null;
end $$;
