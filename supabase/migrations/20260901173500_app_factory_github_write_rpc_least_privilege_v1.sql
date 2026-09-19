-- App Factory direct GitHub-write RPC least-privilege hardening v1.
--
-- Production security readback on 2026-09-01 proved these four public-schema
-- SECURITY DEFINER functions were directly executable by anon/authenticated while
-- capable of performing bounded GitHub/provider mutations. This migration contracts
-- execution authority only. It does not alter function bodies, provider allowlists,
-- credentials, release predicates, rights, money, votes/quorum, or D3 authority.

DO $preflight$
DECLARE
  v_sig text;
  v_oid oid;
  v_expected_sha text;
  v_actual_sha text;
BEGIN
  FOR v_sig, v_expected_sha IN
    SELECT * FROM (VALUES
      ('public.app_factory_github_create_new_file(text,text,text,text,text)', 'de12cceb489ebbcee07ddbdfa9bbd3899f93ea5213009728820d63a5c71cd4c5'),
      ('public.app_factory_merge_receipt_pr(text,text,boolean)', 'd608455915b902bedf3f810140f4098991bd7c7ac5a5a3d25a4f3928cd31170f'),
      ('public.app_factory_public_android_canary_apply_known_repairs()', 'ce7863a4dcaa1f9b66f3e74d6705fb4f928d3c17305d7cfcb49dc420211a6745'),
      ('public.app_factory_publish_final_release_receipts()', '8b0a8258912c75edeba900133765a411a09c7ed0013a8413c7b4f460ca8ce6f0')
    ) AS t(sig, expected_sha)
  LOOP
    v_oid := to_regprocedure(v_sig);
    IF v_oid IS NULL THEN
      RAISE EXCEPTION 'APP_FACTORY_GITHUB_WRITE_RPC_NOT_FOUND:%', v_sig;
    END IF;
    IF NOT (SELECT p.prosecdef FROM pg_proc p WHERE p.oid=v_oid) THEN
      RAISE EXCEPTION 'APP_FACTORY_GITHUB_WRITE_RPC_SECURITY_DEFINER_EXPECTED:%', v_sig;
    END IF;
    SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex') INTO v_actual_sha;
    IF v_actual_sha <> v_expected_sha THEN
      RAISE EXCEPTION 'APP_FACTORY_GITHUB_WRITE_RPC_DEFINITION_DRIFT:%:%', v_sig, v_actual_sha;
    END IF;
  END LOOP;
END
$preflight$;

REVOKE ALL ON FUNCTION public.app_factory_github_create_new_file(text,text,text,text,text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_github_create_new_file(text,text,text,text,text)
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_merge_receipt_pr(text,text,boolean)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_merge_receipt_pr(text,text,boolean)
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_public_android_canary_apply_known_repairs()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_public_android_canary_apply_known_repairs()
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_publish_final_release_receipts()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_publish_final_release_receipts()
  TO service_role;

DO $readback$
DECLARE
  v_sig text;
BEGIN
  FOREACH v_sig IN ARRAY ARRAY[
    'public.app_factory_github_create_new_file(text,text,text,text,text)',
    'public.app_factory_merge_receipt_pr(text,text,boolean)',
    'public.app_factory_public_android_canary_apply_known_repairs()',
    'public.app_factory_publish_final_release_receipts()'
  ]
  LOOP
    IF has_function_privilege('anon',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'APP_FACTORY_GITHUB_WRITE_RPC_ANON_EXECUTE_STILL_PRESENT:%',v_sig;
    END IF;
    IF has_function_privilege('authenticated',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'APP_FACTORY_GITHUB_WRITE_RPC_AUTHENTICATED_EXECUTE_STILL_PRESENT:%',v_sig;
    END IF;
    IF NOT has_function_privilege('service_role',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'APP_FACTORY_GITHUB_WRITE_RPC_SERVICE_ROLE_EXECUTE_MISSING:%',v_sig;
    END IF;
  END LOOP;
END
$readback$;

COMMENT ON FUNCTION public.app_factory_github_create_new_file(text,text,text,text,text) IS
'Privileged App Factory GitHub content-write executor. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_merge_receipt_pr(text,text,boolean) IS
'Privileged App Factory GitHub PR merge executor. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_public_android_canary_apply_known_repairs() IS
'Privileged App Factory GitHub workflow-repair executor. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_publish_final_release_receipts() IS
'Privileged App Factory GitHub release-receipt publisher. Service-role only; end-user execution prohibited.';
