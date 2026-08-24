# CHLOM Machine Access Terms

These public terms describe the default access boundary for CHLOM™ APIs, MCP tools, agents, plugins, SDKs, schemas, webhooks, feeds, automation hooks, and other machine-consumable interfaces.

## 1. Access is scoped, not implied

A public schema, endpoint description, tool declaration, successful request, test credential, SDK, plugin, agent capability, webhook, provider event, or repository artifact does not create permission beyond its expressly authorized scope.

Access may be bounded by identity, credential, organization, environment, purpose, role, data class, field of use, territory, call budget, rate limit, commercial plan, contract, consent, security posture, and revocation state.

## 2. No authority manufacture

Machine access cannot independently create or enlarge CrownThrive authority. In particular, a machine action cannot by itself create ownership, assign rights, grant a license, certify a user or asset, create a valid DAIL institutional fact, activate a price, issue an entitlement, move Crown Credits or money, settle a payout, or override a governing contract.

Provider success is evidence, not institutional truth.

## 3. Identity and provenance

Authorized machine actions should resolve to a governed actor or service identity and, when supported, carry a stable ID, DID or equivalent subject reference, request ID, version, timestamp, SHA-256 digest, source reference, authority scope, and audit record.

CHLOM Fingerprint and related identity/provenance mechanisms may have public verification surfaces while private derivation logic, keys, protected mappings, and restricted evidence remain non-public.

## 4. Data and confidentiality

Do not request, transmit, expose, cache, train on, or retain restricted data beyond the authorized purpose. Public machine surfaces must not be used to exfiltrate credentials, customer records, payment data, protected-person data, private contracts, confidential economic logic, private evidence, restricted prompts, or trade-secret implementation details.

## 5. AI and model use

Model training, fine-tuning, embedding-corpus creation, distillation, automated bulk extraction, competitive reconstruction, or creation of a substitutive commercial knowledge product from CrownThrive-controlled material requires separate authorization unless independently permitted by law.

## 6. Commercial use

Paid production use, resale, white-labeling, embedded/OEM use, managed services, commercial redistribution, production certification, or commercial derivative services require the applicable CrownThrive commercial agreement.

Public evaluation material may be used to understand compatibility and prepare an integration, but it does not grant production commercial rights.

## 7. Safety and compliance

Machine clients must respect published security controls, consent, privacy, rights, policy, rate limits, content restrictions, and applicable law. Attempts to bypass authentication, authorization, tenancy, governance, audit, or economic controls are prohibited to the extent permitted by law and contract.

## 8. Versioning and revocation

Machine interfaces may be versioned, deprecated, rate-limited, suspended, or revoked. Production consumers should pin supported versions and implement graceful failure, retry, idempotency, rollback, and fail-closed behavior for high-consequence actions.

## 9. Commercial contact

Licensing, production API/MCP access, enterprise integration, agent/plugin distribution, and OEM/embedded arrangements: contact@crownthrive.com
