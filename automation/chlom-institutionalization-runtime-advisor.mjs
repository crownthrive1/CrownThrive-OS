// CHLOM Institutionalization Runtime Advisor v1
// Deterministic advisory policy engine. No network, writes, credentials, release authority, or AI decision authority.

const PRIORITY_ORDER = Object.freeze({ P0: 0, P1: 1, P2: 2, P3: 3 });

function object(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(code);
  return value;
}

function boolean(value, code) {
  if (typeof value !== 'boolean') throw new Error(code);
  return value;
}

function string(value, code) {
  if (typeof value !== 'string' || value.length === 0 || value.length > 500) throw new Error(code);
  return value;
}

function advisory(code, priority, ownerAgentId, summary, evidence, actions) {
  return {
    advisory_id: `ct.advisory.chlom.institutionalization.${code.toLowerCase()}.v1`,
    code,
    priority,
    owner_agent_id: ownerAgentId,
    summary,
    evidence,
    recommended_actions: actions,
    advisory_only: true,
    automatic_action: false,
    decision_authority: false,
    write_authority: false,
    release_authority: false,
  };
}

export function adviseInstitutionalizationRuntime(input) {
  const value = object(input, 'runtime_advisor_input_required');
  const edge = object(value.edge_function, 'runtime_advisor_edge_required');
  const database = object(value.database, 'runtime_advisor_database_required');
  const ci = object(value.ci, 'runtime_advisor_ci_required');
  const review = object(value.review, 'runtime_advisor_review_required');
  const commercialization = object(value.commercialization, 'runtime_advisor_commercialization_required');

  string(edge.slug, 'runtime_advisor_edge_slug_required');
  boolean(edge.exists, 'runtime_advisor_edge_exists_boolean_required');
  boolean(edge.active, 'runtime_advisor_edge_active_boolean_required');
  boolean(edge.verify_jwt, 'runtime_advisor_edge_verify_jwt_boolean_required');
  string(database.package_state, 'runtime_advisor_package_state_required');
  string(database.ingest_state, 'runtime_advisor_ingest_state_required');
  string(database.package_canary, 'runtime_advisor_package_canary_required');
  string(database.ingest_canary, 'runtime_advisor_ingest_canary_required');
  string(database.oidc_subject_canary, 'runtime_advisor_oidc_subject_canary_required');
  string(ci.package_v2_workflow, 'runtime_advisor_ci_state_required');
  string(review.state, 'runtime_advisor_review_state_required');
  boolean(commercialization.effective_offer, 'runtime_advisor_effective_offer_boolean_required');
  boolean(commercialization.checkout_enabled, 'runtime_advisor_checkout_boolean_required');

  const advisories = [];

  if (!edge.exists) {
    advisories.push(advisory(
      'EDGE_FUNCTION_MISSING', 'P0', 'ct.subagent.operations-sre',
      'Deploy the OIDC-gated CHLOM institutionalization v2 Edge Function.',
      { slug: edge.slug },
      ['deploy exact source-controlled function', 'record function ID/version/build digest', 'rerun package ingest workflow'],
    ));
  } else if (!edge.active) {
    advisories.push(advisory(
      'EDGE_FUNCTION_INACTIVE', 'P0', 'ct.subagent.operations-sre',
      'Restore the institutionalization v2 Edge Function to ACTIVE state.',
      { slug: edge.slug, status: edge.status ?? null },
      ['inspect deployment logs', 'redeploy exact known-good source', 'run unauthenticated rejection and OIDC ingest checks'],
    ));
  }

  if (edge.exists && edge.verify_jwt !== false) {
    advisories.push(advisory(
      'CUSTOM_OIDC_MIDDLEWARE_CONFLICT', 'P0', 'ct.agent.qa-security',
      'Disable Supabase JWT middleware for this function and retain internal GitHub OIDC verification.',
      { verify_jwt: edge.verify_jwt },
      ['set verify_jwt false', 'verify GitHub RS256/JWKS validation remains mandatory', 'run wrong-issuer/audience/signature tests'],
    ));
  }

  if (database.package_canary !== 'PASS_CHLOM_INSTITUTIONALIZATION_PACKAGE_V2_CANARY') {
    advisories.push(advisory(
      'PACKAGE_CANARY_NOT_PASS', 'P0', 'ct.subagent.verification-tevv',
      'Restore deterministic package validation before ingest.',
      { observed: database.package_canary },
      ['inspect validator drift', 'rerun mutation and authority-boundary negatives', 'do not ingest a real package'],
    ));
  }
  if (database.ingest_canary !== 'PASS_CHLOM_INSTITUTIONALIZATION_INGEST_V2_CANARY') {
    advisories.push(advisory(
      'INGEST_CANARY_NOT_PASS', 'P0', 'ct.subagent.verification-tevv',
      'Restore OIDC claim, replay, ancestry, and manifest-binding canaries.',
      { observed: database.ingest_canary },
      ['verify OIDC JTI idempotency', 'verify source ancestry and manifest digests', 'verify raw token and artifact bodies are not persisted'],
    ));
  }
  if (database.oidc_subject_canary !== 'PASS_CHLOM_INSTITUTIONALIZATION_OIDC_SUBJECT_V2_CANARY') {
    advisories.push(advisory(
      'OIDC_SUBJECT_CANARY_NOT_PASS', 'P0', 'ct.agent.qa-security',
      'Reconcile legacy and immutable GitHub OIDC subject formats without broadening repository trust.',
      { observed: database.oidc_subject_canary },
      ['allow only exact owner/repository IDs', 'reject wrong IDs and branches', 'rerun immutable-subject canary'],
    ));
  }

  if (ci.package_v2_workflow !== 'success') {
    advisories.push(advisory(
      'PACKAGE_V2_WORKFLOW_NOT_GREEN', 'P0', 'ct.subagent.operations-sre',
      'Resolve the exact-head GitHub OIDC package ingest workflow failure.',
      { observed: ci.package_v2_workflow, run_id: ci.package_v2_run_id ?? null },
      ['inspect failing step and sanitized error code', 'fix source or runtime without weakening trust policy', 'rerun on the current exact head'],
    ));
  }

  if (database.package_state === 'NO_RECORDED_PACKAGE_V2') {
    advisories.push(advisory(
      'REAL_PACKAGE_NOT_RECORDED', 'P1', 'ct.subagent.evidence-provenance',
      'Ingest the committed Phase C institutionalization package through the verified GitHub OIDC workflow.',
      { package_state: database.package_state },
      ['require exact committed manifest', 'require frozen source head to be an ancestor', 'record package and OIDC receipt digests only'],
    ));
  }

  if (database.ingest_state !== 'RECORDED_CONTROLLED_TEST_EVIDENCE') {
    advisories.push(advisory(
      'INGEST_STATUS_NOT_RECORDED', 'P1', 'ct.subagent.evidence-provenance',
      'Establish an append-only controlled-test ingest receipt.',
      { ingest_state: database.ingest_state },
      ['use GitHub OIDC token', 'persist token fingerprint—not token value', 'preserve no-live boundaries'],
    ));
  }

  if (review.state !== 'READY_FOR_PHASE_GATE_REVIEW') {
    advisories.push(advisory(
      'INDEPENDENT_REVIEW_REMAINS_HOLD', 'P2', 'ct.agent.phase-gate',
      'Keep production and merge paths closed until designated reviewers act from fresh identity contexts.',
      {
        review_state: review.state,
        ready_reviewers: review.ready_reviewers ?? null,
        required_reviewers: review.required_reviewers ?? null,
        receipts_recorded: review.receipts_recorded ?? null,
      },
      ['do not fabricate reviewer heartbeats', 'collect exact-snapshot append-only receipts', 'forward only a complete receipt set to Phase Gate'],
    ));
  }

  if (commercialization.effective_offer || commercialization.checkout_enabled) {
    advisories.push(advisory(
      'COMMERCIALIZATION_BOUNDARY_BREACH', 'P0', 'ct.agent.commerce',
      'Disable effective offer and checkout state until independent price, rights, security, tax, and fulfillment review completes.',
      { effective_offer: commercialization.effective_offer, checkout_enabled: commercialization.checkout_enabled },
      ['close checkout', 'hold public price', 'preserve candidate-only WalletKit catalog'],
    ));
  } else if (commercialization.pricing_state !== 'PRICE_REVIEW') {
    advisories.push(advisory(
      'PRICING_STATE_UNRESOLVED', 'P3', 'ct.subagent.finance-tax-treasury',
      'Normalize WalletKit bundle candidates to the governed pricing-review state.',
      { pricing_state: commercialization.pricing_state ?? null },
      ['freeze candidate scope', 'record cost and support assumptions', 'obtain independent pricing receipt'],
    ));
  }

  advisories.sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority] || a.code.localeCompare(b.code));
  return {
    algorithm_id: 'ct.algorithm.chlom.institutionalization-runtime-advisor.v1',
    semantic_version: '1.0.0',
    mode: 'deterministic_advisory_policy_engine',
    state: advisories.length === 0 ? 'NO_RUNTIME_GAPS' : 'ADVISORIES_PRESENT',
    advisory_count: advisories.length,
    highest_priority: advisories[0]?.priority ?? null,
    advisories,
    ai_governance: {
      advisory_only: true,
      deterministic_rules_first: true,
      future_llm_extension_requires_prompt_and_model_receipt: true,
      output_requires_independent_review: true,
      decision_authority: false,
      write_authority: false,
      automatic_release: false,
      training_on_restricted_artifacts: false,
    },
    hard_boundaries: {
      network_access: false,
      credential_access: false,
      provider_write: false,
      money_movement: false,
      rights_grant: false,
      chain_broadcast: false,
      phase_advancement: false,
      merge_authorized: false,
    },
  };
}
