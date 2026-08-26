revoke execute on function public.penta_backup_control_plane_v1(text,text) from public, anon, authenticated;
grant execute on function public.penta_backup_control_plane_v1(text,text) to service_role;

revoke execute on function public.penta_flush_ephemeral_v1(interval,boolean) from public, anon, authenticated;
grant execute on function public.penta_flush_ephemeral_v1(interval,boolean) to service_role;

revoke execute on function public.penta_redblue_pentagreen_23514_v1() from public, anon, authenticated;
grant execute on function public.penta_redblue_pentagreen_23514_v1() to service_role;

revoke execute on function public.penta_remediate_pentagreen_23514_v1() from public, anon, authenticated;
grant execute on function public.penta_remediate_pentagreen_23514_v1() to service_role;

revoke execute on function public.penta_restore_plan_v1(uuid) from public, anon, authenticated;
grant execute on function public.penta_restore_plan_v1(uuid) to service_role;
