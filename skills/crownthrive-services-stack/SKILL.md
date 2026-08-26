# CrownThrive Services Stack Compatibility Skill

## Purpose

Use the 14 stable `ct.css.service.*` identities as provider-independent service semantics beneath the production Penta Family control plane.

## Current sequence

1. Resolve the stable CSS service ID.
2. Resolve the current operation contract and data class.
3. Resolve human/service identity through PentaIdentity where applicable.
4. Ask PentaCredentials for a valid credential binding reference; never consume raw secret material from this skill.
5. Ask PentaCertify for current exact-operation certification.
6. Resolve CHLOM/Penta authority for the requested operation.
7. Use PentaMation for governed workflow orchestration, PentaRoute for the execution path, and PentaFederation for cross-system bindings/proofs only when those registered members and the target path are eligible.
8. Require provider readback for side effects.
9. Route drift/failure to PentaNurture and current state to PentaStatus.

## Historical CSS runtime

Do not assume the August-23 Edge function, `:39` schedule, provider counts, health snapshot, or legacy admin-role map remains current. Those records are lineage until re-read.

The predecessor Edge source is not a production candidate because it contains hard-coded privileged identity allowlisting, a direct service-role token identity shortcut, and pre-Penta authorization roles.

## Hard boundaries

- No raw credential export.
- No authority manufacture.
- No provider write without exact-operation authority and certification.
- No money movement from billing/commerce labels alone.
- No rights grant from licensing labels alone.
- No self-approval or D3 automation.
- No unregistered Penta name may be used as an execution owner.
