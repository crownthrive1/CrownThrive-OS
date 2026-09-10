const VERSION = '4.0.0';
const SNAPSHOT_AT = '2026-09-10T19:00:00.000Z';
const CANONICAL_ORIGIN = 'https://crown-thrive-os.vercel.app';
const DEFAULT_LIMIT = 250;
const MAX_LIMIT = 1000;

const DATABASE = Object.freeze({
  schemas: 79,
  tables: 2770,
  views: 30,
  materialized_views: 2,
  sequences: 106,
  routines: 4827,
  cron_jobs_total: 344,
  cron_jobs_active: 297,
  storage_buckets: 193,
  storage_buckets_public: 161,
  storage_buckets_private: 32,
});

const FAMILY_COUNTS = Object.freeze({
  dail: 267,
  wallet_ledger_treasury: 619,
  fabric_mesh_bridge_router: 1062,
  factory_builder_generator: 104,
  plugin_connector_integration: 373,
  contract_policy_license: 159,
  runtime_scheduler_queue: 517,
  registry_catalog_census: 766,
  agent_penta_oracle: 2065,
});

const SCHEMAS = Object.freeze([
  'adluxe_control','affiliate_control','api_marketplace_public','app_factory_provider','asrm','asset_census','auth',
  'chlom_identity','chlom_protocol','chlom_runtime','chlom_secrets','chlom_security_lab','chlom_wallet',
  'communications_evidence','cos_store','crm','cron','crownlytics_ingest','css_core','developer_commerce','extensions',
  'graphql','graphql_public','gretna','hosting_control','institutional_federation','institutional_versioning',
  'integration_control','internal','net','os_v2','penta_balancer','penta_certify','penta_contracts','penta_discovery',
  'penta_dnd','penta_docs','penta_gas','penta_help','penta_os20','penta_pm','penta_pm_fabric','penta_pr',
  'penta_runtime','penta_scribe','penta_security','penta_self','penta_task_runtime','penta_translate','penta_treasury',
  'pentaads_platform','pentagovernance','pentamocracy','pentas','pentatime','pgbouncer','pgmq','pgmq_public',
  'pgsodium','pgsodium_masks','product_factory','public','public_bridge','realtime','rewards_control','sacred_history',
  'sermon_commerce','storage','stripe','supabase_functions','supabase_migrations','thivebase_control','thivebase_private',
  'thrivebeacons','thriveledger','vault','virality_canon','virality_control','virality_site_private',
]);

const DAIL_PRIMARY = Object.freeze([
  { id: 'chlom_canonical_dail', name: 'CHLOM Canonical DAIL', class: 'dual', lane: 'Doctrine / Assumption / Intent / Lineage', estimated_rows: 1208358 },
  { id: 'intent_and_decision_log', name: 'Intent and Decision Log', class: 'dual', lane: 'Intent / Decision / Outcome', estimated_rows: 12313 },
  { id: 'human_dail', name: 'Human DAIL', class: 'human', lane: 'Founder decision / narrative', estimated_rows: 8939 },
  { id: 'crownthrive_dail', name: 'CrownThrive DAIL', class: 'machine', lane: 'Machine lifecycle', estimated_rows: 2317 },
  { id: 'dail_append_only_event_stream', name: 'DAIL Append-Only Event Stream', class: 'hybrid', lane: 'Append-only events', estimated_rows: 19264 },
]);

const DAIL_SUPPORTING = Object.freeze([
  'dail_canonical','dail_delivery_events','dail_route_receipts','pentagreen_event_store',
  'pentagreen_lineage_events','penta_event_stream_v1','pentafabric_events',
]);

const CONNECTORS = Object.freeze([
  'Ahrefs','CALL-E','Canva','ChatGPT Ads Manager','CoinGecko','CoinMarketCap','Consensus','CryptoAudit',
  'DigitalOcean','DoorDash','Etsy','Figma','Finances','Financial Datasets','GitHub','Gmail','GoDaddy',
  'Google Calendar','Google Contacts','Google Drive','Health','Jotform','MangaBoom','Manufact',
  'Microsoft Outlook Calendar','Microsoft Outlook Email','Microsoft Teams','Mintlify','MongoDB Atlas',
  'OpenAI Platform','Plugin Management','Realtor.com','Riverside','Semrush','ShareThis AI','Spotify',
  'Stripe','Supabase','Token Terminal','Uber Eats','Vercel','Zapier','Zoom','Files',
]);

const REPOSITORIES = Object.freeze([
  'CrownThrive-OS','CrownThrive-Dashboard','CrownThrive-Corridor','CrownThrive-Ecosystem','ThriveText-Hub',
  'ThriveEstate','CrownFluence','reward-hub','ThriveBase','MM-Suite','Go-Flipbooks','PentaAds',
  'PentaBrain','PentaPersonas','CrownLytics','CrownPulse','ThrivePush','ThriveTickets','ThrivePeer',
  'FindCliques','Locticians','CrownThriveU','AdLuxe-Network','Melanated-TV','Virality-Music',
]);

const RECORDS = [
  ...SCHEMAS.map((name) => ({
    id: `schema:${name}`,
    name,
    family: schemaFamily(name),
    source: 'ThriveBase',
    visibility: sensitiveSchema(name) ? 'restricted' : 'operator',
    status: 'indexed',
    kind: 'database_schema',
    description: sensitiveSchema(name)
      ? 'Schema existence and classification are indexed; contents require authenticated operator authority.'
      : 'Authoritative ThriveBase schema indexed in the governed estate census.',
  })),
  ...DAIL_PRIMARY.map((system) => ({
    id: `dail:${system.id}`,
    name: system.name,
    family: 'dail',
    source: 'ThriveBase',
    visibility: 'operator',
    status: 'primary',
    kind: 'dail_system',
    count: system.estimated_rows,
    description: `${system.class} DAIL · ${system.lane}. Row count is an estimated inventory snapshot, not a delivery claim.`,
  })),
  ...DAIL_SUPPORTING.map((name) => ({
    id: `dail-support:${name}`,
    name,
    family: 'dail',
    source: 'ThriveBase',
    visibility: 'operator',
    status: 'supporting',
    kind: 'dail_support_system',
    description: 'Supporting lineage, routing, event, or delivery-evidence surface.',
  })),
  ...REPOSITORIES.map((name) => ({
    id: `repo:${name.toLowerCase()}`,
    name,
    family: repositoryFamily(name),
    source: 'GitHub',
    visibility: 'operator',
    status: 'indexed',
    kind: 'software_repository',
    description: 'Repository identity is indexed. Private code, secrets, deployment variables, issues, and unpublished branches are not projected publicly.',
  })),
  ...CONNECTORS.map((name) => ({
    id: `connector:${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
    name,
    family: connectorFamily(name),
    source: 'Connectors',
    visibility: 'operator',
    status: ['Gmail','Google Calendar','Google Drive'].includes(name) ? 'installed' : 'discoverable',
    kind: 'capability_provider',
    description: 'Capability provider indexed at snapshot time. Connection, authorization, and permission state can vary; credentials are never projected.',
  })),
  { id: 'wallet:chlom', name: 'CHLOM Wallet', family: 'wallets', source: 'Command', visibility: 'public', status: 'enforced', kind: 'economic_gate', count: 6, description: 'Mandatory internal economic-mutation gate. Aggregate wallet count only; addresses, balances, owners, and transactions are restricted.' },
  { id: 'wallet:verified-ledger', name: 'Verified Internal Ledger Accounts', family: 'wallets', source: 'Command', visibility: 'public', status: 'verified', kind: 'ledger_accounts', count: 7, description: 'Aggregate verified-account count. Account identifiers, balances, entries, and actors are restricted.' },
  { id: 'wallet:bindings', name: 'Mandatory Wallet Service Bindings', family: 'wallets', source: 'Command', visibility: 'public', status: 'active', kind: 'service_bindings', count: 676, description: 'Authenticated economic services inherit the CHLOM Wallet requirement.' },
  { id: 'wallet:receipts', name: 'Wallet Gate Receipts', family: 'wallets', source: 'Command', visibility: 'public', status: 'indexed', kind: 'gate_receipts', count: 853, description: 'Aggregate decision-receipt count. Raw receipts, actors, payloads, and private evidence are operator-restricted.' },
  { id: 'wallet:agent', name: 'Agent Wallet Boundary', family: 'wallets', source: 'Command', visibility: 'public', status: 'stale_fail_closed', kind: 'movement_boundary', count: 0, description: 'Unattended external value limit remains zero while heartbeat freshness is not verified.' },
  { id: 'wallet:external', name: 'External Wallet Participation', family: 'wallets', source: 'Command', visibility: 'public', status: 'optional', kind: 'participation_boundary', description: 'An external wallet is not required to participate in CrownThrive internal economics.' },
  { id: 'wallet:card', name: 'Card-Issuing Rail', family: 'wallets', source: 'Command', visibility: 'public', status: 'provider_contract_required', kind: 'external_rail', description: 'Not represented as production without a legitimate issuer or BIN sponsor.' },
  { id: 'wallet:stablecoin', name: 'Stablecoin Checkout', family: 'wallets', source: 'Command', visibility: 'public', status: 'hold', kind: 'external_rail', description: 'Remains outside production until its independent release predicates pass.' },
  { id: 'fabric:pentafabric', name: 'PentaFabric', family: 'fabrics', source: 'ThriveBase', visibility: 'operator', status: 'indexed', kind: 'event_fabric', description: 'Cross-system event and evidence fabric represented through safe aggregate health and routing metadata.' },
  { id: 'fabric:penta-pm', name: 'Penta PM Fabric', family: 'fabrics', source: 'ThriveBase', visibility: 'operator', status: 'indexed', kind: 'coordination_fabric', description: 'Project, execution, and provider coordination fabric.' },
  { id: 'fabric:public-bridge', name: 'Public Bridge', family: 'fabrics', source: 'ThriveBase', visibility: 'public', status: 'bounded', kind: 'projection_bridge', description: 'Public-safe bridge that strips credentials, private payloads, actors, balances, and custody fields.' },
  { id: 'fabric:integration-control', name: 'Integration Control Plane', family: 'fabrics', source: 'ThriveBase', visibility: 'operator', status: 'indexed', kind: 'integration_fabric', description: 'Integration registrations, provider contracts, lifecycle evidence, and bounded execution status.' },
  { id: 'factory:product', name: 'Product Factory', family: 'factories', source: 'ThriveBase', visibility: 'operator', status: 'active', kind: 'product_factory', description: 'Governed product assembly, packaging, pricing, publication, and release workflow.' },
  { id: 'factory:app', name: 'App Factory Provider', family: 'factories', source: 'ThriveBase', visibility: 'operator', status: 'indexed', kind: 'application_factory', description: 'Application generation and provider-deployment custody.' },
  { id: 'factory:pentagreen', name: 'PentaGreen', family: 'factories', source: 'ThriveBase', visibility: 'operator', status: 'active', kind: 'commercial_factory', description: 'Commercialization, entitlement, fulfillment, and release routing.' },
  { id: 'factory:go-flipbooks', name: 'Go Flipbooks', family: 'factories', source: 'ThriveBase', visibility: 'public', status: 'production', kind: 'publishing_factory', description: 'Publication intake, validation, controlled reader, commerce, entitlement, and evidence corridor.' },
  { id: 'runtime:penta', name: 'Penta Runtime', family: 'runtimes', source: 'ThriveBase', visibility: 'operator', status: 'active', kind: 'execution_runtime', description: 'Penta execution, remediation, runs, queues, and evidence.' },
  { id: 'runtime:task', name: 'Penta Task Runtime', family: 'runtimes', source: 'ThriveBase', visibility: 'operator', status: 'active', kind: 'task_runtime', description: 'Task custody, leases, attempts, terminal state, and replay metadata.' },
  { id: 'runtime:time', name: 'PentaTime', family: 'runtimes', source: 'ThriveBase', visibility: 'operator', status: 'active', kind: 'scheduler', description: 'Wake requests, schedules, execution cadence, and temporal coordination.' },
  { id: 'runtime:cron', name: 'Scheduled Jobs', family: 'runtimes', source: 'ThriveBase', visibility: 'operator', status: 'active', kind: 'scheduler_inventory', count: 297, description: '297 of 344 scheduled jobs were active at the authoritative census snapshot.' },
  { id: 'contracts:chlom', name: 'CHLOM Contracts and Policy', family: 'contracts', source: 'ThriveBase', visibility: 'operator', status: 'indexed', kind: 'governance_contracts', description: 'Authority, rights, licensing, policy, attestations, disputes, royalties, treasury, and governance contracts.' },
  { id: 'contracts:wallet-cert', name: 'CHLOM Wallet Production Certificate', family: 'contracts', source: 'Command', visibility: 'public', status: 'certified', kind: 'certificate', description: 'ct.cert.chlom-wallet.v3.20260904034831436.fd4578817c96' },
  { id: 'contracts:dail-assurance', name: 'DAIL Assurance Contract', family: 'contracts', source: 'Command', visibility: 'public', status: 'verified_prefix_valid_catchup_pending', kind: 'assurance_contract', description: 'Previously verified evidence remains valid while new events await the next checkpoint.' },
  { id: 'documents:drive', name: 'CrownThrive Empire Drive', family: 'documents', source: 'Google Drive', visibility: 'operator', status: 'indexed_sample', kind: 'drive', count: 100, description: 'At least 100 root metadata entries were observed. Filenames and contents are not indiscriminately projected.' },
  { id: 'documents:docs', name: 'Google Docs', family: 'documents', source: 'Google Drive', visibility: 'operator', status: 'minimum_count', kind: 'documents', count: 100, description: 'At least 100 native Docs were observed through a bounded census query.' },
  { id: 'documents:sheets', name: 'Google Sheets', family: 'documents', source: 'Google Drive', visibility: 'operator', status: 'minimum_count', kind: 'spreadsheets', count: 100, description: 'At least 100 native Sheets were observed through a bounded census query.' },
  { id: 'documents:chats', name: 'Chats, Email, and Collaboration Bodies', family: 'documents', source: 'Communications', visibility: 'restricted', status: 'class_indexed', kind: 'private_communications', description: 'Source classes and lifecycle metadata may be indexed. Raw bodies, attachments, recipients, private threads, and personal correspondence are restricted.' },
  { id: 'documents:library', name: 'Chat and Library Files', family: 'documents', source: 'Files', visibility: 'operator', status: 'available', kind: 'file_library', description: 'Cross-chat file library is available for governed retrieval. File content remains subject to source scope and access control.' },
  { id: 'secrets:vault', name: 'Secrets and Credential Material', family: 'restricted', source: 'Vault', visibility: 'restricted', status: 'existence_only', kind: 'secret_class', description: 'Credential existence and rotation state may be reported to authorized operators. Secret values are never exposed in Command.' },
  { id: 'privacy:identities', name: 'Private Identities and Actors', family: 'restricted', source: 'Identity', visibility: 'restricted', status: 'existence_only', kind: 'identity_class', description: 'Aggregate counts and authorization posture may be visible. Personal identities and actor linkage require explicit authority.' },
  { id: 'privacy:balances', name: 'Balances and Transaction Bodies', family: 'restricted', source: 'Ledger', visibility: 'restricted', status: 'existence_only', kind: 'financial_class', description: 'Economic-gate state is visible; balances, transaction bodies, account identifiers, and personal financial data are not public.' },
];

function schemaFamily(name) {
  if (name.includes('dail')) return 'dail';
  if (name.includes('wallet') || name.includes('ledger') || name.includes('treasury')) return 'wallets';
  if (name.includes('fabric') || name.includes('bridge') || name.includes('integration')) return 'fabrics';
  if (name.includes('factory')) return 'factories';
  if (name.includes('contract') || name.includes('protocol') || name.includes('governance') || name.includes('mocracy')) return 'contracts';
  if (name.includes('runtime') || name.includes('time') || name === 'cron' || name === 'pgmq') return 'runtimes';
  if (name.includes('docs') || name.includes('storage')) return 'documents';
  if (name.includes('ads') || name.includes('commerce') || name === 'stripe') return 'commerce';
  if (name.includes('penta')) return 'agents';
  return 'data';
}

function sensitiveSchema(name) {
  return name.includes('secrets') || name.includes('private') || name === 'vault' || name === 'auth' || name.includes('identity');
}

function repositoryFamily(name) {
  const value = name.toLowerCase();
  if (value.includes('penta')) return 'agents';
  if (value.includes('base') || value.includes('os') || value.includes('dashboard')) return 'software';
  if (value.includes('flipbook') || value.includes('music') || value.includes('tv')) return 'publishing';
  if (value.includes('reward') || value.includes('affiliate') || value.includes('ads')) return 'commerce';
  return 'software';
}

function connectorFamily(name) {
  if (['GitHub','Vercel','Supabase','DigitalOcean','MongoDB Atlas','Manufact','Mintlify','OpenAI Platform'].includes(name)) return 'software';
  if (['Gmail','Google Calendar','Google Contacts','Google Drive','Microsoft Outlook Calendar','Microsoft Outlook Email','Microsoft Teams','Zoom','Files'].includes(name)) return 'documents';
  if (['Stripe','Finances','Financial Datasets','CoinGecko','CoinMarketCap','CryptoAudit','Token Terminal'].includes(name)) return 'commerce';
  if (['Ahrefs','Semrush','ChatGPT Ads Manager','ShareThis AI'].includes(name)) return 'plugins';
  return 'plugins';
}

function params(request) {
  try {
    return new URL(String(request?.url || '/'), CANONICAL_ORIGIN).searchParams;
  } catch {
    return new URLSearchParams();
  }
}

function clean(value, maximum = 120) {
  return String(value || '').trim().toLowerCase().slice(0, maximum);
}

function limit(value) {
  const parsed = Number(value);
  return Number.isInteger(parsed) ? Math.min(Math.max(parsed, 1), MAX_LIMIT) : DEFAULT_LIMIT;
}

function send(response, status, payload, head = false) {
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
  response.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()');
  response.setHeader('X-CrownThrive-Estate-State', payload?.status || 'UNKNOWN');
  if (head) return response.status(status).end();
  return response.status(status).json(payload);
}

export default async function handler(request, response) {
  const head = request.method === 'HEAD';
  if (request.method !== 'GET' && !head) {
    response.setHeader('Allow', 'GET, HEAD');
    return send(response, 405, { schema: 'ct.command.estate-api.v4', status: 'REJECTED', error: 'method_not_allowed', pass_manufactured: false });
  }

  const search = params(request);
  const q = clean(search.get('q'), 200);
  const family = clean(search.get('family'));
  const source = clean(search.get('source'));
  const visibility = clean(search.get('visibility'));
  const start = Math.max(0, Number(search.get('offset')) || 0);
  const take = limit(search.get('limit'));

  const filtered = RECORDS.filter((record) => {
    if (family && clean(record.family) !== family) return false;
    if (source && clean(record.source) !== source) return false;
    if (visibility && clean(record.visibility) !== visibility) return false;
    if (!q) return true;
    return [record.name,record.family,record.source,record.visibility,record.status,record.kind,record.description]
      .some((value) => clean(value, 1000).includes(q));
  });

  const payload = {
    schema: 'ct.command.estate-api.v4',
    version: VERSION,
    status: 'PARTIAL',
    state_reason: 'COMPLETE_FAMILY_CENSUS_WITH_BOUNDED_SOURCE_SAMPLES_AND_RESTRICTED_PRIVATE_CONTENT',
    census: {
      database: DATABASE,
      indexed_object_families: FAMILY_COUNTS,
      family_counts_overlap: true,
      family_count_note: 'Object-family totals overlap because one database object may match multiple governed families.',
      github_repositories_observed: 100,
      github_repositories_enumerated_in_public_snapshot: REPOSITORIES.length,
      capability_providers_discoverable: CONNECTORS.length,
      drive_root_entries_observed_minimum: 100,
      native_docs_observed_minimum: 100,
      native_sheets_observed_minimum: 100,
      edge_function_exact_count: null,
      edge_function_count_state: 'MANAGEMENT_PLANE_ENUMERATED_COUNT_WITHHELD_UNTIL_DEDUPLICATED',
    },
    dail: {
      primary_systems: DAIL_PRIMARY,
      supporting_systems: DAIL_SUPPORTING,
      current_assurance_source: '/api/command',
      delivery_claim_policy: 'PENDING_REMAINS_PENDING_UNTIL_TERMINAL_DELIVERY_READBACK',
    },
    visibility_contract: {
      public: 'Aggregate counts, system names, nonsecret status, release boundaries, and public-safe evidence.',
      operator: 'Authenticated inventory metadata, lineage indexes, health, ownership classes, and evidence references.',
      restricted: 'Secrets, credentials, raw private documents, correspondence bodies, PII, wallet/account identifiers, balances, transactions, private payloads, and signing material.',
      public_raw_private_data: false,
      credential_material_exposed: false,
      wallet_identifiers_exposed: false,
      balances_exposed: false,
      private_communications_exposed: false,
      private_document_bodies_exposed: false,
    },
    source_coverage: [
      { source: 'ThriveBase', state: 'authoritative_census', coverage: 'schemas, objects, routines, schedules, storage, DAIL, wallet, fabrics, runtimes, factories, contracts' },
      { source: 'GitHub', state: 'repository_census', coverage: '100 repositories observed; representative public-safe identities enumerated' },
      { source: 'Google Drive', state: 'bounded_metadata_census', coverage: 'root metadata, Docs, Sheets, governed publication and evidence custody' },
      { source: 'Connectors', state: 'capability_census', coverage: '44 discoverable providers; authorization varies' },
      { source: 'Command APIs', state: 'live_overlay', coverage: 'wallet, DAIL assurance, operations, health, providers, routes, commercial catalog' },
      { source: 'Chats and communications', state: 'restricted_class_index', coverage: 'source classes and lifecycle only; raw bodies not public' },
    ],
    filters: { q, family: family || null, source: source || null, visibility: visibility || null, limit: take, offset: start },
    total_records: filtered.length,
    returned_records: filtered.slice(start, start + take).length,
    records: filtered.slice(start, start + take),
    provenance: {
      snapshot_at: SNAPSHOT_AT,
      generated_at: new Date().toISOString(),
      database_source: 'ThriveBase system-catalog census',
      repository_source: 'GitHub repository census',
      drive_source: 'Google Drive bounded metadata census',
      connector_source: 'capability-provider discovery snapshot',
      dynamic_overlay_endpoints: ['/api/command','/api/operations','/api/catalog','/api/health'],
      pass_manufactured: false,
    },
    controls: {
      read_only_projection: true,
      economic_mutations_exposed: false,
      external_money_movement_exposed: false,
      raw_private_evidence_public: false,
      authenticated_operator_plane_separate: true,
    },
    pass_manufactured: false,
  };

  return send(response, 200, payload, head);
}
