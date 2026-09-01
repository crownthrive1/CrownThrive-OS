-- Fail-closed recovery contract for App Factory provider-control dispatch RPC hardening v1.
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
      ('public.app_factory_operational_cleanup_dispatch(text)', 'b1db1dfd098ea8553e9ecf4b8896b14c565cbd1d171bf46863576b1e11305a59'),
      ('public.app_factory_ssl_control_dispatch(text)', '5a85557bc1a27317920fae869dddddd24e042f9342b3c4e75ebb1c615c060a79'),
      ('public.app_factory_docroot_control_dispatch(text)', '78ecf659712ff65755664bff5a7738a3d77e0db4a4f4cab09e0a0f2026625827'),
      ('public.app_factory_storage_repair_dispatch(text)', '4581b2893095468929def1ed00e7c755a8dd85a4f7b5a42bbc4f9549ae9cfd57')
    ) AS t(sig, expected_sha)
  LOOP
    v_oid := to_regprocedure(v_sig);
    IF v_oid IS NULL THEN
      RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_RPC_NOT_FOUND:%',v_sig;
    END IF;
    SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex') INTO v_actual_sha;
    IF v_actual_sha <> v_expected_sha THEN
      RAISE EXCEPTION 'ROLLBACK_REFUSES_CHANGED_APP_FACTORY_PROVIDER_DISPATCH_RPC:%:%',v_sig,v_actual_sha;
    END IF;
  END LOOP;
END
$preflight$;

REVOKE ALL ON FUNCTION public.app_factory_operational_cleanup_dispatch(text)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_operational_cleanup_dispatch(text) TO service_role;
REVOKE ALL ON FUNCTION public.app_factory_ssl_control_dispatch(text)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_ssl_control_dispatch(text) TO service_role;
REVOKE ALL ON FUNCTION public.app_factory_docroot_control_dispatch(text)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_docroot_control_dispatch(text) TO service_role;
REVOKE ALL ON FUNCTION public.app_factory_storage_repair_dispatch(text)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_storage_repair_dispatch(text) TO service_role;

DO $readback$
DECLARE
  v_sig text;
BEGIN
  FOREACH v_sig IN ARRAY ARRAY[
    'public.app_factory_operational_cleanup_dispatch(text)',
    'public.app_factory_ssl_control_dispatch(text)',
    'public.app_factory_docroot_control_dispatch(text)',
    'public.app_factory_storage_repair_dispatch(text)'
  ]
  LOOP
    IF has_function_privilege('anon',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_RPC_ANON_EXECUTE_PRESENT:%',v_sig;
    END IF;
    IF has_function_privilege('authenticated',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_RPC_AUTHENTICATED_EXECUTE_PRESENT:%',v_sig;
    END IF;
    IF NOT has_function_privilege('service_role',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_RPC_SERVICE_EXECUTE_MISSING:%',v_sig;
    END IF;
  END LOOP;
END
$readback$;
