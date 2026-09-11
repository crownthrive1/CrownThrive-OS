const $ = (id) => document.getElementById(id);
const endpoint = '/api/cie-demo';

const presets = {
  salon: {label:'Natural-hair studio',description:'Single-brand service business moving into education and repeatable content.'},
  media: {label:'Media network',description:'Multi-channel editorial system balancing audience, sponsors, licensing and voice.'},
  platform: {label:'Creator platform',description:'Software product that must carry creator identity through commerce and tooling.'},
  institution: {label:'Cultural institution',description:'Program, archive, education, press and commercial use under one institutional voice.'},
  agency: {label:'Brand agency',description:'Repeatable client delivery without copy-pasting one cultural template across accounts.'},
};

let lastRun = null;

function esc(value='') {
  return String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function chips(values=[]) {
  return values.map((v)=>`<span class="run-chip">${esc(v)}</span>`).join('');
}

function setStatus(text, tone='idle') {
  const el = $('runStatus');
  el.textContent = text;
  el.dataset.tone = tone;
}

function setPreset(id) {
  document.querySelectorAll('[data-preset]').forEach((b)=>b.classList.toggle('active', b.dataset.preset===id));
  $('preset').value = id;
  $('scenarioNote').textContent = presets[id]?.description || '';
}

async function loadPreset(id) {
  setPreset(id);
  const response = await fetch(endpoint);
  if (!response.ok) return;
  const custom = {
    salon:{name:'Rooted Crown Studio',sector:'beauty_service',scope:'single_brand',identity:'A culturally grounded natural-hair studio centered on trust, education, and healthy long-term hair care.',audience:'Black women, men, parents, and loc clients who want culturally competent natural-hair care.',voice:'Expert, warm, specific, culturally fluent, never gimmicky.',goals:'grow bookings\nlaunch education products\nbuild repeat customer trust',channels:'website\nsocial\nemail',guardrails:'no trend-chasing slang\nnever flatten Black hair culture into aesthetics\neducation before hard sell'},
    media:{name:'Melanated Voices Network Demo',sector:'media_network',scope:'multi_brand',identity:'A Black-centered media network preserving lived voice, cultural authorship, and accountable storytelling across formats.',audience:'Viewers, listeners, creators, sponsors, and community partners seeking culturally grounded media.',voice:'Editorially sharp, human, culturally literate, accountable, direct.',goals:'expand programming\nsell sponsorship\nlicense content\npreserve editorial coherence',channels:'streaming\npodcast\nsocial\nnewsletter\nevents',guardrails:'sponsor does not rewrite editorial voice\npreserve attribution\nseparate commentary from verified claims'},
    platform:{name:'Creator Commerce Platform',sector:'software_platform',scope:'multi_site',identity:'A commerce platform that helps culturally rooted creators sell digital products without losing authorship or brand context.',audience:'Independent creators, small publishers, agencies, and cultural entrepreneurs.',voice:'Clear, enabling, practical, creator-first.',goals:'onboard creators\nincrease product publication\nsupport licensing\nintegrate analytics',channels:'product_ui\ndocs\nemail\npartner_marketplace',guardrails:'do not commoditize creator identity\npreserve creator attribution\nkeep rights language explicit'},
    institution:{name:'Regional Cultural Institute',sector:'institution',scope:'institutional',identity:'A regional cultural institution preserving local history while teaching, publishing, convening, and building economic opportunity.',audience:'Families, educators, artists, donors, researchers, civic partners, and youth.',voice:'Authoritative, accessible, archival, community-accountable.',goals:'modernize communications\nlaunch digital archive\ngrow education programs\ncreate licensed exhibits',channels:'website\narchive\neducation\nevents\nsocial\npress',guardrails:'community provenance must be visible\narchive and marketing claims stay distinct\ncommercial use requires rights context'},
    agency:{name:'Culture-Led Brand Agency',sector:'agency',scope:'agency',identity:'An agency implementing culturally coherent brand systems for multiple clients without copy-pasting one voice across accounts.',audience:'Founders, cultural organizations, consumer brands, and media clients.',voice:'Strategic, precise, culturally competent, evidence-aware.',goals:'standardize discovery\nreduce brand drift\nscale client delivery\npackage repeatable implementation',channels:'client_strategy\ncampaigns\nsocial\nweb\nads\nreporting',guardrails:'client identity remains client-owned\nno generic cultural templates\ndocument assumptions and rights'}
  }[id];
  if (!custom) return;
  $('name').value=custom.name;$('sector').value=custom.sector;$('scope').value=custom.scope;$('identity').value=custom.identity;$('audience').value=custom.audience;$('voice').value=custom.voice;$('goals').value=custom.goals;$('channels').value=custom.channels;$('guardrails').value=custom.guardrails;
}

function lines(value) {
  return value.split(/\n|,/).map((x)=>x.trim()).filter(Boolean);
}

function payload() {
  return {
    preset:$('preset').value,
    name:$('name').value.trim(),sector:$('sector').value.trim(),operating_scope:$('scope').value,
    identity:$('identity').value.trim(),audience:$('audience').value.trim(),voice:$('voice').value.trim(),
    goals:lines($('goals').value),channels:lines($('channels').value),guardrails:lines($('guardrails').value),
  };
}

function renderStages(stages) {
  $('stageList').innerHTML = stages.map((s)=>`<article class="run-stage"><div class="stage-num">0${s.stage}</div><div><div class="stage-title"><b>${esc(s.name)}</b><span>${esc(s.status)}</span></div><p>${esc(s.show_your_work)}</p></div></article>`).join('');
}

function renderScores(scoring) {
  const labels={identity_depth:'Identity Depth',cultural_contribution:'Cultural Contribution',ecosystem_gravity:'Ecosystem Gravity',economic_utility:'Economic Utility',scalability_longevity:'Scalability + Longevity',imprint_power:'Imprint Power'};
  $('scoreGrid').innerHTML = Object.entries(scoring.lenses).map(([k,v])=>`<div class="score-card"><span>${esc(labels[k]||k)}</span><b>${v}/10</b><div class="meter"><i style="width:${v*10}%"></i></div></div>`).join('');
  $('overallScore').textContent = scoring.score_100;
}

function renderRisks(items) {
  $('riskList').innerHTML = items.map((r)=>`<div class="risk" data-level="${esc(r.level)}"><b>${esc(r.finding)}</b><span>${esc(r.why)}</span></div>`).join('');
}

function renderRun(run) {
  lastRun = run;
  $('emptyRun').hidden = true;
  $('runOutput').hidden = false;
  $('runId').textContent = run.run_id;
  $('runTime').textContent = new Date(run.executed_at).toLocaleString();
  $('serverDuration').textContent = `${run.server_duration_ms} ms`;
  $('family').textContent = run.result.imprint_family.replaceAll('_',' ');
  $('tier').textContent = `${run.result.recommended_license.name} · $${run.result.recommended_license.price_usd.toLocaleString()}`;
  $('tierReason').textContent = run.result.recommended_license.reason;
  $('routeChips').innerHTML = chips(run.result.routing);
  $('before').textContent = run.result.before_after.without_cie;
  $('after').textContent = run.result.before_after.with_cie;
  $('pentaState').textContent = run.result.pentaads_projection.eligible ? 'Placement context generated' : 'No ad-distribution signal in this scenario';
  $('pentaDetail').textContent = `Rights: ${run.result.pentaads_projection.rights_state} · provider write: ${run.result.pentaads_projection.provider_write_authority} · ad spend: ${run.result.pentaads_projection.ad_spend_authority}`;
  renderStages(run.stages);
  renderScores(run.result.scoring);
  renderRisks(run.result.risks);
  $('jsonOut').textContent = JSON.stringify(run,null,2);
}

async function runScenario() {
  setStatus('Executing real Vercel scenario…','running');
  $('runBtn').disabled = true;
  $('runBtn').textContent = 'Running CIE…';
  const start = performance.now();
  try {
    const response = await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload())});
    const data = await response.json();
    if (!response.ok) throw new Error(data?.missing ? `Missing: ${data.missing.join(', ')}` : data?.error || 'Scenario failed');
    const roundTrip = Math.round(performance.now()-start);
    renderRun(data);
    $('roundTrip').textContent = `${roundTrip} ms`;
    setStatus(`Executed · HTTP ${response.status} · ${data.run_id}`,'pass');
  } catch (error) {
    setStatus(`Run failed · ${error.message}`,'fail');
  } finally {
    $('runBtn').disabled=false;
    $('runBtn').textContent='Run CIE scenario →';
  }
}

$('runBtn').addEventListener('click',runScenario);
document.querySelectorAll('[data-preset]').forEach((button)=>button.addEventListener('click',()=>loadPreset(button.dataset.preset)));
$('copyJson').addEventListener('click',async()=>{if(!lastRun)return;await navigator.clipboard.writeText(JSON.stringify(lastRun,null,2));$('copyJson').textContent='Copied';setTimeout(()=>$('copyJson').textContent='Copy JSON',1200);});
$('downloadJson').addEventListener('click',()=>{if(!lastRun)return;const blob=new Blob([JSON.stringify(lastRun,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`${lastRun.run_id}.json`;a.click();URL.revokeObjectURL(url);});

loadPreset('media');
