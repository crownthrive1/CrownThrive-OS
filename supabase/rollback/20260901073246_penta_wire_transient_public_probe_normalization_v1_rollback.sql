CREATE OR REPLACE FUNCTION integration_control.penta_wire_probe_public_v1()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'integration_control', 'extensions'
AS $function$
declare
 b record; v_resp extensions.http_response; v_body text; v_state text; v_sha text; v_url_sha text; v_evidence jsonb; v_evidence_sha text;
 v_pass int:=0; v_hold int:=0; v_fail int:=0; v_total int:=0;
begin
 for b in select * from integration_control.penta_wire_service_bindings_v1 where binding_state='active_probe' and public_read_safe=true and probe_method in ('GET','HEAD') and probe_url is not null order by service_id
 loop
  v_total:=v_total+1; v_body:=''; v_state:='fail';
  begin
   v_resp:=chlom_runtime.dail_http_v1((row(b.probe_method,b.probe_url,array[
     extensions.http_header('accept','application/json,text/html,*/*'),
     extensions.http_header('cache-control','no-cache, no-store'),
     extensions.http_header('user-agent','PentaWire-Public-Probe/1.0')],null,null))::extensions.http_request);
   v_body:=coalesce(v_resp.content,'');
   v_state:=case when v_resp.status between 200 and 399 then 'pass' when v_resp.status between 400 and 499 then 'hold' else 'fail' end;
  exception when others then
   v_resp:=null; v_body:=sqlstate||':'||sqlerrm; v_state:='fail';
  end;
  v_sha:=encode(extensions.digest(v_body,'sha256'),'hex');
  v_url_sha:=encode(extensions.digest(b.probe_url,'sha256'),'hex');
  v_evidence:=jsonb_build_object('contract','ct.penta.wire.public-probe.v1','service_id',b.service_id,'probe_method',b.probe_method,
    'probe_url_sha256',v_url_sha,'state',v_state,'http_status',case when v_resp is null then null else v_resp.status end,
    'content_type',case when v_resp is null then null else v_resp.content_type end,'response_sha256',v_sha,
    'response_body_stored',false,'credential_sent',false,'provider_write',false,'authority_effect','none','observed_at',clock_timestamp());
  v_evidence_sha:=encode(extensions.digest(v_evidence::text,'sha256'),'hex');
  insert into integration_control.penta_wire_probe_receipts_v1(service_id,probe_method,probe_url,probe_url_sha256,state,http_status,content_type,response_sha256,evidence,evidence_sha256,recorded_by_agent_id)
  values(b.service_id,b.probe_method,b.probe_url,v_url_sha,v_state,case when v_resp is null then null else v_resp.status end,case when v_resp is null then null else v_resp.content_type end,v_sha,v_evidence,v_evidence_sha,'ct.agent.penta-wire');
  update integration_control.penta_wire_service_bindings_v1 set last_probe_state=v_state,last_http_status=case when v_resp is null then null else v_resp.status end,
    last_response_sha256=v_sha,last_observed_at=now(),updated_at=now() where service_id=b.service_id;
  if v_state='pass' then v_pass:=v_pass+1; elsif v_state='hold' then v_hold:=v_hold+1; else v_fail:=v_fail+1; end if;
 end loop;
 return jsonb_build_object('contract','ct.penta.wire.public-probe-cycle.v1','total',v_total,'pass',v_pass,'hold',v_hold,'fail',v_fail,
  'credential_sent',false,'response_body_stored',false,'provider_write',false,'authority_effect','none','observed_at',clock_timestamp());
end $function$;

COMMENT ON FUNCTION integration_control.penta_wire_probe_public_v1() IS NULL;
