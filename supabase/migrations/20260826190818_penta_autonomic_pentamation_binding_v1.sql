with d as (
  select jsonb_build_object(
    'contract','ct.penta.autonomic-incident-response.v1',
    'schedule','*/5 * * * *',
    'steps',jsonb_build_array(
      'PentaFlagger.detect','PentaTagger.route','PentaHarvestor.capture','PentaNotifs.notify',
      'PentaBackup.checkpoint','PentaBlue.remediate','PentaRed.verify','PentaReports.aar','PentaMail.deliver'
    ),
    'fail_closed',true,
    'economic_authority',false,
    'destructive_authority',false,
    'registered_handler','penta.pentagreen.23514.candidate-identity.v1'
  ) as body
)
insert into public.penta_mation_workflows(workflow_id,version,status,trigger_type,risk_class,authority_ref,owner_ref,definition,definition_sha256,schema_version)
select 'penta.autonomic.incident-response',1,'active','schedule','D2','founder-directive:penta-autonomic-operations-2026-08-26','penta.mation',body,
       encode(extensions.digest(body::text,'sha256'),'hex'),'1'
from d
on conflict(workflow_id,version) do update set status=excluded.status,trigger_type=excluded.trigger_type,
 risk_class=excluded.risk_class,authority_ref=excluded.authority_ref,owner_ref=excluded.owner_ref,
 definition=excluded.definition,definition_sha256=excluded.definition_sha256,updated_at=now();
