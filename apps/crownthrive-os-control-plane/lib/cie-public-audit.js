function text(value, max = 12000) { return String(value ?? '').trim().slice(0, max); }
function list(value, max = 30) { return Array.isArray(value) ? [...new Set(value.map((v) => text(v, 500)).filter(Boolean))].slice(0, max) : []; }
function low(value) { return text(value).toLowerCase(); }
function hasAny(source, needles) { const s = low(source); return needles.some((n) => s.includes(n)); }

export function normalizeAuditInput(body = {}) {
  const imprint = body.imprint || {};
  const asset = body.asset || {};
  return {
    imprint: {
      name: text(imprint.name || 'Untitled imprint', 160),
      identity: text(imprint.identity, 1000),
      audience: text(imprint.audience, 800),
      voice: text(imprint.voice, 600),
      goals: list(imprint.goals, 12),
      guardrails: list(imprint.guardrails, 20),
      required_signals: list(imprint.required_signals, 12),
      forbidden_phrases: list(imprint.forbidden_phrases, 20)
    },
    asset: {
      id: text(asset.id || `asset-${Date.now()}`, 120),
      type: text(asset.type || 'content', 80),
      channel: text(asset.channel || 'unknown', 80),
      title: text(asset.title || 'Untitled asset', 240),
      content: text(asset.content, 12000),
      metadata: {
        ai_generated: Boolean(asset.metadata?.ai_generated),
        has_sources: Boolean(asset.metadata?.has_sources),
        has_attribution: Boolean(asset.metadata?.has_attribution),
        has_rights_context: Boolean(asset.metadata?.has_rights_context),
        sponsor_directed_voice: Boolean(asset.metadata?.sponsor_directed_voice),
        sponsor_disclosed: Boolean(asset.metadata?.sponsor_disclosed),
        irreversible_release: Boolean(asset.metadata?.irreversible_release)
      }
    }
  };
}

function result(status, rule_id, finding, evidence, fix, auto_action) {
  return { status, rule_id, finding, evidence, fix, auto_action };
}

export function auditAsset(body = {}) {
  const { imprint, asset } = normalizeAuditInput(body);
  const checks = [];
  const content = asset.content;
  const guardrailText = imprint.guardrails.join(' ').toLowerCase();
  const goalText = imprint.goals.join(' ').toLowerCase();

  if (content.length < 40) {
    checks.push(result('HOLD','asset_too_thin','Asset does not contain enough material for a meaningful release review',`${content.length} characters supplied`,'Provide the full customer-facing asset before release.','stop_release'));
  } else {
    checks.push(result('PASS','asset_present','A reviewable asset was supplied',`${content.length} characters supplied`,'No change required.','continue_analysis'));
  }

  const forbidden = imprint.forbidden_phrases.filter((phrase) => phrase && low(content).includes(low(phrase)));
  if (forbidden.length) {
    checks.push(result('HOLD','explicit_forbidden_phrase','Asset contains language explicitly prohibited by the active imprint',forbidden.join(', '),'Remove or rewrite the prohibited language, then re-run the asset.','stop_release'));
  }

  const absoluteClaim = /(guaranteed|guarantees|always works|never fails|scientifically proven|100% proven|zero risk|instant results)/i.test(content);
  if (absoluteClaim && !asset.metadata.has_sources) {
    checks.push(result('HOLD','unsupported_absolute_claim','Asset makes an absolute or scientific-sounding claim without source evidence','Absolute claim detected and has_sources=false','Add verifiable evidence, narrow the claim, or remove it.','stop_release'));
  }

  const numericClaim = /\b\d{1,3}(?:\.\d+)?%\b|\b\d+(?:\.\d+)?x\b/i.test(content);
  if (numericClaim && asset.metadata.ai_generated && !asset.metadata.has_sources) {
    checks.push(result('HOLD','ai_numeric_claim_without_source','AI-assisted asset contains a numeric performance claim without source evidence','ai_generated=true, numeric claim detected, has_sources=false','Attach a source and human verification or remove the number.','stop_release'));
  }

  const attributionRequired = /attribution|credit|creator|provenance/.test(guardrailText);
  if (attributionRequired && !asset.metadata.has_attribution) {
    checks.push(result('HOLD','attribution_missing','Active guardrails require attribution or provenance but the asset has none','Guardrail requires attribution; has_attribution=false','Attach the required creator/source attribution.','stop_release'));
  }

  const rightsRequired = /rights|license|licensing|syndicat|affiliate|resell|wholesale|white-label|oem/.test(`${guardrailText} ${goalText}`);
  if (rightsRequired && !asset.metadata.has_rights_context) {
    checks.push(result('HOLD','rights_context_missing','This route has licensing, distribution or rights pressure without attached rights context','Goal/guardrail implies rights context; has_rights_context=false','Attach the applicable rights/provenance reference before distribution.','stop_release'));
  }

  const editorialBoundary = /editorial|sponsor|independent voice/.test(guardrailText);
  if ((editorialBoundary || /article|editorial|podcast|newsletter/.test(low(asset.type))) && asset.metadata.sponsor_directed_voice) {
    checks.push(result('HOLD','sponsor_voice_override','Sponsor control is attempting to cross into editorial or institutional authority','sponsor_directed_voice=true','Separate sponsor copy from editorial judgment and preserve disclosure.','stop_release'));
  }
  if (asset.metadata.sponsor_directed_voice && !asset.metadata.sponsor_disclosed) {
    checks.push(result('HOLD','sponsor_disclosure_missing','Sponsor-influenced material is not visibly disclosed','sponsor_directed_voice=true; sponsor_disclosed=false','Add a clear sponsorship disclosure before release.','stop_release'));
  }

  if (/no trend|trend-chasing|never gimmicky/.test(guardrailText) && hasAny(content,['viral hack','trend hack','secret trick','you need this now','everyone is doing'])) {
    checks.push(result('WARN','trend_pressure_language','Asset uses trend-pressure language that conflicts with an anti-gimmick guardrail','Trend-pressure phrase detected','Rewrite around durable value, evidence and audience need.','draft_only_review_required'));
  }

  const exclamationCount = (content.match(/!/g) || []).length;
  const capsWords = (content.match(/\b[A-Z]{4,}\b/g) || []).length;
  if (exclamationCount >= 5 || capsWords >= 5) {
    checks.push(result('WARN','promotional_tone_spike','Asset has a promotional intensity spike that may exceed the stated voice',`${exclamationCount} exclamation marks; ${capsWords} all-caps words`,'Reduce urgency and compare against the voice envelope.','draft_only_review_required'));
  }

  if (asset.channel === 'social' && content.length > 1800) {
    checks.push(result('WARN','channel_format_mismatch','Social asset is unusually long for the declared channel',`${content.length} characters`,'Create a channel-specific projection instead of copying the long-form source wholesale.','draft_only_review_required'));
  }

  const missingSignals = imprint.required_signals.filter((signal) => !low(content).includes(low(signal)));
  if (missingSignals.length) {
    checks.push(result('WARN','required_signal_missing','Asset is missing signals the active imprint expects on this route',missingSignals.join(', '),'Add the missing signal only if it fits the asset job; otherwise document an explicit exception.','draft_only_review_required'));
  }

  if (asset.metadata.irreversible_release && checks.some((c) => c.status !== 'PASS')) {
    checks.push(result('HOLD','irreversible_release_with_open_findings','The asset is marked for irreversible release while review findings remain open','irreversible_release=true with WARN/HOLD findings','Resolve findings before irreversible publication or provider mutation.','stop_release'));
  }

  if (!checks.some((c) => c.status === 'HOLD') && !checks.some((c) => c.status === 'WARN')) {
    checks.push(result('PASS','imprint_conformance','No public-rule conformance failure was detected','Identity/guardrail checks completed','Preserve the imprint context and continue to the next authorized stage.','allow_next_stage'));
  }

  const status = checks.some((c) => c.status === 'HOLD') ? 'HOLD' : checks.some((c) => c.status === 'WARN') ? 'WARN' : 'PASS';
  const automatic = status === 'HOLD'
    ? ['stop_release','retain_failure_evidence','route_to_identity_or_rights_review','generate_remediation_checklist']
    : status === 'WARN'
      ? ['allow_draft_only','mark_review_required','retain_warning_evidence','generate_remediation_checklist']
      : ['allow_next_stage','attach_imprint_context','emit_conformance_evidence'];

  return {
    schema: 'ct.cie.public-asset-audit.v1',
    status,
    audited_at: new Date().toISOString(),
    imprint: { name: imprint.name, goals: imprint.goals, guardrails: imprint.guardrails },
    asset: { id: asset.id, type: asset.type, channel: asset.channel, title: asset.title },
    checks,
    automatic_actions: automatic,
    authority: { public_demo: true, provider_write: false, payment: false, ad_spend: false, protected_calibration: false, persistence: false },
    note: 'This is transparent public conformance logic. It demonstrates CIE operating behavior but does not replace licensed implementation review, legal clearance or provider-side execution.'
  };
}

export function auditPackage(body = {}) {
  const assets = Array.isArray(body.assets) ? body.assets.slice(0, 30) : [];
  const imprint = body.imprint || {};
  const results = assets.map((asset) => auditAsset({ imprint, asset }));
  const hold = results.filter((r) => r.status === 'HOLD').length;
  const warn = results.filter((r) => r.status === 'WARN').length;
  const pass = results.filter((r) => r.status === 'PASS').length;
  const status = hold ? 'HOLD' : warn ? 'WARN' : 'PASS';
  const channels = [...new Set(results.map((r) => r.asset.channel).filter(Boolean))];
  const voices = assets.map((asset) => low(asset.content)).filter(Boolean);
  const hasPromo = voices.some((v) => /buy now|limited time|must have|act now/.test(v));
  const hasEditorial = assets.some((a) => /article|editorial|podcast|newsletter/.test(low(a.type)));
  const packageFindings = [];
  if (hasPromo && hasEditorial) packageFindings.push({status:'WARN',rule_id:'package_voice_collision',finding:'Package mixes hard-promo and editorial assets; verify that this is intentional channel variation rather than identity drift.'});
  if (channels.length >= 4) packageFindings.push({status:'WARN',rule_id:'package_channel_complexity',finding:`Package spans ${channels.length} channels and should carry one shared imprint reference into each handoff.`});
  const finalStatus = status === 'HOLD' || packageFindings.some((f) => f.status === 'HOLD') ? 'HOLD' : status === 'WARN' || packageFindings.length ? 'WARN' : 'PASS';
  return {
    schema: 'ct.cie.public-package-audit.v1',
    status: finalStatus,
    package_id: text(body.package_id || `cie-package-${Date.now()}`, 160),
    audited_at: new Date().toISOString(),
    summary: { assets: results.length, pass, warn, hold, channels },
    package_findings: packageFindings,
    assets: results,
    automatic_actions: finalStatus === 'HOLD'
      ? ['hold_entire_package','retain_all_asset_evidence','route_failed_assets_for_remediation','re-run_before_release']
      : finalStatus === 'WARN'
        ? ['keep_package_in_review','allow_nonfinal_preview','retain_warning_evidence','re-run_before_release']
        : ['allow_next_authorized_stage','bind_shared_imprint_context','emit_package_conformance_evidence'],
    authority: { public_demo: true, provider_write: false, payment: false, ad_spend: false, protected_calibration: false, persistence: false }
  };
}
