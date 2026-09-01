-- Rollback for PentaHelp independent-gate transport v1.
-- This removes only the additive transport layer. It does not mutate PentaHelp requests,
-- liaison threads, Penta authority state, destination decisions, or immutable DAIL history.

drop function if exists public.penta_help_dispatch_independent_gates_v1(integer);
drop trigger if exists independent_gate_dispatch_append_only_v1 on penta_help.independent_gate_dispatches_v1;
drop function if exists penta_help.reject_independent_gate_dispatch_mutation_v1();
drop table if exists penta_help.independent_gate_dispatches_v1;
