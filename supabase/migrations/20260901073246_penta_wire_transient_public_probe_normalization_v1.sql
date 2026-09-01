DO $$
DECLARE
  v_sha text;
BEGIN
  SELECT encode(digest(pg_get_functiondef('integration_control.penta_wire_probe_public_v1()'::regprocedure),'sha256'),'hex') INTO v_sha;
  IF v_sha <> '3dd9ad80086bfc186bd71c167388c7221ae994ce040271418df9545330179844' THEN
    RAISE EXCEPTION 'PENTA_WIRE_PUBLIC_PROBE_PREDECESSOR_DIGEST_MISMATCH:%',v_sha;
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION integration_control.penta_wire_probe_public_v1()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'integration_control', 'extensions'
AS $function$
DECLARE
  b record;
  v_resp extensions.http_response;
  v_body text;
  v_state text;
  v_sha text;
  v_url_sha text;
  v_evidence jsonb;
  v_evidence_sha text;
  v_pass int:=0;
  v_hold int:=0;
  v_fail int:=0;
  v_total int:=0;
  v_transport_hold int:=0;
  v_transport_failure boolean:=false;
  v_transport_error_class text;
BEGIN
  FOR b IN
    SELECT *
    FROM integration_control.penta_wire_service_bindings_v1
    WHERE binding_state='active_probe'
      AND public_read_safe=true
      AND probe_method IN ('GET','HEAD')
      AND probe_url IS NOT NULL
    ORDER BY service_id
  LOOP
    v_total:=v_total+1;
    v_body:='';
    v_state:='fail';
    v_transport_failure:=false;
    v_transport_error_class:=null;

    BEGIN
      v_resp:=chlom_runtime.dail_http_v1((row(
        b.probe_method,
        b.probe_url,
        array[
          extensions.http_header('accept','application/json,text/html,*/*'),
          extensions.http_header('cache-control','no-cache, no-store'),
          extensions.http_header('user-agent','PentaWire-Public-Probe/1.0')
        ],
        null,
        null
      ))::extensions.http_request);
      v_body:=coalesce(v_resp.content,'');
      v_state:=case
        when v_resp.status between 200 and 399 then 'pass'
        when v_resp.status between 400 and 499 then 'hold'
        else 'fail'
      end;
    EXCEPTION WHEN OTHERS THEN
      v_resp:=null;
      v_body:=sqlstate||':'||sqlerrm;
      v_transport_failure:=true;
      IF lower(sqlerrm) LIKE '%timeout%'
         OR lower(sqlerrm) LIKE '%timed out%'
         OR lower(sqlerrm) LIKE '%failed to connect%'
         OR lower(sqlerrm) LIKE '%could not resolve host%'
         OR lower(sqlerrm) LIKE '%couldn''t resolve host%'
         OR lower(sqlerrm) LIKE '%connection refused%'
         OR lower(sqlerrm) LIKE '%network is unreachable%'
      THEN
        v_state:='hold';
        v_transport_error_class:='transient_network';
        v_transport_hold:=v_transport_hold+1;
      ELSE
        v_state:='fail';
        v_transport_error_class:='probe_execution_error';
      END IF;
    END;

    v_sha:=encode(extensions.digest(v_body,'sha256'),'hex');
    v_url_sha:=encode(extensions.digest(b.probe_url,'sha256'),'hex');
    v_evidence:=jsonb_build_object(
      'contract','ct.penta.wire.public-probe.v1',
      'service_id',b.service_id,
      'probe_method',b.probe_method,
      'probe_url_sha256',v_url_sha,
      'state',v_state,
      'http_status',case when v_resp is null then null else v_resp.status end,
      'content_type',case when v_resp is null then null else v_resp.content_type end,
      'response_sha256',v_sha,
      'response_body_stored',false,
      'credential_sent',false,
      'provider_write',false,
      'authority_effect','none',
      'transport_failure',v_transport_failure,
      'transport_error_class',v_transport_error_class,
      'observed_at',clock_timestamp()
    );
    v_evidence_sha:=encode(extensions.digest(v_evidence::text,'sha256'),'hex');

    INSERT INTO integration_control.penta_wire_probe_receipts_v1(
      service_id,probe_method,probe_url,probe_url_sha256,state,http_status,content_type,response_sha256,evidence,evidence_sha256,recorded_by_agent_id
    ) VALUES(
      b.service_id,b.probe_method,b.probe_url,v_url_sha,v_state,
      case when v_resp is null then null else v_resp.status end,
      case when v_resp is null then null else v_resp.content_type end,
      v_sha,v_evidence,v_evidence_sha,'ct.agent.penta-wire'
    );

    UPDATE integration_control.penta_wire_service_bindings_v1
    SET last_probe_state=v_state,
        last_http_status=case when v_resp is null then null else v_resp.status end,
        last_response_sha256=v_sha,
        last_observed_at=now(),
        updated_at=now()
    WHERE service_id=b.service_id;

    IF v_state='pass' THEN
      v_pass:=v_pass+1;
    ELSIF v_state='hold' THEN
      v_hold:=v_hold+1;
    ELSE
      v_fail:=v_fail+1;
    END IF;
  END LOOP;

  RETURN jsonb_build_object(
    'contract','ct.penta.wire.public-probe-cycle.v1',
    'total',v_total,
    'pass',v_pass,
    'hold',v_hold,
    'fail',v_fail,
    'transport_holds',v_transport_hold,
    'credential_sent',false,
    'response_body_stored',false,
    'provider_write',false,
    'authority_effect','none',
    'observed_at',clock_timestamp()
  );
END
$function$;

COMMENT ON FUNCTION integration_control.penta_wire_probe_public_v1() IS
  'Public-read-safe PentaWire probe cycle. Transient transport failures are scoped HOLD predicates; non-transport probe execution defects remain FAIL.';

DO $$
DECLARE
  v_def text:=pg_get_functiondef('integration_control.penta_wire_probe_public_v1()'::regprocedure);
BEGIN
  IF position('transient_network' in v_def)=0
     OR position('transport_holds' in v_def)=0
     OR position('probe_execution_error' in v_def)=0
  THEN
    RAISE EXCEPTION 'PENTA_WIRE_PUBLIC_PROBE_NORMALIZATION_VERIFY_FAILED';
  END IF;
END
$$;