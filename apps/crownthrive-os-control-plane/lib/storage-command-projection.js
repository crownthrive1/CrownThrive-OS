// Public-safe, read-only projection. Never return an upstream object by spreading it.
export const SCHEMA = 'ct.command.storage-status.v1';
const STATES = new Set([
  'READY', 'ACTIVE_VERIFIED', 'ACTIVE_PRIVATE_STORAGE_ARCHIVE_SCHEDULED',
  'COPIED_VERIFIED', 'COPYING', 'SEALED_VERIFIED', 'DEFERRED_PRESSURE',
  'DEFERRED_CONTINUITY_LOCK', 'DEFERRED_OVERLAP', 'DISABLED', 'HOLD',
  'NORMAL', 'RECOVERY', 'WATCH', 'ACCEPTING_ORDERS',
  'CATALOG_ACTIVE_CAPACITY_QUALIFICATION', 'STRIPE_ACTIVE_FULFILLMENT_GATED',
  'NOT_CUT_OVER', 'CUT_OVER', 'VERIFIED', 'FAILED', 'ERROR',
  'LANE_SNAPSHOTS_VERIFIED', 'ACTIVE_PROVIDER_VERIFIED_BACKFILL_IN_PROGRESS',
]);
const LANES = ['dail', 'backups', 'origins', 'delivery', 'masters', 'web3', 'children'];
const OFFER_NAMES = Object.freeze({
  'CT-SF-START-100': 'Vault Start', 'CT-SF-CREATOR-500': 'Creator Vault',
  'CT-SF-BUSINESS-1000': 'Business Vault', 'CT-SF-ARCHIVE-1000': 'Archive Vault',
});
const CONSUMERS = Object.freeze({
  'gretna-origins': 'Gretna Junction origins', 'locticians-origins': 'Locticians origins',
  'virality-origins': 'Virality Music origins', 'virality-masters': 'Virality Music masters',
  'virality-delivery': 'Virality Music delivery', 'go-flipbooks-delivery': 'Go Flipbooks delivery',
  'melanated-vault-masters': 'Melanated Vault masters', 'melanated-stock-masters': 'Melanated Stock masters',
  'melanated-tv-masters': 'Melanated TV masters', 'crownthrive-studios-masters': 'CrownThrive Studios masters',
  'little-crowns-private': 'Little Crowns private custody', 'chlom-web3-objects': 'CHLOM off-chain objects',
  'fabric-archive': 'PentaFabric archives', 'fabric-evidence': 'PentaFabric evidence',
  'melanin-magic-origins': 'Melanin Magic origins', 'melanated-voices-masters': 'Melanated Voices masters',
});
export const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
export function integer(value) {
  if (typeof value !== 'number' && !(typeof value === 'string' && /^\d+$/.test(value))) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}
const boolean = (value) => typeof value === 'boolean' ? value : null;
const state = (value) => STATES.has(value) ? value : 'UNKNOWN';
function instant(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T/.test(value)) return null;
  const time = Date.parse(value);
  return Number.isFinite(time) ? new Date(time).toISOString() : null;
}
const list = (value) => Array.isArray(value) ? value : [];

export function projectStorage(wasabi, catalog, retrievedAt) {
  const sourceAge = Date.parse(retrievedAt) - Date.parse(wasabi?.observed_at);
  const w = object(wasabi) && object(wasabi.archive) && object(wasabi.control) && instant(wasabi.observed_at) && Number.isFinite(sourceAge) && sourceAge >= -60_000 && sourceAge <= 90_000 ? wasabi : null;
  const c = object(catalog) && typeof catalog.sales_enabled === 'boolean' && Array.isArray(catalog.offers) ? catalog : null;
  const cursor = w?.archive;
  const control = w?.control;
  const meta = object(control?.metadata) ? control.metadata : {};
  const immutable = object(meta.dail_immutable_v2) ? meta.dail_immutable_v2 : {};
  const sectionNo = integer(cursor?.section_no);
  const currentSection = sectionNo !== null && sectionNo > 0 ? list(w?.sections).find((s) => object(s) && integer(s.section_no) === sectionNo) : null;
  const target = integer(control?.archive_section_events);
  const sectionEvents = integer(currentSection?.events);
  const validProgress = target !== null && target > 0 && sectionEvents !== null && sectionEvents <= target;
  const buckets = LANES.map((lane) => {
    const matches = list(w?.buckets).filter((b) => object(b) && b.lane === lane);
    const bucket = matches.length === 1 ? matches[0] : null;
    return { lane, state: state(bucket?.state), provider_verified_at: instant(bucket?.verified_at) };
  });
  const consumers = Object.entries(CONSUMERS).flatMap(([id, name]) => {
    const matches = list(w?.consumers).filter((x) => object(x) && x.consumer_id === id);
    if (matches.length !== 1) return [];
    const row = matches[0];
    return [{ name, backend_state: state(row.backend_state), cutover_state: state(row.site_cutover_state), external_delivery_enabled: boolean(row.external_delivery_enabled) }];
  });
  const offers = c ? Object.entries(OFFER_NAMES).flatMap(([id, name]) => {
    const matches = c.offers.filter((x) => object(x) && x.id === id);
    if (matches.length !== 1) return [];
    const row = matches[0];
    return [{ id, name, billing_amount_cents: integer(row.billing_amount_cents), billing_interval_months: integer(row.billing_interval_months), currency: row.currency === 'usd' ? 'usd' : null, included_bytes: integer(row.included_bytes), included_download_bytes: integer(row.included_download_bytes), catalog_binding_present: boolean(row.stripe_catalog_active), available: c.sales_enabled === true && row.available === true, state: state(row.state) }];
  }) : [];
  return {
    schema: SCHEMA,
    status: w && c ? 'OBSERVED' : w || c ? 'PARTIAL' : 'UNAVAILABLE',
    retrieved_at: instant(retrievedAt),
    source: { wasabi_status: w ? 'THRIVEBASE_READ' : 'UNAVAILABLE', catalog: c ? 'THRIVEBASE_READ' : 'UNAVAILABLE', wasabi_observed_at: instant(w?.observed_at), evidence_class: 'REGISTERED_PROVIDER_READBACK_NOT_NEW_PROVIDER_PROBE' },
    archive: w ? {
      state: state(cursor.state), enabled: boolean(cursor.enabled),
      total_archived_events: integer(cursor.exported_event_count), section_no: integer(cursor.section_no),
      section_events: sectionEvents, section_target_events: target,
      section_progress_percent: validProgress ? Math.round(sectionEvents / target * 10000) / 100 : null,
      next_shard_no: integer(cursor.next_shard_no), last_archived_sequence_id: integer(cursor.last_sequence_id),
      last_run_at: instant(cursor.last_run_at),
      sealed_sections_in_status: Array.isArray(w.sections) ? w.sections.filter((s) => object(s) && s.state === 'SEALED_VERIFIED').length : null,
      last_run_events_copied: integer(cursor.last_result?.events_copied),
      source_pruning_enabled: boolean(w.source_delete_enabled),
      hot_window: 'LOGICAL_LATEST_ONE_MILLION_ACTUAL_ROWS_NOT_PHYSICALLY_PRUNED',
      sequence_ids_are_event_counts: false,
    } : null,
    custody: w ? { buckets, consumers, registered_verified_objects: integer(w.objects?.verified_count), registered_bytes: integer(w.objects?.registered_bytes), retention_mode: ['COMPLIANCE', 'GOVERNANCE'].includes(immutable.retention_mode) ? immutable.retention_mode : null, retention_days: integer(immutable.retention_days), full_restore_proven_by_this_read: false, external_delivery_enabled_count: Array.isArray(w.consumers) ? consumers.filter((x) => x.external_delivery_enabled === true).length : null } : null,
    controls: w ? { writes_enabled: boolean(control.writes_enabled), local_write_budget_bytes: integer(control.upload_budget_bytes), local_write_stop_at: instant(control.safety_stop_at), balancer_mode: state(w.balancer?.mode), pressure: integer(w.balancer?.pressure), single_put_ceiling_bytes: integer(meta.max_supported_binary_ticket_bytes), largest_empirical_test_bytes: integer(meta.largest_live_qualification_object_bytes), independent_blockchain_or_ipfs_network: boolean(w.independent_blockchain_or_ipfs_network) } : null,
    commerce: c ? { sales_enabled: c.sales_enabled, activation_state: state(c.activation_state), offers, payment_execution_exposed: false, catalog_is_not_payment_or_fulfillment_proof: true } : null,
    privacy: { public_safe: true, read_only: true, raw_payloads_exposed: false, credentials_exposed: false, customer_records_exposed: false, signed_urls_exposed: false },
  };
}
