# CHLOM Commercial Projection Architecture

## Objective

The CHLOM commercial projection converts a bounded, intentionally public-safe source package in the CrownThrive parent into a deterministic overlay for the public `crownthrive/chlom-protocol` repository.

The design separates **commercial discoverability** from **private implementation custody**.

## Control plane

The parent controls:

- commercial product designation;
- public/private release policy;
- CrownThrive OS product identity;
- current terminology and repository relationship;
- managed public documentation;
- factory validation and provenance;
- commercial license boundary.

The public child controls its own local validation, contribution workflow, public registries, schemas, research artifacts and other unmanaged public-safe content, subject to the parent-child contract for the managed overlay.

## Deterministic pipeline

```text
CrownThrive-Support/main
        |
        v
commercial/chlom-protocol/public/
        |
        v
projection manifest + contract
        |
        v
security / IP / terminology validator
        |
        v
dist/chlom-protocol/
        |
        +--> artifact receipt
        |
        +--> child candidate branch (when cross-repo authority exists)
                  |
                  v
             pull request
                  |
                  v
          child validation / review
```

## Managed overlay

The factory manages only paths enumerated in the projection manifest. It does not perform a destructive mirror and does not delete unmanaged child content.

This preserves the public repository's machine-readable registries, schemas, tests, historical papers and external contribution surfaces while letting CrownThrive centrally govern the commercial identity and product boundary.

## Provenance receipt

Every generated candidate includes `.crownthrive/upstream.json` containing:

- canonical parent repository;
- exact parent commit SHA;
- projection schema version;
- generation timestamp from the workflow;
- target public repository;
- repository role;
- canonical DAIL and DLA terminology.

## Fail-closed conditions

The projection fails if:

- a managed source path is missing;
- a managed path escapes the public-safe source root;
- a raw-secret or private-key shape is detected;
- a prohibited authority claim is introduced;
- legacy DAL is asserted as current DAIL;
- historical Decentralized Licensing Authority is asserted as the current DLA expansion;
- the manifest permits direct child-main writes or force-push;
- provenance cannot bind to the exact parent commit.

## Commercial activation boundary

The factory can publish documentation and integration candidates. It cannot manufacture a live checkout, price, payment, token, mainnet, public API, entitlement, certification or legal authority. Those require their own governed activation evidence.

## Cross-repository authority

Parent validation and artifact generation work without a cross-repository token. Automated child pull-request creation requires a separately provisioned credential with bounded write access to `crownthrive/chlom-protocol`.

The expected secret name is `CHLOM_PUBLIC_REPO_TOKEN`. The secret value is never stored in source and is not exported into artifacts.
