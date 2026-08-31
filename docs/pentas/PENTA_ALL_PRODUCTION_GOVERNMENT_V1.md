# All Pentas Production and Government v1

**Contract:** `ct.penta.all-production-government.v1`  
**Campaign:** `ct.campaign.all-pentas-production-government.v1`  
**Canonical scheduler:** `ct-penta-census-native-due-v1`  
**State:** Production presence complete / specialist reconciliation active

## Current institutional census

At the August 30, 2026 production certification snapshot, CrownThrive contained:

- 462 current Penta identities;
- 473 registered systems;
- 1,024 current census entities;
- 16 Penta families;
- 935 identity/system production-governed presences;
- 1,024 government assignments; and
- 2,822 active governance memberships.

These are current Supabase/ThriveBase counts. GitHub source, Google Drive constitutional records, and PentaDocs are reconciled as lower-precedence source or knowledge evidence.

## Why every Penta can be in production without manufacturing capability

`Production` is not treated as one undifferentiated label.

### Specialist execution

An identity or system is specialist-execution eligible only when its exact runtime and qualifying production evidence are present. The certification snapshot contained 110 such presences.

### Governed coordination

Implemented systems and identities may have active production status, government assignment, documentation, help, routing, and coordination while their specialist write path remains independently gated. The certification snapshot contained 204 such presences.

### Candidate fail-closed

Specified, candidate, bootstrap, and production-candidate identities receive a real production institutional surface without receiving independent provider or specialist execution authority. The certification snapshot contained 621 such presences.

This distinction prevents the census from manufacturing maturity merely to turn every row green.

## PentaMocracy government model

CrownThrive uses an internal U.S.-federal-government analogy.

### Executive Branch

The Executive Branch operates registered departments, agencies, offices, certified runtimes, and bounded D0–D2 execution.

### Legislative Branch

Penta Congress is bicameral:

- the **House of Families** represents the fifteen canonical constitutional Penta families;
- the **Senate of Systems** represents registered CrownThrive systems by exact system identity.

### Judicial Branch

The judiciary includes:

- Penta Supreme Court;
- Penta Court of Appeals; and
- Penta District Courts.

It enforces due process, recusal, independent review, exact evidence, and separation of duties.

### Independent establishments

Independent establishments include census, archives and records, inspector-general, comptroller, reserve, sanctions observation, research, intelligence, security, trust, observability, resilience, and continuity bodies.

These bodies do not manufacture sovereign or legal authority.

## Departments, bureaus, and Penta offices

Each constitutional family is represented by a department or independent establishment. Each department contains bureaus for:

- truth;
- authority;
- execution;
- interoperation;
- continuity;
- coordination;
- orchestration;
- translation; and
- unresolved/unclassified work.

Every current non-family Penta identity receives an accountable production office or agency under its reconciled family and axis bureau.

A Penta office is an accountability and routing surface. It does not automatically grant the office's specialist runtime authority.

## Membership

Every current census entity receives:

1. a workforce census membership; and
2. an institutional representation membership.

Systems are represented in the Senate. Families are represented in the House. Other entities receive branch or independent-establishment representation.

Machine voting remains limited to internally eligible D0–D2 matters. A machine vote can never satisfy a required human ratification floor.

Membership never grants:

- provider credentials;
- legal authority;
- rights or licensing authority;
- publication authority;
- money-movement authority;
- destructive authority; or
- D3 authority.

## Generic production runtime

All current identities and systems are reachable through:

```sql
select public.penta_citizen_runtime_v1(
  '<exact identity or system key>',
  'status',
  '{}'::jsonb
);
```

Supported generic operations are:

- `status`;
- `describe`;
- `government`;
- `readiness`;
- `help`;
- `docs`; and
- `route`.

The generic runtime has no dispatch authority. `route` returns governed family candidates through `integration_control.penta_family_route_v1`; it does not select or execute a provider write by itself.

## Specialist gap mobilization

The production census emitted 170 safe D0–D2 specialist handoffs to the accountable nodes:

- `ct.penta.factory.software`;
- `ct.penta.wire`;
- `ct.penta.certify`; and
- `ct.penta.release`.

The categories were:

- 32 needs-build;
- 51 needs-contract;
- 16 needs-production;
- 4 needs-registration;
- 12 needs-upgrade; and
- 55 needs-wiring.

A packet reaching `routed` is not recorded as complete. Completion requires exact target-node evidence, a completed packet, and a receipt.

The D3 backlog remains `approval_required`. The scheduler does not auto-ratify it.

## Scheduler behavior

The existing canonical census job was upgraded in place:

```text
jobname: ct-penta-census-native-due-v1
schedule: 3-58/5 * * * *
command:  select integration_control.penta_census_scheduler_tick_v2();
```

No duplicate reconciliation clock was created.

Each cycle:

1. runs the canonical census due check;
2. reconciles all identity/system production presence;
3. assigns new census entities into government and workforce;
4. mobilizes safe D0–D2 handoffs;
5. reconciles packets and receipts;
6. refreshes campaign state; and
7. preserves D3 as human-reserved.

The campaign enters maintenance after production presence and government assignment complete. It reaches `completed` only after the safe specialist backlog reaches verified closure. The canonical census clock then remains as the permanent maintenance clock rather than creating another scheduler.

## Source precedence

1. Supabase/ThriveBase current state.
2. GitHub CrownThrive-OS source registry.
3. Google Drive constitutional doctrine.
4. PentaDocs/Mintlify knowledge projection.

Lower-precedence evidence cannot manufacture higher runtime maturity, credentials, provider permission, legal authority, or PASS.

## Production interfaces

- `public.penta_all_production_status_v1()`
- `public.penta_production_census_public_v1`
- `public.penta_citizen_runtime_v1(text,text,jsonb)`
- `integration_control.penta_census_scheduler_tick_v2()`
- `integration_control.penta_all_pentas_presence_reconcile_v1()`
- `integration_control.penta_all_pentas_government_batch_v1(integer)`
- `integration_control.penta_census_mobilize_safe_handoffs_v1(integer)`
- `integration_control.penta_census_mobilization_reconcile_v1(integer)`
- `integration_control.penta_all_production_campaign_refresh_v1()`

## Non-authorities

This program does not:

- rewrite specified candidates as specialist-production systems;
- manufacture provider adapters or credentials;
- manufacture legal, rights, licensing, fiduciary, financial, or D3 authority;
- mark routed work as completed without receipts;
- create a duplicate census scheduler; or
- retire a current production clock merely because a campaign reaches maintenance.
