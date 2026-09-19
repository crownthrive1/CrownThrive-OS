begin;

create schema if not exists virality_control;

revoke all on schema virality_control from public, anon, authenticated;
grant usage on schema virality_control to service_role;

create table if not exists virality_control.asset_registry (
  asset_id uuid primary key default gen_random_uuid(),
  canonical_key text not null unique,
  title text not null,
  edition_label text not null,
  asset_class text not null check (
    asset_class in (
      'book', 'printable', 'epub', 'audio', 'video', 'image',
      'workbook', 'bundle', 'companion', 'license', 'other'
    )
  ),
  governing_world text,
  rights_state text not null default 'pending_validation' check (
    rights_state in ('pending_validation', 'cleared', 'restricted', 'disputed', 'expired', 'blocked')
  ),
  release_state text not null default 'intake' check (
    release_state in ('intake', 'qa', 'approved', 'published', 'archived', 'blocked')
  ),
  monetization_state text not null default 'not_eligible' check (
    monetization_state in ('not_eligible', 'eligible', 'listed', 'active', 'suspended')
  ),
  canonicality_state text not null default 'candidate' check (
    canonicality_state in ('candidate', 'canonical', 'variant', 'retired', 'disputed')
  ),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists virality_control.asset_versions (
  version_id uuid primary key default gen_random_uuid(),
  asset_id uuid not null references virality_control.asset_registry(asset_id) on delete restrict,
  version_no integer not null default 1 check (version_no > 0),
  format_role text not null check (
    format_role in ('distribution_pdf', 'editable_source', 'epub', 'printable', 'audio_master', 'cover', 'other')
  ),
  source_filename text not null,
  canonical_filename text not null,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  mime_type text not null,
  byte_size bigint not null check (byte_size >= 0),
  page_count integer check (page_count is null or page_count > 0),
  drive_file_id text,
  drive_verified_at timestamptz,
  storage_bucket text,
  storage_path text,
  binary_state text not null default 'supabase_pending' check (
    binary_state in ('drive_verified', 'supabase_pending', 'dual_verified', 'quarantined', 'rejected')
  ),
  qa_state text not null default 'pending' check (
    qa_state in ('pending', 'verified', 'hold', 'quarantined', 'rejected')
  ),
  accessibility_state text not null default 'unverified' check (
    accessibility_state in ('unverified', 'tagging_required', 'tagged_unverified_pdfua', 'verified', 'not_applicable')
  ),
  visual_state text not null default 'unverified' check (
    visual_state in ('unverified', 'verified', 'upgrade_recommended', 'rejected')
  ),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (asset_id, version_no, format_role),
  unique (sha256),
  check ((storage_bucket is null and storage_path is null) or (storage_bucket is not null and storage_path is not null))
);

create index if not exists asset_versions_asset_id_idx
  on virality_control.asset_versions(asset_id);

create unique index if not exists asset_versions_storage_object_uidx
  on virality_control.asset_versions(storage_bucket, storage_path)
  where storage_bucket is not null and storage_path is not null;

create table if not exists virality_control.asset_references (
  reference_id uuid primary key default gen_random_uuid(),
  version_id uuid not null references virality_control.asset_versions(version_id) on delete cascade,
  source_system text not null,
  reference_type text not null,
  reference_value text not null,
  verification_state text not null default 'unverified' check (
    verification_state in ('unverified', 'verified', 'stale', 'blocked')
  ),
  verified_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (source_system, reference_type, reference_value)
);

create index if not exists asset_references_version_id_idx
  on virality_control.asset_references(version_id);

create table if not exists virality_control.sync_runs (
  run_id uuid primary key default gen_random_uuid(),
  provider text not null check (provider = 'soundcloud'),
  scheduled_for date not null,
  attempt smallint not null default 1 check (attempt > 0),
  status text not null default 'running' check (
    status in ('running', 'succeeded', 'partial', 'failed', 'skipped', 'blocked')
  ),
  evidence_state text not null default 'blocked' check (
    evidence_state in ('verified', 'observed_unverified', 'blocked')
  ),
  request_count integer not null default 0 check (request_count >= 0),
  response_count integer not null default 0 check (response_count >= 0),
  raw_digest text,
  raw_storage_prefix text,
  error_code text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  unique (provider, scheduled_for, attempt)
);

create table if not exists virality_control.soundcloud_entities (
  entity_type text not null check (entity_type in ('account', 'track')),
  provider_entity_id text not null,
  asset_id uuid references virality_control.asset_registry(asset_id) on delete set null,
  title text,
  permalink_url text,
  duration_ms bigint check (duration_ms is null or duration_ms >= 0),
  active boolean not null default true,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  provider_payload_digest text,
  metadata jsonb not null default '{}'::jsonb,
  primary key (entity_type, provider_entity_id)
);

create index if not exists soundcloud_entities_asset_id_idx
  on virality_control.soundcloud_entities(asset_id);

create table if not exists virality_control.soundcloud_metric_snapshots (
  snapshot_id uuid primary key default gen_random_uuid(),
  sync_run_id uuid not null references virality_control.sync_runs(run_id) on delete restrict,
  snapshot_date date not null,
  entity_type text not null,
  provider_entity_id text not null,
  asset_id uuid references virality_control.asset_registry(asset_id) on delete set null,
  evidence_state text not null check (
    evidence_state in ('verified', 'observed_unverified', 'blocked')
  ),
  plays bigint check (plays is null or plays >= 0),
  likes bigint check (likes is null or likes >= 0),
  reposts bigint check (reposts is null or reposts >= 0),
  comments bigint check (comments is null or comments >= 0),
  downloads bigint check (downloads is null or downloads >= 0),
  followers bigint check (followers is null or followers >= 0),
  track_count bigint check (track_count is null or track_count >= 0),
  metrics jsonb not null default '{}'::jsonb,
  collected_at timestamptz not null default now(),
  foreign key (entity_type, provider_entity_id)
    references virality_control.soundcloud_entities(entity_type, provider_entity_id),
  unique (snapshot_date, entity_type, provider_entity_id)
);

create index if not exists soundcloud_snapshots_sync_run_idx
  on virality_control.soundcloud_metric_snapshots(sync_run_id);

create index if not exists soundcloud_snapshots_asset_date_idx
  on virality_control.soundcloud_metric_snapshots(asset_id, snapshot_date desc);

create table if not exists virality_control.promotion_recommendations (
  recommendation_id uuid primary key default gen_random_uuid(),
  algorithm_id text not null references institutional_federation.algorithm_registry(algorithm_id) on delete restrict,
  asset_id uuid not null references virality_control.asset_registry(asset_id) on delete restrict,
  target_surface text not null,
  action_type text not null,
  score numeric(8,6) not null check (score between 0 and 1),
  evidence_start date not null,
  evidence_end date not null,
  evidence_digest text not null,
  reasons jsonb not null,
  safeguards jsonb not null default '{}'::jsonb,
  state text not null default 'proposed' check (
    state in ('proposed', 'approved', 'rejected', 'expired', 'executing', 'succeeded', 'failed', 'revoked')
  ),
  human_approval_required boolean not null default true,
  reviewed_by text,
  reviewed_at timestamptz,
  decision_reason text,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (evidence_end >= evidence_start),
  unique (algorithm_id, asset_id, target_surface, action_type, evidence_digest)
);

create index if not exists promotion_recommendations_algorithm_id_idx
  on virality_control.promotion_recommendations(algorithm_id);

create index if not exists promotion_recommendations_asset_id_idx
  on virality_control.promotion_recommendations(asset_id);

create index if not exists promotion_recommendations_queue_idx
  on virality_control.promotion_recommendations(state, created_at);

create table if not exists virality_control.promotion_recommendation_events (
  event_id uuid primary key default gen_random_uuid(),
  recommendation_id uuid not null references virality_control.promotion_recommendations(recommendation_id) on delete restrict,
  event_type text not null,
  actor_ref text not null,
  reason text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists promotion_events_recommendation_id_idx
  on virality_control.promotion_recommendation_events(recommendation_id, created_at);

alter table virality_control.asset_registry enable row level security;
alter table virality_control.asset_versions enable row level security;
alter table virality_control.asset_references enable row level security;
alter table virality_control.sync_runs enable row level security;
alter table virality_control.soundcloud_entities enable row level security;
alter table virality_control.soundcloud_metric_snapshots enable row level security;
alter table virality_control.promotion_recommendations enable row level security;
alter table virality_control.promotion_recommendation_events enable row level security;

revoke all on all tables in schema virality_control from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema virality_control to service_role;

drop policy if exists asset_registry_service_role_all on virality_control.asset_registry;
create policy asset_registry_service_role_all on virality_control.asset_registry
  for all to service_role using (true) with check (true);

drop policy if exists asset_versions_service_role_all on virality_control.asset_versions;
create policy asset_versions_service_role_all on virality_control.asset_versions
  for all to service_role using (true) with check (true);

drop policy if exists asset_references_service_role_all on virality_control.asset_references;
create policy asset_references_service_role_all on virality_control.asset_references
  for all to service_role using (true) with check (true);

drop policy if exists sync_runs_service_role_all on virality_control.sync_runs;
create policy sync_runs_service_role_all on virality_control.sync_runs
  for all to service_role using (true) with check (true);

drop policy if exists soundcloud_entities_service_role_all on virality_control.soundcloud_entities;
create policy soundcloud_entities_service_role_all on virality_control.soundcloud_entities
  for all to service_role using (true) with check (true);

drop policy if exists soundcloud_metric_snapshots_service_role_all on virality_control.soundcloud_metric_snapshots;
create policy soundcloud_metric_snapshots_service_role_all on virality_control.soundcloud_metric_snapshots
  for all to service_role using (true) with check (true);

drop policy if exists promotion_recommendations_service_role_all on virality_control.promotion_recommendations;
create policy promotion_recommendations_service_role_all on virality_control.promotion_recommendations
  for all to service_role using (true) with check (true);

drop policy if exists promotion_recommendation_events_service_role_all on virality_control.promotion_recommendation_events;
create policy promotion_recommendation_events_service_role_all on virality_control.promotion_recommendation_events
  for all to service_role using (true) with check (true);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'virality-private-assets',
  'virality-private-assets',
  false,
  1073741824,
  array[
    'application/pdf',
    'application/epub+zip',
    'application/zip',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'audio/mpeg',
    'audio/wav',
    'audio/x-wav',
    'image/jpeg',
    'image/png',
    'image/webp'
  ]
)
on conflict (id) do update set
  public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types,
  updated_at = now();

insert into integration_control.services (
  service_id, display_name, base_url, docs_url, auth_scheme, credential_ref,
  credential_state, integration_state, write_gate, monthly_request_limit, timezone, metadata
)
values
  (
    'virality_music',
    'Virality Music by CrownThrive',
    'https://vm.crownthrive.com',
    'https://crown-thrive.mintlify.io/platforms/virality-music-institutional-registry',
    'internal_service',
    'not_configured',
    'unverified',
    'documented',
    false,
    null,
    'UTC',
    jsonb_build_object(
      'governance_owner', 'CrownThrive, LLC',
      'rights_authority', 'CHLOM',
      'licensing_route', 'Good Shit Only',
      'measurement_authority', 'CrownLytics'
    )
  ),
  (
    'soundcloud',
    'SoundCloud for Virality Music',
    'https://api.soundcloud.com',
    'https://developers.soundcloud.com/docs/api/',
    'oauth2',
    'vault:soundcloud.access_token',
    'unverified',
    'documented',
    false,
    null,
    'UTC',
    jsonb_build_object(
      'account_slug', 'crownthrive',
      'account_url', 'https://soundcloud.com/crownthrive',
      'daily_sync_state', 'blocked_pending_authenticated_read',
      'provider_write_prohibited', true
    )
  )
on conflict (service_id) do update set
  display_name = excluded.display_name,
  base_url = excluded.base_url,
  docs_url = excluded.docs_url,
  auth_scheme = excluded.auth_scheme,
  credential_ref = excluded.credential_ref,
  credential_state = excluded.credential_state,
  integration_state = excluded.integration_state,
  write_gate = excluded.write_gate,
  monthly_request_limit = excluded.monthly_request_limit,
  timezone = excluded.timezone,
  metadata = integration_control.services.metadata || excluded.metadata,
  updated_at = now();

insert into integration_control.mcp_tools (
  tool_name, service_id, operation_key, risk_class, enabled,
  requires_human_approval, input_schema, output_schema, notes
)
values
  ('virality.assets.list', 'virality_music', 'assets.list', 'D0', false, false, '{}'::jsonb, '{}'::jsonb, 'Disabled until service-role read certification.'),
  ('virality.assets.get', 'virality_music', 'assets.get', 'D0', false, false, '{}'::jsonb, '{}'::jsonb, 'Disabled until identifier and field-boundary certification.'),
  ('virality.stats.current', 'virality_music', 'stats.current', 'D0', false, false, '{}'::jsonb, '{}'::jsonb, 'Disabled until dated snapshot read certification.'),
  ('virality.stats.history', 'virality_music', 'stats.history', 'D0', false, false, '{}'::jsonb, '{}'::jsonb, 'Disabled until pagination and evidence-state certification.'),
  ('virality.recommendations.list', 'virality_music', 'recommendations.list', 'D1', false, false, '{}'::jsonb, '{}'::jsonb, 'Recommendation-only shadow mode.'),
  ('virality.recommendations.decide', 'virality_music', 'recommendations.decide', 'D2', false, true, '{}'::jsonb, '{}'::jsonb, 'Human approval required; no direct placement write.'),
  ('soundcloud.sync.daily', 'soundcloud', 'sync.daily', 'D1', false, false, '{}'::jsonb, '{}'::jsonb, 'Disabled until authenticated bounded-read proof.'),
  ('virality.promotion.execute', 'virality_music', 'promotion.execute', 'D3', false, true, '{}'::jsonb, '{}'::jsonb, 'Not implemented. Requires separate release, rights, commerce, experiment, and rollback certification.')
on conflict (tool_name) do update set
  service_id = excluded.service_id,
  operation_key = excluded.operation_key,
  risk_class = excluded.risk_class,
  enabled = false,
  requires_human_approval = excluded.requires_human_approval,
  notes = excluded.notes,
  updated_at = now();

insert into integration_control.governed_deferrals (
  deferral_id, scope_type, scope_key, title, status, risk_class,
  external_dependency, unresolved_condition, accountable_owner,
  compensating_controls, evidence_refs, reopening_trigger,
  review_due_at, notes
)
values
  (
    'CT-VM-DEF-SUPABASE-STORAGE-20260820',
    'provider_state',
    'virality-private-assets',
    'Virality binary parity in Supabase Storage',
    'candidate',
    'D1',
    true,
    'The connected Supabase capability does not expose Storage object upload operations, so the 16 private binaries cannot yet receive certified object copies.',
    'Kavonte Jones Sr.',
    jsonb_build_array(
      'Private Google Drive custody copy verified by exact byte-size readback.',
      'Private Supabase bucket created with no public access.',
      'Operational rows use binary_state=supabase_pending and contain no false object path.'
    ),
    jsonb_build_array(
      'CT-VM-ASSET-INGEST-2026-08-20-V1',
      'CrownThrive_Virality-Music_Asset-Manifest_2026-08-20_v1.json'
    ),
    'Enable the Supabase Storage feature for the connected MCP or provide an approved server-side service-role upload path, then upload, hash-verify, and set binary_state=dual_verified.',
    '2026-08-27T17:00:00Z'::timestamptz,
    'NEED_TO_DO. This deferral is not a PASS and does not authorize public delivery from Supabase.'
  ),
  (
    'CT-VM-DEF-SOUNDCLOUD-AUTH-20260820',
    'provider_state',
    'soundcloud-daily-read',
    'Authenticated SoundCloud daily statistics read',
    'candidate',
    'D1',
    true,
    'No authenticated SoundCloud API credential or export adapter is certified in Vault. Public page observations cannot replace Artist Studio totals.',
    'Kavonte Jones Sr.',
    jsonb_build_array(
      'Preserve the August 13, 2026 verified baseline.',
      'Record blocked or observed_unverified scans without overwriting verified totals.',
      'Keep provider writes and promotion execution disabled.'
    ),
    jsonb_build_array(
      'https://vm.crownthrive.com',
      'https://soundcloud.com/crownthrive'
    ),
    'Configure a least-privilege SoundCloud read credential or repeatable signed export, then complete bounded pagination, request-budget, freshness, and field-mapping tests.',
    '2026-08-27T17:00:00Z'::timestamptz,
    'NEED_TO_DO. Daily observation automation may run, but authenticated provider totals remain blocked.'
  )
on conflict (deferral_id) do update set
  unresolved_condition = excluded.unresolved_condition,
  accountable_owner = excluded.accountable_owner,
  compensating_controls = excluded.compensating_controls,
  evidence_refs = excluded.evidence_refs,
  reopening_trigger = excluded.reopening_trigger,
  review_due_at = excluded.review_due_at,
  notes = excluded.notes,
  updated_at = now();

insert into virality_control.asset_registry (
  canonical_key, title, edition_label, asset_class, governing_world,
  rights_state, release_state, monetization_state, canonicality_state, metadata
)
values
  ('VM-BOOK-ASK-ASHLEY-V2-IC', 'Ask Ashley Who Got Paid', 'Version 2 Illustrated Collector Edition', 'book', 'TrapOpera', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{"lineage_adjudication":"Compare against Who Paid Ashley? canonical lineage"}'::jsonb),
  ('VM-BOOK-DARKER-BERRY-PEC', 'Darker the Berry, Sweeter the Lie', 'The Privileged Envelope Chronicle', 'book', 'TrapOpera', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{}'::jsonb),
  ('VM-BOOK-MARCUS-FEE', 'Marcus: A Good Man with a Pussy Problem', 'Forbidden Evidence Edition', 'book', 'TrapOpera', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{"audience":"18+"}'::jsonb),
  ('VM-BOOK-KIARA-FUI', 'Who the Fuck Is Kiara? The Other Woman Has Evidence', 'First Unfiltered Illustrated Edition', 'book', 'TrapOpera', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{"audience":"18+"}'::jsonb),
  ('VM-BOOK-MAYBELLE-FI', 'Maybelle: The Woman Who Kept the Table', 'First Illustrated Edition', 'book', 'Willie and Maybelle Jenkins', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{}'::jsonb),
  ('VM-BOOK-WILLIE-FI', 'Willie: The Legend', 'First Illustrated Edition', 'book', 'Willie and Maybelle Jenkins', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{}'::jsonb),
  ('VM-BOOK-TO-HELL-TASHA', 'To Hell We Go!', 'Tasha Triple-Life Evidence Edition', 'book', 'TrapOpera', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{}'::jsonb),
  ('VM-BOOK-WRH-V2-A-231', 'What Really Happened', 'Version 2 Illustrated Collector Edition - Variant A - 231 pages', 'book', 'TrapOpera', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{"variant_group":"VM-BOOK-WRH-V2","canonical_selection_required":true,"audit_disposition":"canonical_candidate","print_gate":"illustrations_approximately_171_ppi"}'::jsonb),
  ('VM-BOOK-WRH-V2-B-227', 'What Really Happened', 'Version 2 Illustrated Collector Edition - Variant B - 227 pages', 'book', 'TrapOpera', 'pending_validation', 'blocked', 'not_eligible', 'variant', '{"variant_group":"VM-BOOK-WRH-V2","canonical_selection_required":true,"audit_disposition":"alternate_or_superseded_variant_candidate"}'::jsonb),
  ('VM-BOOK-ALMA-V2-IL', 'Alma Knight Carter: The Woman Who Taught Money to Stay', 'Version 2 Illustrated Legacy Edition', 'book', 'TrapOpera', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{}'::jsonb),
  ('VM-BOOK-THIRD-LIFE-V2-IC', 'The Third Life Had the Wrong Name', 'Version 2 Illustrated Collector Edition', 'book', 'TrapOpera', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{}'::jsonb),
  ('VM-BOOK-LEONARD-CLARENCE-IF', 'Leonard & Clarence: Two Damn Fools', 'Illustrated Flagship Edition', 'book', 'Willie and Maybelle Jenkins', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{"source_pair":"verified_normalized_text_match"}'::jsonb),
  ('VM-BOOK-LEONARD-COFFIELD-IW', 'Leonard Coffield: The Fool Who Saw Everything', 'First Illustrated Witness Edition', 'book', 'Willie and Maybelle Jenkins', 'pending_validation', 'qa', 'not_eligible', 'candidate', '{"source_pair":"verified_normalized_text_match"}'::jsonb),
  ('VM-BOOK-ROSETTA-IL', 'Rosetta: The Woman Who Made the Legend Wash Dishes', 'Illustrated Legacy Edition', 'book', 'Willie and Maybelle Jenkins', 'pending_validation', 'blocked', 'not_eligible', 'candidate', '{"design_gate":"rebuild_required","source_gate":"editable_source_missing","audit_disposition":"hold_rebuild"}'::jsonb)
on conflict (canonical_key) do update set
  title = excluded.title,
  edition_label = excluded.edition_label,
  asset_class = excluded.asset_class,
  governing_world = excluded.governing_world,
  metadata = virality_control.asset_registry.metadata || excluded.metadata,
  updated_at = now();

insert into virality_control.asset_versions (
  asset_id, version_no, format_role, source_filename, canonical_filename, sha256,
  mime_type, byte_size, page_count, drive_file_id, drive_verified_at,
  binary_state, qa_state, accessibility_state, visual_state, metadata
)
values
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-ASK-ASHLEY-V2-IC'), 1, 'distribution_pdf', '01-Ask_Ashley_Who_Got_Paid_Version_2_Illustrated_Collector_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Ask-Ashley-Who-Got-Paid_V2-Illustrated-Collector_2026-08-20_v1.pdf', 'ea90e2f98cb41cecc1de88417b714cc216abffa9cf8d3b474dd874aaf39caa9e', 'application/pdf', 35672517, 319, '1RBdSj3V-HRXm4ZFQzJ4vRfdRfeznqdsF', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-DARKER-BERRY-PEC'), 1, 'distribution_pdf', '02-Darker_The_Berry_Sweeter_The_Lie_Privileged_Envelope_Chronicle.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Darker-the-Berry-Sweeter-the-Lie_Privileged-Envelope-Chronicle_2026-08-20_v1.pdf', '4dcd664ca1fb9cfc56973f71ab1cb642739ca7b9c9a6a748de5c50bbcdc31923', 'application/pdf', 5120224, 184, '17Zf4R3z6kx2pv-HYv3t-LAjq953T7MFp', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-MARCUS-FEE'), 1, 'distribution_pdf', '03-Marcus_A_Good_Man_With_A_Pussy_Problem_Forbidden_Evidence_Edition-1-.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Marcus-A-Good-Man-With-a-Pussy-Problem_Forbidden-Evidence_2026-08-20_v1.pdf', '841d87eb974fd386bd02a57e441317efb76414e6db37e0dfde54dd4bc99ae352', 'application/pdf', 39118530, 246, '1iE092aYQl7xBLH2UU7RBMkqp5beELPJ0', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{"audience":"18+"}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-KIARA-FUI'), 1, 'distribution_pdf', '04-Who_The_Fuck_Is_Kiara_First_Unfiltered_Illustrated_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Who-the-Fuck-Is-Kiara_First-Unfiltered-Illustrated_2026-08-20_v1.pdf', '94320b741ac201dc89e33750ae0569d512a7405347a06e79656c5edddbcfcc5e', 'application/pdf', 36091966, 176, '1Nram0h0fnAtM3Nv5mHs4LAfsr0zZ025u', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{"audience":"18+"}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-MAYBELLE-FI'), 1, 'distribution_pdf', '05-Maybelle_The_Woman_Who_Kept_The_Table_First_Illustrated_Edition-1-.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Maybelle-The-Woman-Who-Kept-the-Table_First-Illustrated_2026-08-20_v1.pdf', 'e5f9df4cf97c0bdfacef3271d23001a47099f61e86b236b3d2c80a485583953e', 'application/pdf', 41600510, 152, '1mh31JK0QZ0zjllRoO2aV8_AKDXDaFmgO', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-WILLIE-FI'), 1, 'distribution_pdf', '06-Willie_The_Legend_First_Illustrated_Edition-4-.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Willie-the-Legend_First-Illustrated_2026-08-20_v1.pdf', 'cc7ba86a4ef24396c1ff2a77f177d4179ce00348b01cc48e5f219eceacbcf88e', 'application/pdf', 41665444, 190, '12iH9vdlUdZE5xL8n7nuzGQqME8LqJd4-', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-TO-HELL-TASHA'), 1, 'distribution_pdf', '07-To_Hell_We_Go_Tasha_Triple_Life_Evidence_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_To-Hell-We-Go_Tasha-Triple-Life-Evidence_2026-08-20_v1.pdf', '0b139d8dad3a9a5a8996fb2a44120f0498ffbe58a9791ee5308672b4d3d98c97', 'application/pdf', 4064579, 135, '1QHAnzpA84Abr_hW_b6_ShtHRbX_PjlbH', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-WRH-V2-A-231'), 1, 'distribution_pdf', '08-What_Really_Happened_Version_2_Illustrated_Collector_Edition-1-.pdf', 'CrownThrive_Virality-Music_Book-Distribution_What-Really-Happened_V2-Illustrated-Collector_Variant-A-231p_2026-08-20_v1.pdf', '6c46803b20acd815fe53add98d0f68752ffa1cbe538c00b19bf88947d9bb55f2', 'application/pdf', 18755016, 231, '1aZb6bDF10JcDa8TFmG4LCtJO8iuql-E6', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{"variant_group":"VM-BOOK-WRH-V2"}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-WRH-V2-B-227'), 1, 'distribution_pdf', '09-What_Really_Happened_Version_2_Illustrated_Collector_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_What-Really-Happened_V2-Illustrated-Collector_Variant-B-227p_2026-08-20_v1.pdf', '75aa54d5bb1987e83d7b1066f8969a60cf1a3a05eb146d334e45b790eac5858a', 'application/pdf', 2285948, 227, '1CkRYgC5Rub_fYh3Ng28j90ReK9VjEWQ2', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{"variant_group":"VM-BOOK-WRH-V2"}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-ALMA-V2-IL'), 1, 'distribution_pdf', '10-Alma_Knight_Carter_The_Woman_Who_Taught_Money_To_Stay_Version_2_Illustrated_Legacy_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Alma-Knight-Carter-The-Woman-Who-Taught-Money-to-Stay_V2-Illustrated-Legacy_2026-08-20_v1.pdf', 'a02434727b52bf0e97475fda50de2c7220795d4166f7f025117a9d52ed41ad5c', 'application/pdf', 37816264, 158, '1QEHPlTpev92yqq-Df3ws4S1ETbq9WuOF', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-THIRD-LIFE-V2-IC'), 1, 'distribution_pdf', '11-The_Third_Life_Had_The_Wrong_Name_Version_2_Illustrated_Collector_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_The-Third-Life-Had-the-Wrong-Name_V2-Illustrated-Collector_2026-08-20_v1.pdf', '1c70c64c24ffa347a8ace048eb9b999448484362ce76b68a02ed76f2ffeb63ed', 'application/pdf', 4674076, 280, '1S6s24YprlhKKZg1YvihJ2MKeFnR4OGoe', now(), 'supabase_pending', 'hold', 'tagging_required', 'verified', '{}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-LEONARD-CLARENCE-IF'), 1, 'distribution_pdf', '12-Leonard_Clarence_Two_Damn_Fools_Illustrated_Flagship_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Leonard-and-Clarence-Two-Damn-Fools_Illustrated-Flagship_2026-08-20_v1.pdf', '1d3ff22abe053ba192eae71e6e0038bdf70e12f3d7070bb99efdc75584a8caee', 'application/pdf', 3694948, 216, '1WR5lVR8Bv5zpNsp_KCBpYv2e06cAsjBa', now(), 'supabase_pending', 'verified', 'tagged_unverified_pdfua', 'verified', '{"source_pair_text_sha256":"a7cab9d42034c655eabb865de5a258f665853694a6321b546f42e404fd6e6151"}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-LEONARD-CLARENCE-IF'), 1, 'editable_source', '13-Leonard_Clarence_Two_Damn_Fools_Illustrated_Flagship_Edition.docx', 'CrownThrive_Virality-Music_Book-Source_Leonard-and-Clarence-Two-Damn-Fools_Illustrated-Flagship_2026-08-20_v1.docx', 'e1aa366bfe6890c2053ad3fa9b6fc2656f579233b9a18ab942ff97706b8304cb', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 6062893, 216, '14uBfFxBSPVA-kyeo_XxUWuF7K-NGMAeh', now(), 'supabase_pending', 'verified', 'not_applicable', 'verified', '{"paired_distribution_sha256":"1d3ff22abe053ba192eae71e6e0038bdf70e12f3d7070bb99efdc75584a8caee","source_pair_text_sha256":"a7cab9d42034c655eabb865de5a258f665853694a6321b546f42e404fd6e6151"}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-LEONARD-COFFIELD-IW'), 1, 'distribution_pdf', '14-Leonard_Coffield_The_Fool_Who_Saw_Everything_First_Illustrated_Witness_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Leonard-Coffield-The-Fool-Who-Saw-Everything_First-Illustrated-Witness_2026-08-20_v1.pdf', '71fd7369ac6a246f2c02d675c63ddaa600d889c439edb22b4526ce1c578cc61a', 'application/pdf', 5382694, 283, '1xrUtXmaeBVrDUWiDUCdBCI8FJA-et4LC', now(), 'supabase_pending', 'verified', 'tagged_unverified_pdfua', 'verified', '{"source_pair_text_sha256":"b53342b4a423fa804608eff3954af576728b72e0ae3c0269ce8651d5d3f26d8e"}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-LEONARD-COFFIELD-IW'), 1, 'editable_source', '15-Leonard_Coffield_The_Fool_Who_Saw_Everything_First_Illustrated_Witness_Edition.docx', 'CrownThrive_Virality-Music_Book-Source_Leonard-Coffield-The-Fool-Who-Saw-Everything_First-Illustrated-Witness_2026-08-20_v1.docx', '3a910227294fee7c79d2a716f675c55d806da0faac401e567bd242eeeccb9054', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 3685192, 283, '16qJdxFCvPtgxi0sOd7s6RNPQa19JLxZ7', now(), 'supabase_pending', 'verified', 'not_applicable', 'verified', '{"paired_distribution_sha256":"71fd7369ac6a246f2c02d675c63ddaa600d889c439edb22b4526ce1c578cc61a","source_pair_text_sha256":"b53342b4a423fa804608eff3954af576728b72e0ae3c0269ce8651d5d3f26d8e"}'::jsonb),
  ((select asset_id from virality_control.asset_registry where canonical_key='VM-BOOK-ROSETTA-IL'), 1, 'distribution_pdf', '16-Rosetta_The_Woman_Who_Made_The_Legend_Wash_Dishes_Illustrated_Legacy_Edition.pdf', 'CrownThrive_Virality-Music_Book-Distribution_Rosetta-The-Woman-Who-Made-the-Legend-Wash-Dishes_Illustrated-Legacy_2026-08-20_v1.pdf', 'b61cbab00b7c47f82f7df4279afd79cd9bfa22e6b5149e976a2e43922600e2ad', 'application/pdf', 8517800, 111, '13wi1HYYzLTxW-Hn-s3DqQndcK3nf4075', now(), 'supabase_pending', 'hold', 'tagged_unverified_pdfua', 'upgrade_recommended', '{}'::jsonb)
on conflict (sha256) do update set
  drive_file_id = excluded.drive_file_id,
  drive_verified_at = excluded.drive_verified_at,
  binary_state = excluded.binary_state,
  qa_state = excluded.qa_state,
  accessibility_state = excluded.accessibility_state,
  visual_state = excluded.visual_state,
  metadata = virality_control.asset_versions.metadata || excluded.metadata;

insert into virality_control.asset_references (
  version_id, source_system, reference_type, reference_value,
  verification_state, verified_at, metadata
)
select
  v.version_id,
  'google_drive',
  'file_id',
  v.drive_file_id,
  'verified',
  v.drive_verified_at,
  jsonb_build_object('custody_class', 'private_human_accessible_archive')
from virality_control.asset_versions v
where v.drive_file_id is not null
on conflict (source_system, reference_type, reference_value) do update set
  version_id = excluded.version_id,
  verification_state = excluded.verification_state,
  verified_at = excluded.verified_at,
  metadata = virality_control.asset_references.metadata || excluded.metadata;

insert into virality_control.soundcloud_entities (
  entity_type, provider_entity_id, title, permalink_url, active, metadata
)
values (
  'account',
  'crownthrive',
  'Virality Music by CrownThrive',
  'https://soundcloud.com/crownthrive',
  true,
  jsonb_build_object('institutional_owner', 'CrownThrive, LLC')
)
on conflict (entity_type, provider_entity_id) do update set
  title = excluded.title,
  permalink_url = excluded.permalink_url,
  active = true,
  last_seen_at = now(),
  metadata = virality_control.soundcloud_entities.metadata || excluded.metadata;

insert into virality_control.sync_runs (
  provider, scheduled_for, attempt, status, evidence_state,
  request_count, response_count, raw_digest, started_at, finished_at, metadata
)
values (
  'soundcloud',
  '2026-08-13'::date,
  1,
  'succeeded',
  'verified',
  0,
  1,
  encode(extensions.digest('2026-08-13|crownthrive|1114510|4335|11216|637|274|3|20484', 'sha256'), 'hex'),
  '2026-08-13T00:00:00Z'::timestamptz,
  '2026-08-13T00:00:01Z'::timestamptz,
  jsonb_build_object(
    'source_kind', 'founder_provided_soundcloud_artist_studio_snapshot',
    'public_projection', 'https://vm.crownthrive.com',
    'api_request_performed', false
  )
)
on conflict (provider, scheduled_for, attempt) do update set
  status = excluded.status,
  evidence_state = excluded.evidence_state,
  response_count = excluded.response_count,
  raw_digest = excluded.raw_digest,
  finished_at = excluded.finished_at,
  metadata = virality_control.sync_runs.metadata || excluded.metadata;

insert into virality_control.soundcloud_metric_snapshots (
  sync_run_id, snapshot_date, entity_type, provider_entity_id, evidence_state,
  plays, likes, reposts, comments, downloads, followers, track_count, metrics, collected_at
)
select
  r.run_id,
  '2026-08-13'::date,
  'account',
  'crownthrive',
  'verified',
  1114510,
  11216,
  274,
  637,
  3,
  null,
  4335,
  jsonb_build_object('minutes', 20484),
  '2026-08-13T00:00:01Z'::timestamptz
from virality_control.sync_runs r
where r.provider = 'soundcloud'
  and r.scheduled_for = '2026-08-13'::date
  and r.attempt = 1
on conflict (snapshot_date, entity_type, provider_entity_id) do update set
  sync_run_id = excluded.sync_run_id,
  evidence_state = excluded.evidence_state,
  plays = excluded.plays,
  likes = excluded.likes,
  reposts = excluded.reposts,
  comments = excluded.comments,
  downloads = excluded.downloads,
  track_count = excluded.track_count,
  metrics = excluded.metrics,
  collected_at = excluded.collected_at;

create or replace function public.virality_assets_list()
returns table (
  canonical_key text,
  title text,
  edition_label text,
  rights_state text,
  release_state text,
  monetization_state text,
  canonicality_state text
)
language sql
stable
security invoker
set search_path = pg_catalog, virality_control
as $$
  select
    a.canonical_key,
    a.title,
    a.edition_label,
    a.rights_state,
    a.release_state,
    a.monetization_state,
    a.canonicality_state
  from virality_control.asset_registry a
  order by a.canonical_key;
$$;

revoke all on function public.virality_assets_list() from public, anon, authenticated;
grant execute on function public.virality_assets_list() to service_role;

create or replace function public.virality_stats_current()
returns table (
  snapshot_date date,
  evidence_state text,
  plays bigint,
  likes bigint,
  reposts bigint,
  comments bigint,
  downloads bigint,
  followers bigint,
  track_count bigint,
  metrics jsonb
)
language sql
stable
security invoker
set search_path = pg_catalog, virality_control
as $$
  select
    s.snapshot_date,
    s.evidence_state,
    s.plays,
    s.likes,
    s.reposts,
    s.comments,
    s.downloads,
    s.followers,
    s.track_count,
    s.metrics
  from virality_control.soundcloud_metric_snapshots s
  where s.entity_type = 'account'
    and s.provider_entity_id = 'crownthrive'
    and s.evidence_state = 'verified'
  order by s.snapshot_date desc
  limit 1;
$$;

revoke all on function public.virality_stats_current() from public, anon, authenticated;
grant execute on function public.virality_stats_current() to service_role;

comment on schema virality_control is
  'Private Virality Music operational registry, provider evidence, and recommendation-control plane. Not a public content or fulfillment store.';

comment on table virality_control.promotion_recommendations is
  'Shadow-mode recommendation queue. Rows do not authorize public placement, licensing, pricing, checkout activation, or provider writes.';

commit;
