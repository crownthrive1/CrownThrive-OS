# CrownThrive Services Stack Compatibility Skill

## Purpose

Use the 14 stable `ct.css.service.*` identities as provider-independent service semantics beneath the current PentaFabric execution layer.

## Current sequence

1. Resolve the stable CSS service ID.
2. Resolve the current operation contract and data class.
3. Ask PentaCredentials for a valid credential binding reference; never consume raw secret material from this skill.
4. Ask PentaCertify for current exact-operation certification.
5. Resolve CHLOM/Penta authority for the requested operation.
6. Route through PentaFabric only when credential, certification, authority, and provider state all satisfy the contract.
7. Require readback for side effects.
8. Route drift/failure to PentaNurture and current status to PentaStatus.

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
