# DAIL Public Contract

## Canonical identity

**DAIL** means **Decentralized Autonomous Information Ledger**.

DAIL is CHLOM's canonical records and information-ledger identity for governed events, provenance, evidence references, approvals, versions, agreements, corrections and audit history.

## Public purpose

The public CHLOM repository may expose DAIL-compatible event schemas, record identifiers, provenance conventions and verification guidance. These public interfaces are intended to make integrations inspectable and interoperable without exposing protected record bodies.

## Record boundary

A public DAIL record may carry:

- stable record or event identifier;
- schema/version identity;
- actor or authority reference suitable for public exposure;
- timestamps or sequence information;
- cryptographic digest or commitment;
- provenance reference;
- public status vocabulary;
- public-safe relationship identifiers.

A public DAIL record must not carry raw secrets, protected-person data, private credentials, confidential evidence bodies, restricted contracts or private Fingerprint implementation data.

## Integrity model

A DAIL-compatible public event should be append-oriented and attributable. Corrections are represented as subsequent governed records rather than silent historical mutation when the underlying implementation supports append-only behavior.

Public projection of a DAIL digest is not proof that the protected body is public. A digest can establish integrity and lineage while the source body remains in restricted custody.

## Relationship to historical DAL

Legacy CHLOM source contains multiple historical DAL expansions and responsibilities. Those records remain part of CHLOM's recoverable lineage.

They do not override the current canonical identity:

```text
CURRENT: DAIL = Decentralized Autonomous Information Ledger
```

Where historical DAL responsibilities remain relevant, they are mapped into current systems such as DAIL records, Case Management, Identity/Attestations, Revenue Allocation or other explicitly governed components rather than collapsed into one ambiguous acronym.

## Relationship to DLA

DAIL and DLA are separate current concepts.

```text
DAIL = Decentralized Autonomous Information Ledger
DLA  = Dynamic Licensing Asset
```

Licensing authority responsibilities are represented by Licensing Stewardship / Issuer Authority, not by redefining DLA.

## Commercial integration

Commercial integrations may consume or emit DAIL-compatible records under an applicable CrownThrive agreement. Public documentation of the record contract does not independently grant access to private record stores or protected data.
