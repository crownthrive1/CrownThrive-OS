-- App Factory provider-control dispatch RPC least-privilege hardening v1.
--
-- Production caller inventory on 2026-09-01 found these public-schema
-- SECURITY DEFINER functions executable by anon/authenticated while they resolve an
-- internal provider-dispatch token and can trigger bounded provider-control actions.
-- Current pg_stat_statements evidence showed only postgres execution for observed
-- runtime calls and no end-user invocation. This migration contracts ACLs only.

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
      RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_RPC_NOT_FOUND:%', v_sig;
    END IF;
    IF NOT (SELECT p.prosecdef FROM pg_proc p WHERE p.oid=v_oid) THEN
      RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_RPC_SECURITY_DEFINER_EXPECTED:%', v_sig;
    END IF;
    SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex') INTO v_actual_sha;
    IF v_actual_sha <> v_expected_sha THEN
      RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_RPC_DEFINITION_DRIFT:%:%', v_sig, v_actual_sha;
    END IF;
  END LOOP;
END
$preflight$;

REVOKE ALL ON FUNCTION public.app_factory_operational_cleanup_dispatch(text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_operational_cleanup_dispatch(text)
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_ssl_control_dispatch(text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_ssl_control_dispatch(text)
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_docroot_control_dispatch(text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_docroot_control_dispatch(text)
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_storage_repair_dispatch(text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_storage_repair_dispatch(text)
  TO service_role;

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
      RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_RPC_ANON_EXECUTE_STILL_PRESENT:%',v_sig;
    END IF;
    IF has_function_privilege('authenticated',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_RPC_AUTHENTICATED_EXECUTE_STILL_PRESENT:%',v_sig;
    END IF;
    IF NOT has_function_privilege('service_role',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_RPC_SERVICE_ROLE_EXECUTE_MISSING:%',v_sig;
    END IF;
  END LOOP;
END
$readback$;

COMMENT ON FUNCTION public.app_factory_operational_cleanup_dispatch(text) IS
'Privileged App Factory operational-cleanup provider dispatcher. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_ssl_control_dispatch(text) IS
'Privileged App Factory SSL provider-control dispatcher. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_docroot_control_dispatch(text) IS
'Privileged App Factory document-root provider-control dispatcher. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_storage_repair_dispatch(text) IS
'Privileged App Factory storage-repair provider dispatcher. Service-role only; end-user execution prohibited.';
