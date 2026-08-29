-- Replay compatibility for Penta protocol v3.
-- Production historically enforced NOT NULL on penta_system_registry.last_verified_at,
-- while the following additive protocol migration stages one conflict candidate with
-- an explicit NULL before final reconciliation. Temporarily relax only that column;
-- the paired 20260829032550 migration restores and verifies the invariant.

alter table public.penta_system_registry
  alter column last_verified_at drop not null;
