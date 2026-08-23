# Founder Exact Override Execution Standard v1

## Purpose

This standard defines the execution path for an explicit human Founder override after the Founder Continuity request has been approved by the human Founder.

Founder approval and CHLOM surrogate authority are distinct. A direct Founder decision must never be forced through a surrogate-attestation path, and a surrogate must never impersonate the Founder.

## Exact-snapshot requirement

Before a direct Founder-approved action can enter `started` or `succeeded`, the runtime must verify all of the following against the original request:

- the request is explicitly `approved` by the human Founder;
- a non-empty Founder authority-evidence reference exists;
- the supplied `exact_version_ref` matches the approved request;
- the supplied SHA-256 matches the approved request;
- the Founder Continuity policy remains active.

A stale or mismatched version/hash fails closed.

## Execution separation

Direct Founder execution uses `chlom_runtime.founder_continuity_record_founder_execution_v1` and stores a restricted execution receipt. Surrogate-authorized execution continues using `chlom_runtime.founder_continuity_record_execution` with an active CHLOM surrogate attestation.

The legacy surrogate recorder must reject a human-Founder-approved request with `human_founder_override_requires_exact_execution_v1` rather than treating it as a missing surrogate attestation.

## Authority boundary

A Founder override is human authority for the exact approved action. It is not:

- a sovereign-agent PASS;
- Agent D certification;
- authority for a different snapshot;
- permission for an agent to expand its own authority;
- authority created by silence.

The underlying operation must still be executed through a tool/principal that can lawfully and technically perform that exact operation.

## Rollback and evidence

Every override request retains its rollback plan, safeguards, exact version/hash, Founder authority evidence, execution evidence, and DAIL trail. Failed execution requires rollback state; a completed rollback is separately evidenced.
