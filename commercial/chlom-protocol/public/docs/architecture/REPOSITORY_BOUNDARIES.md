# CHLOM Repository Boundaries and Commercial Projection Model

## Canonical public-safe governance parent

`crownthrive1/CrownThrive-OS` is the CrownThrive-controlled **public** canonical governance parent for the factory-managed CHLOM commercial overlay. It carries public-safe institutional policy, documentation, standards, manifests, contracts, factory controls, validators, and release/projection rules.

The parent repository is authoritative for the **managed public projection layer**. It is not an authorized location for raw secrets, private keys, protected evidence bodies, private contracts, confidential implementation logic, protected-person data, private customer data, restricted economic logic, or other vault-bounded material.

Restricted institutional state and protected implementation knowledge remain outside public Git and may be represented publicly only through bounded references, summaries, identifiers, or evidence-safe projections.

## Public commercial child

`crownthrive/chlom-protocol` is the public commercial child repository.

Its job is to expose public-safe CHLOM material for:

- product discovery and technical evaluation;
- machine-readable public registries and schemas;
- developer and integration contracts;
- research and formal verification artifacts;
- commercial licensing and enterprise integration surfaces;
- Pentafabric architecture and machine-use terms;
- support, partnership, and commercial funnel routing;
- approved public documentation.

The child does not become authoritative over parent-managed policy merely because it is public, contains executable examples, or receives independent contributions.

## Repository family truth model

```text
restricted institutional sources / vault-bounded evidence
                 │ references only
                 ▼
CrownThrive-OS
public-safe canonical governance parent
                 │ deterministic allowlisted projection
                 ▼
chlom-protocol
public commercial child
```

**Both GitHub repositories are public.** The public/private distinction applies to information classification and authority, not to a false claim that the parent repository itself is private.

## Safe synchronization contract

1. Canonical managed public policy and projection source are changed in the parent.
2. The parent branch is validated under CHLOM projection and Pentafabric continuity workflows.
3. The factory builds the exact managed overlay from an exact parent commit.
4. Secret, identity, evidence, and IP-boundary checks run before export.
5. The output receives `.crownthrive/upstream.json` with exact parent provenance and architecture identity.
6. If bounded cross-repository write authority is configured, the factory creates a candidate branch and pull request against the public child.
7. The public child runs its own validation before merge.
8. Unmanaged child registries, schemas, tests, research, and other content are preserved.
9. A build receipt, pull request, merge, provider event, or repository publication is not itself a production, economic, legal, ownership, licensing, or certification activation claim.

## Public-safe boundary

Never project:

- raw credentials or private keys;
- webhook or signing secrets;
- protected-person or customer data outside authorized public scope;
- raw private evidence or privileged material;
- private contracts;
- confidential unit economics or private pricing logic;
- private prompts or scoring logic;
- Fingerprint private derivation or protected mappings;
- unpublished source assets or confidential implementation bodies.

The projection factory is allowlist-only and non-destructive toward unmanaged child paths.

## Authority conflicts and historical lineage

If a historical child document presents a different repository-authority relationship, the current factory-managed boundary controls the managed commercial projection layer under the recorded 2026-08-24 Founder-direct authorization.

Historical source documents may be retained for lineage and research. They should be versioned, classified, and cross-referenced rather than silently rewritten to erase their original context.

## Licensing boundary

Public repository access does not create a commercial, patent, trademark, model-training, certification, or production license. The parent defines public-safe policy and the child exposes the commercial surface, but actual commercial rights still require the applicable CrownThrive agreement.

## Canonical naming

- DAIL = **Decentralized Autonomous Information Ledger**.
- DLA = **Dynamic Licensing Asset**.
- Current issuer authority concept = **Licensing Stewardship / Issuer Authority**.

Historical DAL and historical “Decentralized Licensing Authority” wording remain lineage, not current canonical product definitions.
