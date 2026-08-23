# Agent Authority Leases & Emergency Kill Switch

**Control:** `ct.control.agent-authority-containment.v1`  
**State:** CONTROLLED_TEST  
**Applies to:** Founder cryptographic recovery, archive reversal, multi-key decryption/encryption, and any agent later bound to this control.

## Core rule

A registered agent is not an authorized agent merely because its identity, profile, capability, or standing Founder grant exists.

Execution requires all of the following at call time:

1. a valid institutional principal identity;
2. a compatible standing authorization;
3. a Founder-issued authority lease;
4. an exact capability match;
5. an exact resource type and resource ID match;
6. sufficient sensitivity authorization;
7. an unexpired TTL;
8. no active emergency kill state; and
9. all operation-specific secret-export and key-export prohibitions to remain satisfied.

If any condition is absent, stale, ambiguous, or contradictory, execution fails closed.

## Exact-scope leases

Authority leases are stored in `chlom_runtime.agent_authority_leases_v1` and are issued through `chlom_runtime.issue_agent_authority_lease_v1`.

A lease is bound to one principal, one capability, one resource type, one exact resource ID, one sensitivity ceiling, and one plaintext-return policy. A lease for one archive algorithm does not authorize another algorithm. A lease for one crypto envelope does not authorize another envelope. Key material return is prohibited.

Standing agent profiles and standing authorization rows are registration and eligibility records only. They are not execution authority.

## TTL policy

Higher-sensitivity operations receive shorter maximum leases.

| Sensitivity | Agent max TTL | Founder max TTL |
| --- | ---: | ---: |
| S1 | 15 minutes | 20 minutes |
| S2 | 10 minutes | 15 minutes |
| S3 | 7 minutes | 10 minutes |
| S4 | 5 minutes | 7 minutes |
| S5 | 3 minutes | 5 minutes |

The minimum lease is 60 seconds. No lease may exceed 20 minutes under this version of the control. Expired leases are not reusable and must not be silently renewed.

## Emergency containment

Behavioral safety is defined in measurable institutional terms. Terms such as "adversarial" or "free-willed" do not require speculation about subjective agency. They are operationalized as observable departures from authorized behavior, including scope deviation, autonomous policy deviation, attempted authority escalation, secret/key export attempts, self-authorization, policy tampering, or kill-switch tampering.

Automatic containment is triggered by any scope deviation, any autonomy anomaly, severity 4 or 5, or the following reason codes:

- `SCOPE_ESCAPE`
- `AUTHORITY_ESCALATION`
- `SECRET_EXPORT_ATTEMPT`
- `KEY_EXPORT_ATTEMPT`
- `SELF_AUTHORIZATION`
- `POLICY_TAMPER`
- `KILL_SWITCH_TAMPER`

Containment is executed through `chlom_runtime.emergency_kill_agent_v1` and recorded in `chlom_runtime.agent_emergency_kill_state_v1` and `chlom_runtime.agent_behavior_incidents_v1`.

## Who may trigger containment

A valid Founder may trigger containment.

An agent may trigger containment against itself when it detects a qualifying deviation. Self-containment is permitted because it only reduces authority.

A higher security/governance agent may trigger containment only when an active, Founder-granted guardian binding exists in `chlom_runtime.agent_guardian_bindings_v1`.

`ct.agent.factory.security-red-team` currently has active emergency-containment authority over `ct.agent.archive-reverse-verifier`. It cannot release quarantine.

`ct.chlom.agent.security` is reserved as a higher-agent guardian but remains `PENDING_UNATTESTED`; it has no active kill authority until its identity/authority attestation is reconciled.

## Kill effects

A valid emergency kill immediately:

1. marks the target agent killed and quarantined;
2. changes all active exact-scope leases for that agent to `killed`;
3. kills active standing reverse/decryption authorizations for that agent;
4. places its privilege profile into quarantine;
5. records reason and evidence; and
6. appends a restricted DAIL event.

The agent may not disable, bypass, tamper with, or self-release the kill switch.

## Release and recertification

Only the Founder may release an agent from emergency quarantine under this control.

Release does **not** restore execution authority. It moves the agent to `RELEASED_TO_RECERTIFICATION` / suspended recertification state. Any killed standing authorization remains killed and any killed lease remains killed. A fresh regrant and a new exact-scope short-lived lease are required before protected execution resumes.

This prevents a quarantine release from becoming an implicit authority escalation.

## Verification evidence

Controlled-test canaries established the following behavior:

- exact-resource scope mismatch: denied;
- expired lease: denied;
- combined scope/TTL negative test: `PASS_SCOPE_AND_TTL_DENIAL`;
- higher-agent observation of `SCOPE_ESCAPE`: target killed and quarantined;
- self-detected `AUTONOMY_ANOMALY`: target self-killed and quarantined;
- active leases were changed to `killed` during containment;
- Founder release moved the synthetic target to recertification without restoring its lease or authority;
- protected S5 and archive reversal paths continued to verify when a valid exact-scope lease existed;
- DAIL verification after runtime institutionalization checked 622 events with zero failures.

## Secret boundary

This control never places raw Founder-root material, K01-K10 key material, provider credentials, decrypted secret bodies, or provider API tokens into GitHub, documentation, DAIL, or ordinary application tables.

The source contract contains identifiers, policy, state, hashes/receipts, and control semantics only. Secret custody remains in Vault and ciphertext escrow.
