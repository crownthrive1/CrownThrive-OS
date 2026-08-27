# CHLOM Commercial Projection Architecture

## Objective

The CHLOM commercial projection converts a bounded, intentionally public-safe source package in the canonical CrownThrive governance parent into a deterministic overlay for the public `crownthrive/chlom-protocol` commercial repository.

The design separates **commercial discoverability** from **restricted implementation and evidence custody**.

## Repository truth

- `crownthrive1/CrownThrive-OS` is the **public canonical governance parent** for the managed CHLOM commercial overlay.
- `crownthrive/chlom-protocol` is the **public commercial child**.
- Restricted institutional state and confidential implementation bodies are not authorized for publication in either public repository.

## Control plane

The parent controls the managed overlay's:

- commercial product designation;
- public-safe release policy;
- CrownThrive OS product identity;
- CrownThrive Pentafabric architecture identity;
- current terminology and repository relationship;
- managed public documentation;
- factory validation and provenance;
- licensing and machine-use boundary;
- support and commercial-funnel routing.

The public child controls its own local validation, contribution workflow, public registries, schemas, research artifacts, tests, and other unmanaged public-safe content, subject to the parent-child contract for the managed overlay.

## Deterministic pipeline

```text
governed CrownThrive sources
        |
        v
CrownThrive-OS/main
        |
        v
commercial/chlom-protocol/public/
        |
        v
projection manifest + relationship/license contracts
        |
        v
security / IP / terminology / Pentafabric validator
        |
        v
dist/chlom-protocol/
        |
        +--> exact upstream receipt
        |
        +--> child candidate branch (when bounded cross-repo authority exists)
                  |
                  v
             pull request
                  |
                  v
          child validation / review
```

## Managed overlay

The factory manages only paths enumerated in the projection manifest. It does not perform a destructive mirror and does not delete unmanaged child content.

The managed package now covers repository positioning, rights/license notices, machine-access terms, support/funding routing, commercial and licensing pages, Pentafabric architecture, repository topology, agent/factory documentation, DAIL public contract, and exact upstream provenance.

This preserves the public repository's registries, schemas, tests, historical papers, research, and external contribution surfaces while letting CrownThrive centrally govern the managed commercial identity and product boundary.

## Provenance receipt

Every generated candidate includes `.crownthrive/upstream.json` containing:

- canonical parent repository;
- exact parent commit SHA;
- projection schema version;
- CrownThrive Pentafabric architecture ID;
- generation timestamp;
- target public repository;
- repository role;
- canonical DAIL and DLA terminology;
- founder/authority mode used for the governed projection record;
- explicit statement that the receipt is not certification.

## Fail-closed conditions

The projection fails if:

- a managed source path is missing;
- a managed path escapes the public-safe source root;
- a raw-secret or private-key shape is detected;
- a prohibited authority claim is introduced;
- legacy DAL is asserted as current DAIL;
- historical Decentralized Licensing Authority is asserted as the current DLA expansion;
- the manifest permits direct child-main writes, force-push, self-merge, or security bypass;
- restricted material is marked for public export;
- provenance cannot bind to the exact parent commit.

## Continuous projection

The factory is event-driven when managed parent files change and is also designed for scheduled continuity checks. Scheduled execution does not mean scheduled mutation: when the child already matches the managed package, the run is a no-op.

## Commercial activation boundary

The factory can publish documentation, rights notices, integration contracts, agent/factory specifications, and commercial package candidates. It cannot manufacture a live checkout, price, payment, token, mainnet, public API/MCP, entitlement, certification, ownership claim, or legal authority.

Economic activation resolves separately through ThriveEvergreen / ECAC and supporting current-state evidence.

## Cross-repository authority

Parent validation and artifact generation work without a cross-repository token. Automated child pull-request creation requires a separately provisioned credential with bounded write access to `crownthrive/chlom-protocol`.

The expected secret name is `CHLOM_PUBLIC_REPO_TOKEN`. The secret value is never stored in source and is not exported into artifacts.
