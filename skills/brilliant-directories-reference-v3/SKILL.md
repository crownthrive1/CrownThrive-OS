# Brilliant Directories Reference V3

Status: **ACTIVE REFERENCE CONTRACT**  
Version: **3.0.0**  
Execution authority: **NONE**  
Canonical CrownThrive authority: `ct.locticians.brilliant-directories.api-fabric.v3`

## Purpose

Give CrownThrive Pentas a redundant, governed reference path for understanding Brilliant Directories resources, schemas and integration conventions without converting external documentation or source code into execution authority.

## Reference order

1. `crownthrive1/brilliant-directories-mcp` — CrownThrive fork, primary reference.
2. `brilliantdirectories/brilliant-directories-mcp` — upstream fallback/reference.

Both sources are reference-only. The fork is not a replacement for V3 and does not expand permissions.

## What may be learned

Subject to the V3 route registry and least-data rules, Pentas may use the reference repositories to understand provider concepts such as members, posts, leads, reviews, categories, email templates, pages, forms, membership plans, pagination, filtering and API permission behavior.

## What may NOT happen

Reference code or documentation MUST NOT:

- bypass `ct.locticians.brilliant-directories.api-fabric.v3`;
- create execution authority;
- expose or infer provider credentials;
- enable `include_user_token`;
- execute DELETE or other D3 operations without the separate D3 path;
- key-hop to evade provider rate limits;
- silently expand routes or permissions when upstream changes;
- overwrite CrownThrive provider evidence or execution certification.

## Redundancy and drift

CrownThrive maintains both the fork and upstream as independent public reference sources. The system compares their public reference content through a quota-independent raw-content path and records a daily receipt. Drift opens a PentaUpdate/PentaCertify reconciliation lane; it does not automatically alter V3.

## Discovery

Institutional discovery surfaces include:

- `locticians.endpoint.discover.v3` — V3 provider capability discovery;
- `locticians.bd.reference.status.v3` — reference continuity/status only;
- Penta skill registry entries for dynamic outreach and BD reference use.

## Receipt contract

Daily reference receipts record reference availability, content digests, drift classification and the invariant `v3_authority_state=authoritative_unchanged`. Historical degraded receipts are append-only and must not be rewritten after recovery.

## Custody

Public GitHub stores this safe reference contract. Restricted implementation details and reusable internal playbooks are held in private/CHLOM-controlled custody. No raw credential material belongs in either repository.
