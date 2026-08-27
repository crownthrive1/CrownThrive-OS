# PentaPolice Autonomous Policy Supersession & Historical Continuity v1

## Current authority

`ct.factory.autonomous.exact-evidence-promotion.v1` is the current factory-release authority model for D0–D2 releases.

A D0–D2 factory release is accepted only when the exact candidate has all of the following current evidence:

- `genuine_pass=true`;
- every required independent certification is PASS or valid NOT_APPLICABLE;
- every applicable runtime/provider-health contract passes;
- the destination route, provider adapter, rollback, and read-after-write contract are verified;
- targeted maintenance is inactive.

D3 remains human-reserved. Human approval does not waive the technical evidence predicates.

GitHub OIDC is execution identity and attestation. It is not a sovereign vote or quorum source for the autonomous factory authority model.

## Superseded authority

`ct.site.autopublish.v1` and its sovereign-vote-quorum publication semantics are superseded for autonomous factory release authority.

Superseded means historical, not deleted. Its prior existence, configuration, receipts, and decisions remain evidence. PentaPolice prevents it from regaining current authority merely because old code or metadata still references it.

## PentaPolice

PentaPolice (`ct.agent.penta-police`) owns current-control reconciliation. For each registered control family it selects the newest exact control marked current, marks stale competing current controls superseded, and enforces the current authority binding. It never manufactures D3 approval, provider credentials, votes, money movement, rights, or checkout authority.

The release path is policy-sensitive:

1. read exact candidate and maintenance state;
2. evaluate independent certification, health, route, rollback/readback, and D3 human boundary;
3. accept the release when the active authority model permits it;
4. enqueue the existing bounded publication adapter;
5. perform read-after-write verification and preserve rollback evidence.

## PentaArchiver

PentaArchiver (`ct.agent.penta-archiver`) takes every PentaPolice supersession receipt and stores the superseded control snapshot in append-only historical custody. Archive records carry no restore authority. Restoration can occur only through a new governed current-control registration.

## PentaHistorian

PentaHistorian (`ct.agent.penta-historian`) records the supersession as institutional history using the existing historian source/job/observation plane. Historical observations are explicitly `historical_only`, preserve the original control digest, and remain separate from current truth.

## PentaScribe

PentaScribe (`ct.agent.penta-scribe`) writes a factual supersession narrative from the archived snapshots and PentaPolice receipt. The story itself has `current_authority_effect=none`; documentation cannot reactivate a superseded policy.

## Scheduling

The four-agent suite uses the existing internal `public.ct_factory_tick` cadence. External scheduler slots added: **0**.

`ct.schedule.penta-policy-continuity.internal.v1` is an internal schedule-definition binding only. It does not create another external clock.

## Production canary

The first exact release processed after retirement is:

- Candidate: `5d942b82-431b-4ca1-a93a-e0bf852ee8f4`
- Release: `5615a39d-67e6-4558-9c08-0530e8e82768`
- Subject: `ct.product.crownthrive-io.api-sandbox.v1`
- Version: `1.0.0+edge.v5`
- Content SHA-256: `5f31680b3aced8ee88d45814fa03dba5fc8e9d9150bf948742487c2e734269c0`

Live ThriveBase readback after PentaPolice reconciliation showed 10/10 independent certifications, 5/5 health checks, verified route, autonomous acceptance, publication job `published`, catalog projection `published`, and a rollback reference with database-projection read-after-write verification.

The old policy is archived as historical fact and has a PentaScribe story bound to its supersession receipt.
