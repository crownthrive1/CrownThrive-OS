# PentaScribe Federation Governance

PentaScribe Federation Governance is the fail-closed semantic-authority layer between CrownThrive's distributed canonical registries and the PentaScribe/PentaMarketer production control planes.

## Why it exists

Federation increases vocabulary coverage, but multiple registries can legitimately mention the same canonical name. A simple first-match resolver is not sufficient institutional governance because two independent identities could normalize to the same semantic key and one could silently shadow the other.

The federation-governance layer therefore distinguishes three conditions:

1. **single authority claim** — one admitted identity owns the semantic key;
2. **same/equivalent identity overlap** — multiple canonical sources describe the same machine identity, or an explicit compatibility equivalence links legacy/compact IDs to the stable PentaOS identity;
3. **ambiguous semantic authority** — multiple non-equivalent identities claim the same normalized name or alias. This is a production HOLD.

Precedence is used only after identity compatibility is proven. It is not a mechanism for hiding a collision.

## Compatibility equivalences

`penta/scribe/sources.registry.json` may declare explicit ID equivalence groups. An equivalence means that two machine identifiers refer to the same semantic system identity for compatibility and lookup purposes. It does **not** merge legal entities, ownership, trademarks, provider accounts, licenses, credentials, economic rights, or governance authority.

PentaScribe and PentaMarketer currently preserve their compact seed IDs while binding them to the stable PentaOS machine keys through explicit equivalence declarations.

## Production gate

Before federated semantics are trusted, the production runtime runs:

```bash
python penta/scribe/federation_governance.py audit
```

A non-zero ambiguity count fails the governance gate. The PentaScribe runtime records `HOLD_FEDERATION_CONFLICTS` and does not treat the federated index or downstream semantic projections as trusted production truth.

PentaMarketer independently refuses campaign validation when a supplied federated semantic graph has unresolved authority collisions.

## Candidate disposition queue

Discovery observations that are not already resolved by seed canon, registered federation sources, or explicit rejected-name controls become review-only candidate work items.

Each candidate receives:

- a deterministic candidate ID derived from its normalized semantic key;
- observed spelling and proposed normalized ID;
- occurrence count and bounded evidence-source list;
- observed mark symbols, if any;
- a priority based on prevalence and mark-use sensitivity;
- required PentaScribe and CIE review gates;
- conditional PentaIP/CHLOM review when legal, rights, licensing, ownership, or mark status is asserted;
- `automatic_promotion: false`.

The queue is produced with:

```bash
python penta/scribe/federation_governance.py triage \
  --discovery <discovery.json> \
  --out <candidate-queue.json>
```

## Allowed dispositions

A governed reviewer or authorized downstream workflow may eventually classify a candidate as:

- admitted canonical term;
- alias of an existing canonical identity;
- deprecated/superseded term;
- historical/context-only term;
- explicitly rejected/redundant name;
- deferred/HOLD pending evidence.

Discovery itself authorizes none of these outcomes.

## Evidence and continuity

Each PentaScribe production cycle preserves:

- `federation-audit.json`;
- `federated-index.json` when authority is unambiguous;
- `discovery.json`;
- `candidate-queue.json`;
- canonical compiler products;
- reconciliation state;
- summary and cryptographic execution receipt.

This gives PentaDocs, PentaGeneration, PentaVergence, PentaFactory, PentaMarketer, PentaIP, CIE, CHLOM, and other consumers a durable distinction between **recognized canon**, **compatible overlap**, **true candidate**, **rejected name**, and **authority conflict**.

## Constitutional boundary

PentaScribe may recognize and reconcile semantic authority already granted by canonical institutional sources. It may never manufacture legal rights, trademark registration, provider capability, publication authority, economic authority, ownership, or governance power.
