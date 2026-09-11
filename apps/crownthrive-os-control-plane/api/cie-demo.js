const VERSION = '1.1.0';
const LENSES = [
  'identity_depth',
  'cultural_contribution',
  'ecosystem_gravity',
  'economic_utility',
  'scalability_longevity',
  'imprint_power',
];

const PRESETS = {
  salon: {
    name: 'Rooted Crown Studio',
    sector: 'beauty_service',
    operating_scope: 'single_brand',
    identity: 'A culturally grounded natural-hair studio centered on trust, education, and healthy long-term hair care.',
    audience: 'Black women, men, parents, and loc clients who want culturally competent natural-hair care.',
    voice: 'Expert, warm, specific, culturally fluent, never gimmicky.',
    goals: ['grow bookings', 'launch education products', 'build repeat customer trust'],
    channels: ['website', 'social', 'email'],
    guardrails: ['no trend-chasing slang', 'never flatten Black hair culture into aesthetics', 'education before hard sell'],
  },
  media: {
    name: 'Melanated Voices Network Demo',
    sector: 'media_network',
    operating_scope: 'multi_brand',
    identity: 'A Black-centered media network preserving lived voice, cultural authorship, and accountable storytelling across formats.',
    audience: 'Viewers, listeners, creators, sponsors, and community partners seeking culturally grounded media.',
    voice: 'Editorially sharp, human, culturally literate, accountable, direct.',
    goals: ['expand programming', 'sell sponsorship', 'license content', 'preserve editorial coherence'],
    channels: ['streaming', 'podcast', 'social', 'newsletter', 'events'],
    guardrails: ['sponsor does not rewrite editorial voice', 'preserve attribution', 'separate commentary from verified claims'],
  },
  platform: {
    name: 'Creator Commerce Platform',
    sector: 'software_platform',
    operating_scope: 'multi_site',
    identity: 'A commerce platform that helps culturally rooted creators sell digital products without losing authorship or brand context.',
    audience: 'Independent creators, small publishers, agencies, and cultural entrepreneurs.',
    voice: 'Clear, enabling, practical, creator-first.',
    goals: ['onboard creators', 'increase product publication', 'support licensing', 'integrate analytics'],
    channels: ['product_ui', 'docs', 'email', 'partner_marketplace'],
    guardrails: ['do not commoditize creator identity', 'preserve creator attribution', 'keep rights language explicit'],
  },
  institution: {
    name: 'Regional Cultural Institute',
    sector: 'institution',
    operating_scope: 'institutional',
    identity: 'A regional cultural institution preserving local history while teaching, publishing, convening, and building economic opportunity.',
    audience: 'Families, educators, artists, donors, researchers, civic partners, and youth.',
    voice: 'Authoritative, accessible, archival, community-accountable.',
    goals: ['modernize communications', 'launch digital archive', 'grow education programs', 'create licensed exhibits'],
    channels: ['website', 'archive', 'education', 'events', 'social', 'press'],
    guardrails: ['community provenance must be visible', 'archive and marketing claims stay distinct', 'commercial use requires rights context'],
  },
  agency: {
    name: 'Culture-Led Brand Agency',
    sector: 'agency',
    operating_scope: 'agency',
    identity: 'An agency implementing culturally coherent brand systems for multiple clients without copy-pasting one voice across accounts.',
    audience: 'Founders, cultural organizations, consumer brands, and media clients.',
    voice: 'Strategic, precise, culturally competent, evidence-aware.',
    goals: ['standardize discovery', 'reduce brand drift', 'scale client delivery', 'package repeatable implementation'],
    channels: ['client_strategy', 'campaigns', 'social', 'web', 'ads', 'reporting'],
    guardrails: ['client identity remains client-owned', 'no generic cultural templates', 'document assumptions and rights'],
  },
};

function list(value, max = 12) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map((item) => String(item || '').trim()).filter(Boolean))].slice(0, max);
}

function bounded(value, max = 800) {
  return String(value || '').trim().slice(0, max);
}

function parseBody(request) {
  if (request.body && typeof request.body === 'object') return request.body;
  if (typeof request.body === 'string' && request.body.trim()) {
    try { return JSON.parse(request.body); } catch { return null; }
  }
  return null;
}

function classify(input) {
  const sector = input.sector.toLowerCase();
  if (sector.includes('institution') || input.operating_scope === 'institutional') return 'institutional';
  if (sector.includes('media')) return 'media_channel';
  if (sector.includes('software') || sector.includes('platform') || sector.includes('saas')) return 'platform';
  if (input.operating_scope === 'multi_brand' || sector.includes('ecosystem') || sector.includes('directory')) return 'corridor';
  return 'brand_campaign';
}

function recommendTier(input) {
  if (input.operating_scope === 'enterprise' || input.operating_scope === 'oem') return {sku:'CIE-ENTERPRISE-001',name:'Enterprise',price_usd:7500,reason:'Multi-environment or embedded/OEM operating scope.'};
  if (input.operating_scope === 'institutional') return {sku:'CIE-INSTITUTION-001',name:'Institutional',price_usd:4999,reason:'Program, institution, or multi-team implementation scope.'};
  if (input.operating_scope === 'agency') return {sku:'CIE-AGENCY-001',name:'Agency',price_usd:2499,reason:'Client implementation and repeatable agency delivery scope.'};
  if (input.operating_scope === 'multi_brand' || input.operating_scope === 'multi_site' || input.channels.length >= 4) return {sku:'CIE-STUDIO-001',name:'Studio',price_usd:799,reason:'Multi-brand/site or multi-channel implementation benefits from API/MCP and PentaAds bridge.'};
  return {sku:'CIE-OPERATOR-001',name:'Operator',price_usd:299,reason:'Single-brand implementation with a bounded channel footprint.'};
}

function score(input, family) {
  const complete = [input.identity, input.audience, input.voice].filter((x) => x.length >= 24).length;
  const guardrailDepth = Math.min(input.guardrails.length, 5);
  const goalDepth = Math.min(input.goals.length, 5);
  const channelDepth = Math.min(input.channels.length, 6);
  const familyBonus = family === 'institutional' || family === 'corridor' ? 1 : 0;
  const values = {
    identity_depth: Math.min(10, 4 + complete + Math.min(guardrailDepth, 2)),
    cultural_contribution: Math.min(10, 4 + Math.min(goalDepth, 2) + Math.min(guardrailDepth, 3)),
    ecosystem_gravity: Math.min(10, 3 + Math.ceil(channelDepth / 2) + Math.min(goalDepth, 2) + familyBonus),
    economic_utility: Math.min(10, 4 + Math.min(goalDepth, 3) + (input.channels.some((x) => /commerce|ads|market|product|email/.test(x)) ? 1 : 0)),
    scalability_longevity: Math.min(10, 4 + Math.min(channelDepth, 3) + Math.min(guardrailDepth, 2)),
    imprint_power: 0,
  };
  values.imprint_power = Math.round((values.identity_depth + values.cultural_contribution + values.ecosystem_gravity + values.economic_utility + values.scalability_longevity) / 5);
  const total = Math.round(LENSES.reduce((sum, lens) => sum + values[lens], 0) / LENSES.length * 10);
  return {score_100: total, lenses: values};
}

function risks(input) {
  const findings = [];
  if (input.channels.length >= 4) findings.push({level:'high',finding:'Channel drift risk',why:'Four or more customer-facing channels create repeated opportunities for tone, promise, and representation to diverge.'});
  if (input.goals.length >= 3) findings.push({level:'medium',finding:'Competing objective risk',why:'Multiple simultaneous growth goals can cause each channel to optimize for a different version of the brand.'});
  if (input.guardrails.length < 2) findings.push({level:'high',finding:'Weak boundary definition',why:'The scenario has too few explicit guardrails to tell operators, agencies, or AI systems what must not drift.'});
  if (/media|institution|agency/.test(input.sector) && !input.guardrails.some((x) => /rights|provenance|attribution|editorial|claim/.test(x.toLowerCase()))) findings.push({level:'medium',finding:'Rights/editorial context gap',why:'This sector commonly requires explicit provenance, attribution, editorial, or rights constraints.'});
  if (!findings.length) findings.push({level:'low',finding:'No major structural gap detected',why:'The supplied identity, audience, voice, goals, channels, and guardrails form a usable public-safe imprint package.'});
  return findings;
}

function route(input, family) {
  const base = ['CIE imprint package'];
  if (input.guardrails.some((x) => /rights|license|provenance|attribution/.test(x.toLowerCase()))) base.push('CHLOM-compatible rights context');
  base.push(`${family} imprint routing`);
  for (const channel of input.channels.slice(0, 5)) base.push(`project to ${channel}`);
  if (input.channels.some((x) => /ads|social|market|email/.test(x))) base.push('PentaAds placement plan');
  base.push('CrownLytics evidence');
  base.push('Thrive Flywheel feedback');
  return base;
}

function normalize(body) {
  const preset = PRESETS[body?.preset] || {};
  const source = {...preset, ...(body || {})};
  return {
    name: bounded(source.name || 'Untitled Imprint', 120),
    sector: bounded(source.sector || 'general_business', 80),
    operating_scope: bounded(source.operating_scope || 'single_brand', 40),
    identity: bounded(source.identity, 900),
    audience: bounded(source.audience, 700),
    voice: bounded(source.voice, 500),
    goals: list(source.goals, 10),
    channels: list(source.channels, 10),
    guardrails: list(source.guardrails, 12),
  };
}

function validate(input) {
  const missing = [];
  for (const key of ['identity','audience','voice']) if (input[key].length < 12) missing.push(key);
  if (!input.goals.length) missing.push('goals');
  if (!input.channels.length) missing.push('channels');
  return missing;
}

function execute(input) {
  const started = Date.now();
  const family = classify(input);
  const scoring = score(input, family);
  const tier = recommendTier(input);
  const riskFindings = risks(input);
  const routing = route(input, family);
  const runId = `cie_demo_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,8)}`;
  const stages = [
    {stage:1,name:'Capture identity context',status:'PASS',show_your_work:`Parsed identity, audience, voice, ${input.goals.length} goals, ${input.channels.length} channels, and ${input.guardrails.length} guardrails.`},
    {stage:2,name:'Classify imprint',status:'PASS',show_your_work:`Sector “${input.sector}” + scope “${input.operating_scope}” resolved to the ${family} imprint family.`},
    {stage:3,name:'Detect drift exposure',status:'PASS',show_your_work:`Evaluated channel count, objective count, guardrail depth, and sector-specific rights/editorial signals; produced ${riskFindings.length} finding(s).`},
    {stage:4,name:'Score public lenses',status:'PASS',show_your_work:`Computed transparent public-demo lens values from completeness, channel complexity, goals, and guardrails. No protected CrownThrive calibration used.`},
    {stage:5,name:'Route the imprint',status:'PASS',show_your_work:`Built a ${routing.length}-step route from imprint package through channels, evidence, and flywheel feedback.`},
    {stage:6,name:'Commercial fit',status:'PASS',show_your_work:`Mapped operating scope and channel complexity to ${tier.name} (${tier.sku}).`},
  ];
  return {
    schema:'ct.cie.demo-run.v1',
    service:'crownthrive-cie-public-demo',
    version:VERSION,
    run_id:runId,
    executed_at:new Date().toISOString(),
    server_duration_ms:Date.now()-started,
    mode:'PUBLIC_DETERMINISTIC_DEMO',
    input,
    result:{
      imprint_family:family,
      canonical_imprint:{
        name:input.name,
        identity:input.identity,
        audience:input.audience,
        voice:input.voice,
        goals:input.goals,
        channels:input.channels,
        guardrails:input.guardrails,
      },
      scoring,
      risks:riskFindings,
      routing,
      recommended_license:tier,
      pentaads_projection:{
        binding:'ct.binding.pentaads.cie.v1',
        eligible:input.channels.some((x)=>/ads|social|market|email/.test(x)),
        identity_context_preserved:true,
        rights_state:input.guardrails.some((x)=>/rights|license|provenance|attribution/.test(x.toLowerCase()))?'CONTEXT_SUPPLIED':'CONTEXT_RECOMMENDED',
        provider_write_authority:false,
        ad_spend_authority:false,
        measurement:['impression','click','conversion','qualified_action'],
      },
      before_after:{
        without_cie:'Identity decisions remain distributed across people, prompts, campaigns, documents, and channels; each new surface can invent its own version of the brand.',
        with_cie:`A ${family} imprint package now carries explicit identity, audience, voice, goals, channel routes, and guardrails into downstream execution.`,
      },
    },
    stages,
    evidence:{
      protected_calibration_used:false,
      credentials_used:false,
      external_provider_write:false,
      payment_executed:false,
      persisted:false,
      note:'This endpoint is a public proof runner. It executes real deterministic CIE demo logic on Vercel but does not claim licensed production decisions, legal clearance, or provider-side mutation.'
    }
  };
}

export default function handler(request, response) {
  response.setHeader('Cache-Control','no-store, max-age=0');
  response.setHeader('Content-Type','application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options','nosniff');
  response.setHeader('Access-Control-Allow-Origin','*');
  response.setHeader('Access-Control-Allow-Methods','GET, POST, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers','Content-Type');
  response.setHeader('X-CrownThrive-CIE-Demo',VERSION);
  if (request.method === 'OPTIONS') return response.status(204).end();
  if (request.method === 'GET') {
    return response.status(200).json({
      schema:'ct.cie.demo-service.v1',service:'crownthrive-cie-public-demo',version:VERSION,status:'OPERATIONAL',
      endpoint:'/api/cie-demo',methods:['GET','POST'],preset_ids:Object.keys(PRESETS),lenses:LENSES,
      authority:{public_demo:true,protected_calibration:false,provider_write:false,ad_spend:false,payment:false,persistence:false},
      observed_at:new Date().toISOString()
    });
  }
  if (request.method !== 'POST') {
    response.setHeader('Allow','GET, POST, OPTIONS');
    return response.status(405).json({error:'method_not_allowed'});
  }
  const body = parseBody(request);
  if (!body) return response.status(400).json({error:'invalid_json'});
  const input = normalize(body);
  const missing = validate(input);
  if (missing.length) return response.status(400).json({error:'incomplete_scenario',missing,required:['identity','audience','voice','goals[]','channels[]']});
  return response.status(200).json(execute(input));
}
