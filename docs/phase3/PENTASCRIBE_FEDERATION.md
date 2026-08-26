# PentaScribe Federated Semantics

Status: Production architecture
Institutional generation: Phase 3

PentaScribe is not a flat list that must manually duplicate every term already governed elsewhere in CrownThrive. Its production semantic resolver federates exact canonical identities from registered institutional sources while preserving the authority and provenance of each source.

## Resolution order

The resolver uses the following precedence:

1. **PentaScribe seed canon** — terms whose definition, aliases, mark-use posture, FAQ prompts, and semantic metadata are directly governed in `penta/scribe/registry.json`.
2. **PentaOS component registry** — canonical technical component names and aliases from `penta/registry/penta-component-registry.v1.json`.
3. **PENTA institutional system registry** — canonical institutional systems and aliases from `data/penta/systems.registry.json`.
4. **Governed system extensions** — currently the PentaScribe/PentaMarketer extension registry.
5. **PentaRoute primitive doctrine** — exact bold-list primitives from the `PentaRoute primitives` section of `docs/phase3/PENTA_GLOSSARY.md`.
6. **Rejected-name controls** — names explicitly documented as redundant or decorative remain rejected observations, not candidates.
7. **Candidate queue** — only an observed name that resolves nowhere above becomes `candidate_only`.

This means PentaScribe can recognize an already-governed name without copying or silently changing its definition.

## Authority preservation

Federation is identity recognition, not authority promotion. A federated record retains its source ID, source path, authority class, stable machine ID, and canonical name. PentaScribe does not use federation to infer ownership, trademark registration, licensing, provider write authority, deployment status, certification, or economic authority.

Trademark and registered-mark evidence remains governed by PentaScribe's explicit mark-use ledger. A canonical PentaOS or PENTA name appearing in a federated source does **not** become a registered trademark and may not use `®` unless the exact mark has evidence-backed registered status.

## Rejected names

The federation source registry explicitly preserves current architecture decisions that certain decorative duplicates should not be created. Current rejected observations include:

- **PentaCapital** — CrownThrive Holdings retains portfolio stewardship and capital-allocation responsibility.
- **PentaImpact** — CII / ThriveFund retain impact and reinvestment responsibility.
- **PentaOps** — OpsOasis / Penta Control retain operations and control responsibility.

If these names appear in documents, PentaScribe records the observation and the rejection rationale instead of repeatedly surfacing them as new candidates.

## PentaMarketer consumption

PentaMarketer consumes the federated resolver for campaign terminology. A campaign can therefore reference canonical names such as PentaMedia, PentaRoute, PentaFactory, or a PentaRoute primitive without requiring those identities to be duplicated in the seven-term PentaScribe seed registry.

Every resolved term carried into a campaign manifest includes its stable identity, canonical display name, authority class, and authority source. Unknown terms still fail closed. Registered-mark checking still consults explicit PentaScribe mark evidence only.

## Production evidence

Every PentaScribe production cycle now preserves:

- the federated semantic index;
- seed-registry reconciliation;
- known seed observations;
- federated observations;
- explicitly rejected observations;
- true candidate-only observations;
- trademark-symbol observations;
- compiled semantic products;
- a SHA-256-bound execution receipt.

PentaMarketer preserves the semantic-resolution mode in its manifest, queue item, channel artifact, summary, latest-state pointer, and execution receipt.

The result is a scalable institutional language mesh: CrownThrive can continue adding systems and primitives to the correct owner registry, while PentaScribe resolves them centrally without manufacturing a second source of truth.
