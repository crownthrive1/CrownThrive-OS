# PentaMarketer

**PentaMarketer** is CrownThrive's governed marketing orchestration and campaign-manifest system.

It turns approved objectives into terminology-conformant, culturally aligned, authority-bounded marketing packages. It does not replace the Cultural Imprint Engine (CIE), CHLOM, PentaMedia, PentaGreen, CrownLytics, CrownPulse, AdLuxe Network, ThrivePush, or PentaDocs; it coordinates marketing work across those owners.

## Dependency order

`PentaScribe vocabulary → CIE imprint/voice → CHLOM rights/authority → PentaMarketer campaign manifest → certified distribution/commerce/media adapters → CrownLytics/CrownPulse measurement → evidence + retrospective`

This order is deliberate. Marketing cannot invent product names, legal status, rights, cultural meaning, or provider authority.

## What PentaMarketer owns

- campaign objective and audience packaging;
- canonical terminology conformance;
- message and CTA manifests;
- channel plan selection;
- campaign IDs and versionable manifests;
- handoff contracts to owned web, email, social, media, community, partner, and paid lanes;
- measurement handoffs to CrownLytics and CrownPulse;
- commerce handoff to PentaGreen;
- documentation handoff to PentaDocs;
- distribution handoff to PentaMedia, AdLuxe Network, ThrivePush, and other certified adapters;
- preservation of campaign language, terms used, approvals, receipts, and retrospectives.

## Fail-closed rules

PentaMarketer refuses a campaign manifest when:

- a referenced institutional term is unknown to PentaScribe;
- a required CIE imprint is missing;
- a CHLOM authority reference is missing;
- a channel is outside policy;
- blocked or unsupported claims are detected;
- `®` is used without evidence-backed registered status.

A successful manifest compilation is **not publication authority**. Provider writes, paid spend, external publication, and economic actions require their own certified routes and applicable approval/capability gates.

## Commands

```bash
python penta/marketer/pentamarketer.py validate --campaign penta/marketer/campaign.example.json
python penta/marketer/pentamarketer.py compile --campaign penta/marketer/campaign.example.json --out /tmp/campaign-manifest.json
```

## Institutional marketing rule

PentaMarketer must market the ecosystem as an interoperable system, not as a pile of disconnected brands. Every campaign should identify the corridor/lane, canonical language, CIE imprint, intended Flywheel movement, downstream destination, measurement owner, and evidence path appropriate to the campaign.
