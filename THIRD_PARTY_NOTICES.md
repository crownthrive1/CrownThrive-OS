# Third-Party Notices

This file preserves notices for third-party material that may have contributed to the repository's initial scaffolding or is referenced by the documentation system.

Third-party licenses apply only to the material covered by those licenses. They do not grant rights to CrownThrive-specific original documentation, architecture, frameworks, registries, policies, brands, source assets, or confidential methods.

## Mintlify Starter Kit scaffolding

The repository was initially created from or informed by Mintlify Starter Kit scaffolding. CrownThrive has replaced the starter identity, project instructions, and branding assets. To the extent portions of the original starter scaffolding remain copyrightable and covered by the following license, this notice is preserved:

> MIT License
>
> Copyright (c) 2026 Mintlify
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Mintlify service and documentation platform

Mintlify is a third-party documentation platform. Use of Mintlify, its hosted service, CLI, components, APIs, MCP tools, themes, icons, or other platform functionality remains subject to Mintlify's applicable terms, documentation, and licenses.

CrownThrive's use of Mintlify does not make Mintlify the owner, licensor, approver, or institutional source of truth for CrownThrive-specific content.

## CHLOM evaluated upstream components — no code incorporated

As of August 19, 2026, the CHLOM Open Source Intake & Upstream Stewardship Cell is evaluating the following upstream projects against defined CHLOM needs. **This section records due-diligence lineage only. No source code, binary, package, fork, trademark, institutional authority, or production dependency from these candidates is incorporated or activated merely because the project is listed here.**

- **Open Policy Agent (OPA)** — evaluated release `v1.17.0`, commit `64a3625d33bc6ad8e7c40df03b76ce2fb3ab4d21`, Apache-2.0. Candidate role: replaceable policy-decision backend behind CrownThrive-owned CHLOM policy IDs and semantic rules.
- **OpenFGA** — evaluated release `v1.18.1`, commit `69efbd95b3d44afb2e2567d485dcc792c7d79e3f`, Apache-2.0. Candidate role: replaceable relationship-authorization backend behind CrownThrive-owned actor/organization/delegation contracts.
- **Cedar** — evaluated release `v4.12.0`, commit `fdcbaed32bdb8c8d13e4eaf2b58db5555e9fb8c5`, Apache-2.0. The evaluated release includes an upstream `NOTICE` identifying "Copyright Cedar Contributors." Candidate role: policy-language/backend compatibility lab, not a second institutional policy authority.
- **Temporal Server** — evaluated release `v1.31.2`, commit `19a774302c613da9adc4436ab14278ccdca8e0a5`, MIT. Candidate role: durable workflow/orchestration backend after CHLOM event and decision contracts are stable.

For Apache-2.0 candidates, any later incorporation or redistribution must preserve the applicable license, modified-file notices, attribution/NOTICE material where required, and the license's patent/trademark boundaries. For the MIT candidate, any covered software copied or substantially distributed must preserve the applicable copyright and permission notice. These license observations are intake controls, not a substitute for CrownThrive's required Legal/Regulatory and IP/Rights/Licensing review.

Before any candidate can move from evaluation to adoption, the governed intake record must additionally resolve exact dependency/SBOM and vulnerability evidence, data/privacy handling, compatibility fixtures, operational exit and replacement, fork necessity, upstream-contribution strategy, specialist endorsements, and the applicable CT-ADR-GOV-011 authority/quorum gate. Unknown or unavailable security evidence remains unknown; it is never converted into a claim of no vulnerabilities.

If CrownThrive later forks an upstream project, the fork must preserve upstream history and required notices, clearly identify CrownThrive modifications, track the upstream remote/version, and maintain a governed rebase/cherry-pick or replacement strategy. A fork does not transfer upstream trademarks, authorship, governance, or institutional authority. Generic non-proprietary fixes should be proposed upstream when practical; CrownThrive-specific policy, private evidence, secrets, and restricted IP remain in CrownThrive-controlled modules.

## External specifications and standards

References to RFCs, NIST publications, W3C Recommendations, OpenAPI, Model Context Protocol, SLSA, C2PA, schema standards, accessibility standards, search-engine documentation, and similar external specifications are governed by their publishers' applicable copyright, license, and use terms.

CrownThrive standards may align with or profile these specifications. Alignment does not imply certification, endorsement, ownership, or incorporation of external text beyond permitted quotation, reference, or implementation.

## Icons, fonts, and hosted assets

Icons, fonts, and hosted assets supplied by Mintlify, Font Awesome, system font providers, browsers, or other third parties remain subject to their applicable licenses and service terms. CrownThrive does not redistribute font files through this repository.

## Dependency notice process

When a new third-party dependency or source is introduced, the responsible contributor must:

1. identify the provider and exact material or package;
2. record the version and source;
3. preserve the required license and attribution;
4. verify that the intended CrownThrive use is permitted;
5. prevent the third-party license from being represented as a license over CrownThrive Material;
6. add any required notice here or in the appropriate dependency manifest.

Questions: contact@crownthrive.com
