# PentaSELF Hard-Repair Operations Runbook v1

**Visibility:** Internal  
**Control plane:** PentaSELF / Penta Surgical Care Family  
**Public counterpart:** `/pentaself/hard-repairs`

## Operator objective

Maintain a complete, reviewable and cryptographically anchored record of every important hard repair while preventing repair automation from acquiring unlimited authority.

## Case lifecycle

| State | Meaning | Owner |
|---|---|---|
| `open` | Registered case awaiting precheck | PentaSELF |
| `preop_ready` | Current truth captured and surgery authorized | PentaRounds |
| `operating` | Exact registered procedure executing | PentaSurgeon |
| `postop_verifying` | Production readback in progress | PentaRounds |
| `rollback_required` | Surgery-caused regression proven | PentaRounds |
| `rolled_back` | Compensation readback passed | PentaRounds |
| `retrying` | One bounded retry authorized | PentaSurgeon |
| `certification_pending` | Healthy exact generation awaiting assurance | PentaDnD / PentaCertify |
| `certified` | Two independent exact-generation passes | PentaSELF coordination only |
| `discharged` | Documentation and any required PR closure complete | PentaCloser |
| `held` | More evidence or a newer generation is required | PentaSELF / PentaDocs |

## Opening a case

A case must reference an active handler from `penta_self.hard_repair_handlers_v1`. The handler generation must be monotonic. All callable procedures must implement `jsonb -> jsonb`.

Required case properties:

- stable `case_key`;
- explicit target reference;
- D0, D1 or D2 authority class;
- severity and priority;
- whether public significance applies;
- whether source closure requires a PR; and
- structured input with no raw credential material.

## Pre-operation checks

Before execution, confirm:

- the handler is active;
- the case risk is within the handler ceiling;
- money movement is false;
- secret mutation is false;
- authority expansion is false;
- direct-main is false;
- PentaSurgeon and PentaRounds are separate agents; and
- the precheck explicitly returns a ready/healthy state.

## Exception handling

A transient SQL exception may cause a transactional subrollback and one immediate retry. The failure record must preserve SQLSTATE and a digest, not raw secret-bearing error payloads.

A second failure is held. Do not loop autonomously.

## Compensating rollback

Compensation is allowed only when post-operation output explicitly establishes:

```json
{
  "regression": true,
  "caused_by_repair": true
}
```

The compensation handler must be registered before surgery. Compensation must pass a separate postcheck. Only then may the one bounded post-compensation retry run.

Do not roll back when causation is unknown. Hold the case and open a newer generation when evidence improves.

## Charting requirements

PentaChart writes these chart types as applicable:

- triage;
- preop;
- procedure;
- postop;
- rollback;
- retry;
- certification;
- discharge; and
- followup.

Every chart is linked to `case_id`, exact generation and SHA-256 digest. Redaction is mandatory for secrets, tokens, passwords, credentials, email addresses, phone numbers, IP addresses, cookies, raw provider bodies and private keys.

## Independent certification

Two passes are required against the same exact case SHA:

1. `penta.dnd`
2. `penta.certify`

PentaSELF cannot certify its own case. PentaSurgeon cannot act as verifier. A digest mismatch invalidates the certification.

## PentaDocs projection

Internal reports are published for every important case under the internal repair ledger. Public reports are generated for significant, critical, held or failed cases after redaction.

Public reports may include:

- repair class;
- final disposition;
- whether compensation or retry occurred;
- independent certifier names;
- exact case digest;
- high-level safety boundaries; and
- public timestamps.

Do not publish raw stack traces, table/query internals, contact PII, provider raw responses, credentials or secrets.

## Source-changing repairs

Register the exact PR using `penta_self.hard_repair_pr_register_v1`.

The merge gate must pass all conditions:

- case state certified/discharged;
- certification state `pass`;
- two exact independent certifications;
- PR targets `main`;
- PR is not draft;
- PR is mergeable;
- required checks are green;
- unresolved high finding count is zero;
- documentation state is complete/published;
- internal report exists; and
- exact head SHA has not changed.

Promotion writes a PentaPR lifecycle snapshot. PentaMerge performs the provider merge. Provider readback must show `provider_merged=true` and a merge commit SHA before PentaCloser discharges the case.

## Follow-up and permanence

A discharged repair is written into the permanent-repair state with `automatic_rollback_allowed=false` and `rollback_requires_newer_independent_failure=true`.

A newly observed defect does not resurrect an old rollback. Open a newer case generation, preserve the old record, and repeat independent assurance.

## Production status

Use:

```sql
select public.penta_self_hard_repair_status_v1();
```

The existing canonical PentaSELF tick executes the surgery and PR lanes. No separate hard-repair cron is authorized.
