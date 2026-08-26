# PentaScribe

**PentaScribe** is CrownThrive's governed institutional language and semantic continuity system.

It owns the machine-governed lifecycle for terms, canonical names, aliases, definitions, dictionaries, glossaries, indexes, FAQs, naming relationships, deprecations, and trademark/mark-use tracking. It is not a replacement for PentaDocs: PentaScribe is the semantic source and compiler; PentaDocs is the institutional knowledge projection and publication layer.

## Institutional contract

PentaScribe must:

1. keep one canonical identity for each admitted term;
2. preserve aliases and superseded names without allowing them to silently become current canon;
3. separate semantic status from legal/trademark status;
4. record provenance for every canonical definition;
5. compile machine-readable truth into human-readable language artifacts;
6. detect collisions, drift, unsupported aliases, and improper registered-mark symbol use;
7. feed PentaDocs, PentaMarketer, PentaMedia, PentaBooks, PentaFactory, CrownThrive IO, APIs/MCPs, and other governed downstream consumers;
8. preserve versions and deprecations for PentaGeneration continuity.

## Authority boundary

PentaScribe **does not create legal rights**. A term appearing in the registry does not prove ownership, registration, filing, licensing authority, or exclusivity. Trademark status remains an evidence-bearing field. The `®` symbol is blocked unless the registry marks a name `registered` and carries a registration reference.

## Source and outputs

Canonical source: `penta/scribe/registry.json`.

The compiler produces:

- `GLOSSARY.md`
- `DICTIONARY.md`
- `INDEX.md`
- `FAQ.md`
- `TRADEMARK_LEDGER.md`
- `ALIASES.md`
- `reconciliation.json`

Generated artifacts belong under `docs/generated/pentascribe/` and must not be manually edited.

## Lifecycle

`candidate/draft → canonical → deprecated/historical`

Trademark evidence is an independent lifecycle:

`unverified → claimed_public_display → filed → registered` with `abandoned` and `not_applicable` where appropriate.

No semantic promotion automatically promotes legal status.

## PENTA loop

**Discover:** ingest terms, aliases, definitions, public usage, FAQ demand, and drift.  
**Govern:** resolve identity, provenance, CIE meaning, CHLOM implications, sensitivity, legal evidence, and status.  
**Execute:** normalize and compile registries and human artifacts.  
**Verify:** validate collisions, provenance, aliases, symbols, schemas, and downstream usage.  
**Preserve:** version definitions, aliases, deprecations, evidence, and generated packs.

## Commands

```bash
python penta/scribe/pentascribe.py validate
python penta/scribe/pentascribe.py reconcile
python penta/scribe/pentascribe.py compile
```

## Reconciliation rule

Existing `docs/phase3/PENTA_GLOSSARY.md` remains institutional doctrine for the PENTA architecture. PentaScribe does not erase it. PentaScribe becomes the compiler and canonical semantic-control responsibility that progressively reconciles specialized glossaries into one governed registry while preserving domain ownership.
