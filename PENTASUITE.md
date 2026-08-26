# PentaSuite™ — Autonomous Agent Laboratory & Lease Authority

## Canonical identity

**PentaSuite™ is CrownThrive's autonomous agent laboratory and agent-construction authority.** It is not a general software backlog factory and it does not create arbitrary platform software on its own initiative.

The only lawful creation origin for a PentaSuite agent is an accepted **PentaRFA™ (Request for Agent)** record. No direct spawn, conversational request, factory side effect, recovered historical record, provider capability, model output, or pre-existing code artifact may bypass PentaRFA.

PentaSuite may use PentaFactory as a bounded compilation/build substrate after PentaRFA authority exists, but PentaFactory does not grant agent authority. PentaRFA is the authority origin; PentaSuite is the laboratory and lifecycle authority; PentaFactory is a software-production substrate.

## Required PentaRFA content

Every agent request must identify, at minimum:

- stable request key and request kind (`new_agent`, `amendment`, `renewal`, or `reapplication`);
- requester identity/reference;
- stable agent key and display name;
- purpose and complete job contract;
- requested authority class (`D0`–`D3`);
- requested scope envelope;
- requested scale ceiling;
- requested TTL;
- data/access requirements;
- expected tools, skills, adapters, and runtime requirements;
- test/evidence requirements;
- rollback expectations;
- continuity/observability requirements.

An accepted request must receive an explicit granted TTL. A conditional grant must also carry explicit remediation conditions. A failed or revoked lease must carry a lockout TTL before reapplication.

## Adjudication states

PentaRFA adjudication has three substantive outcomes:

- `granted` — accepted within the adjudicated scope, scale ceiling, TTL, and authority envelope;
- `conditional_grant` — accepted only after restructuring/limitation, with mandatory remediation during the granted lease TTL;
- `denied` — no PentaSuite construction authority exists.

D3 or equivalent sovereign authority remains human-reserved unless CrownThrive governance separately changes that rule.

## PentaSuite build package

For every accepted PentaRFA, PentaSuite materializes one governed agent blueprint and the assets needed for the agent to perform its adjudicated job. The baseline package includes:

1. identity contract;
2. mission/job contract;
3. authority policy;
4. skill manifest;
5. tool/adapter manifest;
6. data-access contract;
7. secret-binding references only (never raw secret values in source);
8. runtime configuration;
9. test plan;
10. observability/heartbeat contract;
11. continuity checkpoint contract;
12. rollback plan;
13. documentation package;
14. scaling contract;
15. remediation contract;
16. appeal metadata.

A PentaSuite package is not active merely because it was generated. It must be built/validated and then activated under its lease.

## Lease semantics

Agent authority is leased, not permanent.

The TTL clock begins when the validated agent package is activated. The lease records scope, scale ceiling, authority, start/expiry times, remediation deadline where applicable, heartbeat, strike state, rollback contract, and reapplication lockout state.

Authority does not survive lease expiry, revocation, rollback, or a bar. Scale expansion beyond the granted ceiling requires a new PentaRFA amendment/renewal/reapplication; agents may not self-expand authority.

## Conditional acceptance: lease or lose

A conditionally accepted agent may operate only inside the restructured/limited scope that was granted. Every unresolved condition becomes a remediation item. The remediation deadline is the active lease TTL unless governance explicitly sets a tighter approved deadline.

If required remediation is not verified before the TTL expires, PentaSuite revokes the lease, schedules rollback to the last safe baseline, applies the adjudicated lockout period, and requires a fresh PentaRFA reapplication after lockout.

## Enforcement and abuse prevention

PentaSuite tracks violations and applies a bounded escalation ladder:

`remediation -> restricted -> suspended -> revoked -> barred`

A critical violation may enter the ladder at suspension. Revocation or bar requires rollback and a TTL-bound lockout. Repeated reapplication does not erase lifecycle history. Lockouts prevent immediate abusive re-request loops.

No permanent authority removal is implied by this component contract; bar duration is TTL-bound unless a separate governing instrument lawfully establishes another disposition.

## Appeals

PentaSuite adjudication, enforcement, lockout, revocation, and bar actions are appealable to **ThriveAlumni — The Governmental Layer**.

The primary appeal/dispute body is the **Membership and Ethics Committee**. Major governance matters may escalate to the **Board of Directors**, which retains final authority within that governance structure.

An appeal does not automatically stay a safety rollback or revocation. The governance body may explicitly grant a stay. Active granted stays are honored by the PentaSuite lifecycle sentinel until the appeal is resolved or the stay is lifted.

## Runtime implementation

Current production control-plane components:

- `pentarfa_agent_requests`
- `pentasuite_agent_blueprints`
- `pentasuite_agent_assets`
- `pentasuite_agent_leases`
- `pentasuite_remediation_items`
- `pentasuite_lockouts`
- `pentasuite_appeals`
- `pentasuite_lifecycle_events`
- `pentasuite-control` authenticated Edge Function
- `pentasuite-lifecycle-tick-v1` pg_cron lease sentinel

Core RPCs include PentaRFA submission/adjudication, PentaSuite materialization, heartbeat, remediation submission/verification, violation escalation, lease enforcement, appeal filing/review/decision, rollback scheduling, and the autonomous lifecycle tick.

## Non-negotiable invariants

- No PentaRFA, no agent.
- Denied PentaRFA, no agent build.
- Conditional grant means limited authority plus remediation, not disguised full acceptance.
- TTL begins at activation of the validated package.
- No lease means no authority.
- No self-renewal and no self-scaling beyond the grant.
- Missed mandatory remediation means revoke + rollback + lockout + reapply.
- Appeals route to ThriveAlumni governance; they do not silently rewrite the original evidence trail.
- Every lifecycle transition is evidence-bearing and continuity-safe.
