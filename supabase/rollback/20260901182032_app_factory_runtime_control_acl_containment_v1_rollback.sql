-- Fail-closed recovery contract for App Factory runtime-control provider dispatcher ACL containment v1.
-- The incident-observed end-user ACL is a known security defect and is never restored.
-- Recovery is exact-definition-bound and reasserts service-role-only execution.

DO $preflight$
DECLARE
  v_sig text;
  v_oid oid;
  v_expected_sha text;
  v_actual_sha text;
BEGIN
  FOR v_sig, v_expected_sha IN
    SELECT * FROM (VALUES
      ('public.app_factory_android_closeout_dispatch(text)', '73fdbfd341ed5ed84b57e982b67c9ada53025d62cc5fd5b7ee164c699f3ac97a'),
      ('public.app_factory_dcv_control_dispatch(text)', '1f2e3d9bebe6732efc7230333e128bb14fdbd84d6cd775b66bd52fb8fe105731'),
      ('public.app_factory_root_route_dispatch()', '0d62beb998f4b7de4874c1ac6d4bb2dbcfc73214d8513eb4ed0a0f7e96e0cc45'),
      ('public.app_factory_runtime_evidence_dispatch(text)', '7c01fd5730c13997ec25c1d0569c452a7731d1b8fe9c504cf5e880dbef16bdc7')
    ) AS t(sig, expected_sha)
  LOOP
    v_oid := to_regprocedure(v_sig);
    IF v_oid IS NULL THEN
      RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_RUNTIME_CONTROL_RPC_NOT_FOUND:%',v_sig;
    END IF;
    SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex') INTO v_actual_sha;
    IF v_actual_sha <> v_expected_sha THEN
      RAISE EXCEPTION 'ROLLBACK_REFUSES_CHANGED_APP_FACTORY_RUNTIME_CONTROL_RPC:%:%',v_sig,v_actual_sha;
    END IF;
  END LOOP;
END
$preflight$;

REVOKE ALL ON FUNCTION public.app_factory_android_closeout_dispatch(text) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_android_closeout_dispatch(text) TO service_role;
REVOKE ALL ON FUNCTION public.app_factory_dcv_control_dispatch(text) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_dcv_control_dispatch(text) TO service_role;
REVOKE ALL ON FUNCTION public.app_factory_root_route_dispatch() FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_root_route_dispatch() TO service_role;
REVOKE ALL ON FUNCTION public.app_factory_runtime_evidence_dispatch(text) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_runtime_evidence_dispatch(text) TO service_role;

DO $readback$
DECLARE
  v_sig text;
BEGIN
  FOREACH v_sig IN ARRAY ARRAY[
    'public.app_factory_android_closeout_dispatch(text)',
    'public.app_factory_dcv_control_dispatch(text)',
    'public.app_factory_root_route_dispatch()',
    'public.app_factory_runtime_evidence_dispatch(text)'
  ]
  LOOP
    IF has_function_privilege('anon',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_RUNTIME_CONTROL_RPC_ANON_EXECUTE_PRESENT:%',v_sig;
    END IF;
    IF has_function_privilege('authenticated',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_RUNTIME_CONTROL_RPC_AUTHENTICATED_EXECUTE_PRESENT:%',v_sig;
    END IF;
    IF NOT has_function_privilege('service_role',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_RUNTIME_CONTROL_RPC_SERVICE_EXECUTE_MISSING:%',v_sig;
    END IF;
  END LOOP;
END
$readback$;
