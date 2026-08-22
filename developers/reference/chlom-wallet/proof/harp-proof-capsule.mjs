import {
  assertAsciiIdentifier,
  assertHex64,
  assertIsoTimestamp,
  assertSanitizedMetadata,
  canonicalize,
  frameAscii,
  sha256Hex,
} from '../common/canonical-json.mjs';

// HARP v1 — Hash Anchor Root Packager.
// CONTROLLED TEST: creates deterministic proof commitments only. It does not publish to a chain.

export const HARP_SCHEMA_VERSION = '1.0.0';
const LEAF_DOMAIN = 'CHLOM:HARP:LEAF:v1';
const NODE_DOMAIN = 'CHLOM:HARP:NODE:v1';
const MANIFEST_DOMAIN = 'CHLOM:HARP:MANIFEST:v1';
const MAX_ITEMS = 100_000;
const ALLOWED_ITEM_KEYS = new Set([
  'record_id',
  'record_type',
  'payload_digest',
  'policy_digest',
  'occurred_at',
  'source_event_seq',
  'public_metadata',
]);

function rejectUnknownKeys(item) {
  for (const key of Object.keys(item)) {
    if (!ALLOWED_ITEM_KEYS.has(key)) throw new Error(`harp_item_key_not_allowed:${key}`);
  }
}

export function normalizeHarpItem(item) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('harp_item_object_required');
  rejectUnknownKeys(item);
  const record_id = assertAsciiIdentifier(item.record_id, 'harp_record_id_invalid', 160);
  const record_type = assertAsciiIdentifier(item.record_type, 'harp_record_type_invalid', 96);
  const payload_digest = assertHex64(item.payload_digest, 'harp_payload_digest_invalid');
  const policy_digest = item.policy_digest == null ? null : assertHex64(item.policy_digest, 'harp_policy_digest_invalid');
  const occurred_at = item.occurred_at == null ? null : assertIsoTimestamp(item.occurred_at, 'harp_occurred_at_invalid');
  const source_event_seq = item.source_event_seq == null ? null : item.source_event_seq;
  if (source_event_seq !== null && (!Number.isSafeInteger(source_event_seq) || source_event_seq < 1)) {
    throw new Error('harp_source_event_seq_invalid');
  }
  const public_metadata = assertSanitizedMetadata(item.public_metadata ?? {});
  const public_metadata_digest = sha256Hex(canonicalize(public_metadata));
  return {
    record_id,
    record_type,
    payload_digest,
    policy_digest,
    occurred_at,
    source_event_seq,
    public_metadata,
    public_metadata_digest,
  };
}

function harpLeafDigestFromNormalized(normalizedScope, normalized) {
  const preimage = frameAscii([
    LEAF_DOMAIN,
    normalizedScope,
    normalized.record_id,
    normalized.record_type,
    normalized.payload_digest,
    normalized.policy_digest ?? '-',
    normalized.occurred_at ?? '-',
    normalized.source_event_seq ?? '-',
    normalized.public_metadata_digest,
  ]);
  return sha256Hex(preimage);
}

export function harpLeafDigest(scope, item) {
  const normalizedScope = assertAsciiIdentifier(scope, 'harp_scope_invalid', 160);
  return harpLeafDigestFromNormalized(normalizedScope, normalizeHarpItem(item));
}

export function harpNodeDigest(leftDigest, rightDigest) {
  const left = assertHex64(leftDigest, 'harp_left_node_digest_invalid');
  const right = assertHex64(rightDigest, 'harp_right_node_digest_invalid');
  return sha256Hex(frameAscii([NODE_DOMAIN, left, right]));
}

function buildTreeFromLeaves(leafDigests) {
  if (!Array.isArray(leafDigests) || leafDigests.length === 0) throw new Error('harp_leaf_set_required');
  const levels = [leafDigests.map((digest) => assertHex64(digest, 'harp_leaf_digest_invalid'))];
  while (levels.at(-1).length > 1) {
    const current = levels.at(-1);
    const next = [];
    for (let index = 0; index < current.length; index += 2) {
      const left = current[index];
      const right = current[index + 1] ?? left;
      next.push(harpNodeDigest(left, right));
    }
    levels.push(next);
  }
  return levels;
}

export function buildHarpCapsule({ capsule_id, scope, policy_version, created_at, items }) {
  const normalizedCapsuleId = assertAsciiIdentifier(capsule_id, 'harp_capsule_id_invalid', 160);
  const normalizedScope = assertAsciiIdentifier(scope, 'harp_scope_invalid', 160);
  const normalizedPolicyVersion = assertAsciiIdentifier(policy_version, 'harp_policy_version_invalid', 96);
  const normalizedCreatedAt = assertIsoTimestamp(created_at, 'harp_created_at_invalid');
  if (!Array.isArray(items) || items.length < 1 || items.length > MAX_ITEMS) throw new Error('harp_item_count_invalid');

  const normalizedItems = items.map(normalizeHarpItem).sort((a, b) => a.record_id.localeCompare(b.record_id));
  for (let index = 1; index < normalizedItems.length; index++) {
    if (normalizedItems[index - 1].record_id === normalizedItems[index].record_id) throw new Error('harp_duplicate_record_id');
  }

  const commitments = normalizedItems.map((item) => ({
    record_id: item.record_id,
    record_type: item.record_type,
    payload_digest: item.payload_digest,
    policy_digest: item.policy_digest,
    occurred_at: item.occurred_at,
    source_event_seq: item.source_event_seq,
    public_metadata_digest: item.public_metadata_digest,
    leaf_digest: harpLeafDigestFromNormalized(normalizedScope, item),
  }));
  const tree_levels = buildTreeFromLeaves(commitments.map((entry) => entry.leaf_digest));
  const root_digest = tree_levels.at(-1)[0];
  const manifestCore = {
    schema_version: HARP_SCHEMA_VERSION,
    capsule_id: normalizedCapsuleId,
    scope: normalizedScope,
    policy_version: normalizedPolicyVersion,
    created_at: normalizedCreatedAt,
    leaf_count: commitments.length,
    root_digest,
    commitments,
    anchor_state: 'candidate_unbroadcast',
    raw_evidence_included: false,
    money_movement: false,
    public_chain_broadcast: false,
  };
  const manifest_digest = sha256Hex(frameAscii([MANIFEST_DOMAIN, sha256Hex(canonicalize(manifestCore))]));
  return {
    capsule: { ...manifestCore, manifest_digest },
    tree_levels,
  };
}

export function generateHarpProof(buildResult, recordId) {
  if (!buildResult?.capsule || !Array.isArray(buildResult.tree_levels)) throw new Error('harp_build_result_required');
  const record_id = assertAsciiIdentifier(recordId, 'harp_record_id_invalid', 160);
  const index = buildResult.capsule.commitments.findIndex((entry) => entry.record_id === record_id);
  if (index < 0) throw new Error('harp_record_not_found');
  const proof = [];
  let cursor = index;
  for (let levelIndex = 0; levelIndex < buildResult.tree_levels.length - 1; levelIndex++) {
    const level = buildResult.tree_levels[levelIndex];
    const isRight = cursor % 2 === 1;
    const siblingIndex = isRight ? cursor - 1 : cursor + 1;
    proof.push({
      position: isRight ? 'left' : 'right',
      digest: level[siblingIndex] ?? level[cursor],
    });
    cursor = Math.floor(cursor / 2);
  }
  return {
    schema_version: HARP_SCHEMA_VERSION,
    capsule_id: buildResult.capsule.capsule_id,
    scope: buildResult.capsule.scope,
    record_id,
    leaf_index: index,
    leaf_count: buildResult.capsule.leaf_count,
    root_digest: buildResult.capsule.root_digest,
    proof,
  };
}

export function verifyHarpProof({ scope, item, proof, root_digest }) {
  const normalizedScope = assertAsciiIdentifier(scope, 'harp_scope_invalid', 160);
  const root = assertHex64(root_digest, 'harp_root_digest_invalid');
  if (!Array.isArray(proof) || proof.length > 64) throw new Error('harp_proof_invalid');
  let digest = harpLeafDigest(normalizedScope, item);
  for (const step of proof) {
    if (!step || !['left', 'right'].includes(step.position)) throw new Error('harp_proof_position_invalid');
    const sibling = assertHex64(step.digest, 'harp_proof_digest_invalid');
    digest = step.position === 'left' ? harpNodeDigest(sibling, digest) : harpNodeDigest(digest, sibling);
  }
  return {
    valid: digest === root,
    computed_root_digest: digest,
    expected_root_digest: root,
    public_chain_broadcast: false,
    money_movement: false,
  };
}

export function verifyHarpCapsule(capsule) {
  if (!capsule || typeof capsule !== 'object') throw new Error('harp_capsule_required');
  if (capsule.schema_version !== HARP_SCHEMA_VERSION) throw new Error('harp_schema_version_unsupported');
  if (capsule.anchor_state !== 'candidate_unbroadcast' || capsule.public_chain_broadcast !== false || capsule.money_movement !== false) {
    throw new Error('harp_controlled_test_boundary_invalid');
  }
  if (!Array.isArray(capsule.commitments) || capsule.commitments.length !== capsule.leaf_count || capsule.leaf_count < 1) {
    throw new Error('harp_commitment_count_invalid');
  }
  const leaves = capsule.commitments.map((entry) => assertHex64(entry.leaf_digest, 'harp_leaf_digest_invalid'));
  const root = buildTreeFromLeaves(leaves).at(-1)[0];
  const manifestCore = { ...capsule };
  delete manifestCore.manifest_digest;
  const manifestDigest = sha256Hex(frameAscii([MANIFEST_DOMAIN, sha256Hex(canonicalize(manifestCore))]));
  return {
    valid: root === capsule.root_digest && manifestDigest === capsule.manifest_digest,
    root_valid: root === capsule.root_digest,
    manifest_valid: manifestDigest === capsule.manifest_digest,
    computed_root_digest: root,
    computed_manifest_digest: manifestDigest,
  };
}
