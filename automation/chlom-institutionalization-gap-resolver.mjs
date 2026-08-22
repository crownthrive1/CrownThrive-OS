const REQUIRED_ARTIFACT_KINDS = Object.freeze([
  'algorithm',
  'source_code',
  'test',
  'documentation',
  'machine_manifest',
  'schema',
  'threat_model',
  'recovery',
  'pricing',
  'agent_handoff',
  'ci_workflow',
]);

const REQUIRED_CONTROL_SECTIONS = Object.freeze([
  'docs_impact',
  'security',
  'privacy',
  'rights',
  'commercialization',
  'rollback',
  'scheduler',
  'provenance',
  'third_party_dependencies',
  'ai_governance',
]);

const GAP_HANDOFFS = Object.freeze({
  algorithm: 'ct.agent.chlom-wallet-settlement',
  source_code: 'ct.agent.chlom-wallet-settlement',
  test: 'ct.subagent.verification-tevv',
  documentation: 'ct.agent.articleization',
  machine_manifest: 'ct.subagent.evidence-provenance',
  schema: 'ct.agent.api-mcp',
  threat_model: 'ct.agent.qa-security',
  recovery: 'ct.subagent.recovery-rollback',
  pricing: 'ct.subagent.finance-tax-treasury',
  agent_handoff: 'ct.agent.phase-gate',
  ci_workflow: 'ct.subagent.operations-sre',
  docs_impact: 'ct.agent.articleization',
  security: 'ct.agent.qa-security',
  privacy: 'ct.agent.qa-security',
  rights: 'ct.agent.rights-governance',
  commercialization: 'ct.agent.commerce',
  rollback: 'ct.subagent.recovery-rollback',
  scheduler: 'ct.subagent.operations-sre',
  provenance: 'ct.subagent.evidence-provenance',
  third_party_dependencies: 'ct.subagent.legal-regulatory',
  ai_governance: 'ct.agent.phase-gate',
});

function uniqueSorted(values) {
  return [...new Set(values)].sort();
}

function duplicateValues(values) {
  const seen = new Set();
  const duplicates = new Set();
  for (const value of values) {
    if (seen.has(value)) duplicates.add(value);
    seen.add(value);
  }
  return [...duplicates].sort();
}

export function resolveInstitutionalizationGaps(spec, artifactInventory) {
  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) throw new Error('institutionalization_spec_object_required');
  if (!Array.isArray(artifactInventory)) throw new Error('artifact_inventory_array_required');

  const gaps = [];
  const artifactKinds = new Set(artifactInventory.map((artifact) => artifact.kind));
  for (const kind of REQUIRED_ARTIFACT_KINDS) {
    if (!artifactKinds.has(kind)) {
      gaps.push({
        code: `MISSING_ARTIFACT_KIND_${kind.toUpperCase()}`,
        category: kind,
        severity: 'blocking',
        handoff_agent_id: GAP_HANDOFFS[kind],
      });
    }
  }

  for (const section of REQUIRED_CONTROL_SECTIONS) {
    const value = spec[section];
    const missing = value === undefined || value === null || (Array.isArray(value) && value.length === 0) || (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0);
    if (missing) {
      gaps.push({
        code: `MISSING_CONTROL_SECTION_${section.toUpperCase()}`,
        category: section,
        severity: 'blocking',
        handoff_agent_id: GAP_HANDOFFS[section],
      });
    }
  }

  const duplicateArtifactIds = duplicateValues(artifactInventory.map((artifact) => artifact.artifact_id));
  for (const artifactId of duplicateArtifactIds) {
    gaps.push({
      code: 'DUPLICATE_ARTIFACT_ID',
      category: 'identity',
      severity: 'blocking',
      artifact_id: artifactId,
      handoff_agent_id: 'ct.agent.platform-registry',
    });
  }

  const algorithms = Array.isArray(spec.algorithms) ? spec.algorithms : [];
  const duplicateAlgorithmIds = duplicateValues(algorithms.map((algorithm) => algorithm.algorithm_id));
  for (const algorithmId of duplicateAlgorithmIds) {
    gaps.push({
      code: 'DUPLICATE_ALGORITHM_ID',
      category: 'identity',
      severity: 'blocking',
      algorithm_id: algorithmId,
      handoff_agent_id: 'ct.agent.platform-registry',
    });
  }

  for (const artifact of artifactInventory) {
    if (artifact.public_projection === true && artifact.classification !== 'public') {
      gaps.push({
        code: 'NONPUBLIC_ARTIFACT_IN_PUBLIC_PROJECTION',
        category: 'privacy',
        severity: 'blocking',
        artifact_id: artifact.artifact_id,
        handoff_agent_id: 'ct.agent.qa-security',
      });
    }
    if (artifact.secret_shape_detected === true) {
      gaps.push({
        code: 'SECRET_SHAPE_DETECTED',
        category: 'security',
        severity: 'blocking',
        artifact_id: artifact.artifact_id,
        handoff_agent_id: 'ct.agent.qa-security',
      });
    }
  }

  const hardBoundaries = spec.hard_boundaries && typeof spec.hard_boundaries === 'object' ? spec.hard_boundaries : {};
  for (const [key, value] of Object.entries(hardBoundaries)) {
    if (value !== false) {
      gaps.push({
        code: 'HARD_BOUNDARY_NOT_FALSE',
        category: 'authority',
        severity: 'blocking',
        boundary: key,
        observed_value: value,
        handoff_agent_id: 'ct.agent.phase-gate',
      });
    }
  }

  const aiGovernance = spec.ai_governance ?? {};
  if (aiGovernance.advisory_only !== true || aiGovernance.decision_authority !== false || aiGovernance.write_authority !== false) {
    gaps.push({
      code: 'AI_GOVERNANCE_BOUNDARY_INVALID',
      category: 'ai_governance',
      severity: 'blocking',
      handoff_agent_id: 'ct.agent.phase-gate',
    });
  }

  const blockingCount = gaps.filter((gap) => gap.severity === 'blocking').length;
  const score = Math.max(0, 100 - blockingCount * 5);
  const disposition = blockingCount === 0
    ? 'PASS_CONTROLLED_TEST_INSTITUTIONALIZATION'
    : 'HOLD_INSTITUTIONALIZATION_GAPS';

  return {
    algorithm_id: 'ct.algorithm.chlom.institutionalization-gap-resolver.v1',
    algorithm_version: '1.0.0',
    mode: 'deterministic_policy_engine',
    ai_extension_mode: 'advisory_only_no_authority',
    required_artifact_kinds: [...REQUIRED_ARTIFACT_KINDS],
    required_control_sections: [...REQUIRED_CONTROL_SECTIONS],
    artifact_kinds_present: uniqueSorted([...artifactKinds]),
    gap_count: gaps.length,
    blocking_gap_count: blockingCount,
    completeness_score: score,
    disposition,
    gaps: gaps.sort((a, b) => `${a.code}:${a.category}:${a.artifact_id ?? ''}`.localeCompare(`${b.code}:${b.category}:${b.artifact_id ?? ''}`)),
    required_handoffs: uniqueSorted(gaps.map((gap) => gap.handoff_agent_id).filter(Boolean)),
    authority_effect: 'none',
    automatic_remediation: false,
    automatic_release: false,
  };
}

export { REQUIRED_ARTIFACT_KINDS, REQUIRED_CONTROL_SECTIONS };
