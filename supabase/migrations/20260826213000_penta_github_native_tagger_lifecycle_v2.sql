begin;

insert into public.penta_system_registry (
  system_key,
  canonical_name,
  category,
  purpose,
  authority_boundary,
  risk_ceiling,
  maturity,
  version,
  public_exposure,
  docs_ref,
  runtime_ref,
  metadata,
  last_verified_at,
  updated_at
)
values
  (
    'penta.tagger',
    'PentaTagger',
    'operations',
    'Applies and verifies machine-readable GitHub and database routing, ownership, risk, lane, lifecycle and terminal-state projections.',
    'Classifies and verifies metadata only. It never merges, closes, deploys, changes rights, moves money or manufactures authority.',
    'D0',
    'implemented',
    '2.0.0',
    true,
    'docs/penta/PENTA_GITHUB_TAGGER_PR_LIFECYCLE.md',
    'scripts/penta_github_tagger.py + public.penta_tags_v1',
    jsonb_build_object(
      'family', 'github_lifecycle',
      'provider', 'github',
      'workflow', '.github/workflows/penta-github-tagger.yml',
      'readback_required', true,
      'terminal_authority', false
    ),
    now(),
    now()
  ),
  (
    'penta.pr',
    'PentaPR',
    'software_delivery',
    'Classifies open pull requests as MERGE, RESTACK, NURTURE or CLOSE and maintains the hard terminal deadline.',
    'May classify lifecycle state and maintain receipts. It may not manufacture a green merge gate or execute terminal closure outside the PentaCloser path.',
    'D1',
    'implemented',
    '2.0.0',
    true,
    'docs/penta/PENTA_GITHUB_TAGGER_PR_LIFECYCLE.md',
    'scripts/penta_pr_lifecycle.py#pentapr',
    jsonb_build_object(
      'family', 'github_lifecycle',
      'provider', 'github',
      'workflow', '.github/workflows/penta-pr-lifecycle.yml',
      'dispositions', jsonb_build_array('MERGE', 'RESTACK', 'NURTURE', 'CLOSE'),
      'deadline_hours', 12
    ),
    now(),
    now()
  ),
  (
    'penta.merge',
    'PentaMerge',
    'software_delivery',
    'Executes exact-head squash merges for PentaPR-classified pull requests after required governed checks are green.',
    'Terminal merge authority only. It must fail closed on draft, non-mergeable, pending, failed or missing governed-merge-gate evidence and must honor penta:hold.',
    'D2',
    'implemented',
    '2.0.0',
    true,
    'docs/penta/PENTA_GITHUB_TAGGER_PR_LIFECYCLE.md',
    'scripts/penta_pr_lifecycle.py#pentamerge',
    jsonb_build_object(
      'family', 'github_lifecycle',
      'provider', 'github',
      'merge_method', 'squash',
      'exact_head_required', true,
      'hold_label', 'penta:hold'
    ),
    now(),
    now()
  ),
  (
    'penta.closer',
    'PentaCloser',
    'software_delivery',
    'Executes terminal pull-request closure after the hard deadline when exact-head governed merge remains ineligible.',
    'Terminal close authority only. It must tag and read back the close candidate before closure, preserve provenance, and honor penta:hold.',
    'D2',
    'implemented',
    '2.0.0',
    true,
    'docs/penta/PENTA_GITHUB_TAGGER_PR_LIFECYCLE.md',
    'scripts/penta_pr_lifecycle.py#pentacloser',
    jsonb_build_object(
      'family', 'github_lifecycle',
      'provider', 'github',
      'deadline_hours', 12,
      'preclose_readback_required', true,
      'hold_label', 'penta:hold'
    ),
    now(),
    now()
  )
on conflict (system_key) do update
set
  canonical_name = excluded.canonical_name,
  category = excluded.category,
  purpose = excluded.purpose,
  authority_boundary = excluded.authority_boundary,
  risk_ceiling = excluded.risk_ceiling,
  maturity = excluded.maturity,
  version = excluded.version,
  public_exposure = excluded.public_exposure,
  docs_ref = excluded.docs_ref,
  runtime_ref = excluded.runtime_ref,
  metadata = public.penta_system_registry.metadata || excluded.metadata,
  last_verified_at = excluded.last_verified_at,
  updated_at = excluded.updated_at;

commit;
