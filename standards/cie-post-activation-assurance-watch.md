# CIE post-activation assurance watch

## Purpose

The **Cultural Imprint Engine (CIE)** is already in bounded governed production. Its immutable Founder-direct production authority remains tied to the exact activation snapshot. This watch keeps the *current repository-link assurance* healthy as CrownThrive-OS evolves, without converting routine parent-repository evolution into new production authority.

The watch is hosted by the existing Repository Child Guardian 30-minute cycle. It adds **no new cron job, no new external scheduler task, and no new agent authority**.

## Existing schedule reused

- Schedule: `ct.schedule.repository-child-guardian-30m`
- pg_cron job: `ct-repository-child-guardian-30m`
- cadence: `7,37 * * * *`
- Guardian: `ct.agent.repository-child-guardian-ad-litem`
- scheduler slot delta: `0`

`repository_child_guardian_family_cycle_v1` retains the existing Guardian, family rebuild and interoperability synchronization steps, then invokes `cie_post_activation_assurance_watch_v1` as a bounded subroute.

## External evidence boundary

PostgreSQL does not call GitHub and does not claim to know GitHub state by itself.

The watcher consumes only the latest records in `institutional_federation.repository_external_observations_v1`. Those observations must already have been written through a trusted service-role evidence path. For automatic assurance refresh, both Support and CIE observations must be fresh, exact and GitHub-scoped.

If external observations are absent or older than 90 minutes, the watcher returns `HOLD_EXTERNAL_GITHUB_EVIDENCE_STALE` and creates or refreshes a non-destructive Guardian nurture action. It does not fabricate a head SHA, compare result, or PASS.

## Parent-only automatic assurance

A newer CrownThrive-OS `main` SHA may be automatically reconciled only when the newest trusted Support observation proves:

- repository identity is exactly `crownthrive1/CrownThrive-OS` / repository ID `1336348391`;
- `compare_status=ahead`;
- `compare_base_sha` equals the immutable Founder-authorized activation parent SHA;
- `compare_head_sha` equals the newly observed Support `main` SHA;
- `compare_behind_by=0`;
- `compare_ahead_by>=1`;
- `production_authority_rewritten=false`.

The watcher then calls `refresh_cie_parent_child_production_assurance_v1`, which independently rechecks bounded production, Founder-direct receipt integrity, fresh observations, Guardian/family/interoperability evidence and the accepted CIE contract digest.

The resulting current-head link receipt is **assurance only**. It does not change the immutable Founder request, activation receipt, production exact-version reference, production content SHA-256 or activation parent/child snapshot.

## CIE child-head changes are never auto-assured

The CIE observation must identify immutable repository ID `1341314455`, and the observed CIE `main` SHA must remain equal to the production activation child SHA.

If CIE `main` changes, the watcher returns:

`HOLD_CIE_CHILD_HEAD_CHANGED_REAUTH_REQUIRED`

That state explicitly requires a new governed source review and appropriate production decision. A code change to CIE itself is not treated as routine parent continuity and cannot inherit the earlier Founder production authorization.

## Watcher states

Healthy states:

- `PASS_CURRENT_ASSURANCE` — exact observations already match a healthy `linked_governed` assurance receipt.
- `PASS_ASSURANCE_REFRESHED` — Support moved forward as a proven descendant and the watcher created/refreshed current-head assurance.
- `SKIPPED_LOCKED` — another assurance watch transaction already holds the advisory lock.

Fail-closed states:

- `HOLD_PRODUCTION_BOUNDARY_DRIFT`
- `HOLD_EXTERNAL_GITHUB_EVIDENCE_STALE`
- `HOLD_CIE_CHILD_OBSERVATION_TRUST_MISMATCH`
- `HOLD_CIE_CHILD_HEAD_CHANGED_REAUTH_REQUIRED`
- `HOLD_SUPPORT_PARENT_OBSERVATION_TRUST_MISMATCH`
- `HOLD_SUPPORT_DESCENDANT_PROOF_REQUIRED`
- `HOLD_ASSURANCE_REFRESH_FAILED`

## Nurture actions

HOLD states create or refresh a row in `institutional_federation.repository_guardian_actions_v1` under the `POST_ACTIVATION_ASSURANCE_*` action classes.

These actions are always:

- non-destructive;
- merge-authority false;
- parent-approval required;
- limited to observation, evidence refresh, registry reconciliation, handoff opening and patch-candidate preparation.

They explicitly prohibit activation/reactivation, Founder-authority rewrite, merge, delete, archive, transfer, visibility change, child self-activation and automatic D3.

When assurance becomes healthy, only the watcher's own open `POST_ACTIVATION_ASSURANCE_*` nurture actions are resolved.

## Authority boundaries

The watch may never create or alter:

- production activation authority;
- the Founder production request or evidence reference;
- public activation;
- provider-write authority;
- economic or rights effects;
- commerce/pricing/checkout/entitlement;
- voting eligibility;
- D3 authority.

Every watch DAIL event records `production_authority_rewritten=false`, `operational_activation=false`, `provider_write_effect=false`, `economic_effect=false`, `rights_effect=false`, `vote_effect=false`, and `D3_auto=false`.

## Security

The watcher and Guardian wrapper are private-schema `SECURITY DEFINER` functions with pinned `search_path`. Execution is revoked from `public`, `anon` and `authenticated` and granted only to `service_role`; the existing pg_cron execution continues under the database's privileged scheduler context.

## Operational result

This design makes current-head link assurance self-maintaining **when trustworthy external evidence is available** and self-alerting when it is not. It does not pretend that database automation can independently observe GitHub, and it never turns evidence freshness into authority.
