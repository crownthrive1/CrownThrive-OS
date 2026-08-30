# PentaSELF Surgical Care Family v1

**Contract:** `ct.penta.self.hard-repair.v1`  
**Family key:** `SURGICAL_CARE`  
**State:** Production  
**Maximum autonomous risk:** D2  
**D3:** Human-reserved

## Purpose

The Penta Surgical Care Family is CrownThrive's governed production path for high-importance repairs that need more than a shallow retry but must not give PentaSELF unlimited repair authority.

The family closes the complete lifecycle:

1. current-truth triage;
2. pre-operation snapshot;
3. bounded repair surgery;
4. post-operation readback;
5. causal regression determination;
6. compensation only when the surgery caused the regression;
7. one bounded retry after transactional or verified compensating rollback;
8. independent exact-generation certification;
9. structured operational charting;
10. internal and public PentaDocs projection;
11. exact-head pull-request closure for source changes; and
12. permanent forward-only repair registration.

## Family members

### PentaSurgeon

PentaSurgeon executes exact handlers registered in `penta_self.hard_repair_handlers_v1`. Each handler must expose governed `jsonb -> jsonb` precheck, repair, postcheck, optional compensation, and optional retry procedures.

PentaSurgeon cannot:

- execute arbitrary repair SQL;
- exceed D2;
- manufacture authority;
- move money;
- mutate or manufacture credentials or secrets;
- certify its own repair;
- write directly to `main`; or
- restore an older repair generation over a newer certified generation.

### PentaChart

PentaChart records structured operational charts through `penta_scribe.repair_chart_append_v1`. Charts include observations, assessment, procedure, response, plan, evidence, exact case generation, author identity, and SHA-256 digest.

The chart format applies disciplined continuity principles associated with high-quality clinical charting, but it is explicitly operational—not medical care and not a medical record.

### PentaRounds

PentaRounds performs post-operation current-truth readback and answers four separate questions:

1. Is the target healthy?
2. Did a regression occur?
3. Did this surgery cause it?
4. Did compensation and the one bounded retry restore a healthy state?

An unhealthy result alone never authorizes compensation. Both regression and repair causation must be established.

## Existing family integrations

| Penta | Responsibility |
|---|---|
| PentaSELF | Owns the case and coordinates the bounded lifecycle |
| PentaScribe | Preserves structured chart and institutional narrative lineage |
| PentaDocs | Maintains internal reports and redacted public reports |
| PentaDnD | Isolates and independently tests the exact repair generation |
| PentaCertify | Supplies the second independent exact-generation certification |
| PentaPR | Classifies exact-head terminal action |
| PentaMerge | Performs the governed provider merge |
| PentaCloser | Requires provider readback, exact head, and documentation before closure |

## Rollback and retry contract

There are two distinct rollback paths.

### Transaction subrollback

If a registered repair handler raises an unexpected transient exception, PostgreSQL contains the failed sub-operation. PentaSELF may immediately retry once.

### Compensating rollback

If post-operation evidence proves the repair introduced a regression, the registered compensation handler may run. The compensation itself must pass readback before a single post-compensation retry is allowed.

No other automatic rollback is authorized. After discharge, the repair is monotonic and forward-only. A later problem opens a newer case generation; an old snapshot does not silently replace current truth.

## Independent assurance

A repair generation is certifiable only when:

- the case has a valid immutable case digest;
- post-operation truth is healthy and non-regressed;
- PentaDnD passes the exact repair contract;
- PentaCertify passes the same case digest;
- the originator is not counted as a certifier; and
- the verifier is not the repair executor.

## Pull-request closure

Source-changing repairs use `penta_self.hard_repair_pr_merge_gate_v1`.

The gate requires:

- a certified case;
- two exact-generation independent passes;
- a non-draft PR targeting `main`;
- exact head SHA continuity;
- mergeability;
- green checks;
- zero unresolved high findings;
- complete PentaDocs records; and
- an internal repair report already published.

PentaSELF supplies the certified snapshot. PentaPR classifies it. PentaMerge executes the provider action. PentaSELF does not write directly to `main`, does not self-approve, and does not count its own vote.

## Production canary

The canary case `6975c96b-0925-48ad-b7f8-0a71d1509ae7` proved the complete non-provider surgery lifecycle:

- intentional bounded mutation;
- detected repair-caused regression;
- verified compensation;
- one immediate retry;
- healthy post-operation state;
- PentaDnD pass;
- PentaCertify pass;
- PentaChart records;
- PentaDocs internal/public projection; and
- discharge with no authority expansion.

Exact case SHA-256:

`c01273cb8579a4f77edad2f1db5d198166327f101886aa48486a36e55da6685d`

## Production objects

- `penta_self.hard_repair_handlers_v1`
- `penta_self.hard_repair_cases_v1`
- `penta_self.hard_repair_attempts_v1`
- `penta_self.hard_repair_certifications_v1`
- `penta_self.hard_repair_pr_links_v1`
- `penta_scribe.repair_charts_v1`
- `penta_docs.repair_reports_v1`
- `penta_self.hard_repair_cycle_v1(uuid)`
- `penta_self.hard_repair_queue_tick_v1(integer)`
- `penta_self.hard_repair_pr_tick_v1(integer)`
- `penta_dnd.hard_repair_contract_test_v1(uuid)`
- `public.penta_self_hard_repair_status_v1()`

## Production scheduling

No new scheduler is introduced. The family runs through the existing canonical PentaSELF tick. Surgery work and certified PR work are separate lanes, preventing a certified case awaiting merge from being operated on again.
