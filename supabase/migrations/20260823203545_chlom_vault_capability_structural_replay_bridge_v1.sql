-- PROVENANCE-ONLY TOMBSTONE
-- This migration version was the first repair placement for the non-secret
-- capability structural replay bridge. Provider branch-action readback proved
-- the actual failing historical execution-builder preflight is
-- 20260823202950_execution_builder_capability_contract_identity_v1.sql, so this
-- later placement cannot satisfy the prerequisite ordering.
--
-- The executable repair moved to:
-- 20260823202949_chlom_vault_capability_structural_replay_bridge_v1.sql
--
-- Preserve this no-op migration as lineage. Do not add capability authority,
-- credentials, secret values, provider activation, D3 authority, money movement,
-- rights grants, certification effect, or branch deletion here.

begin;
select 1;
commit;
