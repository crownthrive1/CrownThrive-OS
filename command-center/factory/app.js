const $ = (id) => document.getElementById(id);
const classify = (value='') => /PASS|READY|ONLINE|ACTIVE|DEPLOYED/.test(value) ? 'pass' : /HOLD|AWAIT|PENDING|UNRESOLVED/.test(value) ? 'hold' : '';
const applyBadge = (id, value) => { const el=$(id); el.textContent=value; el.className=`badge ${classify(value)}`; };
async function load(){
  let data;
  try { const r=await fetch('/api/factory/status',{cache:'no-store'}); if(!r.ok) throw new Error(`HTTP ${r.status}`); data=await r.json(); }
  catch(e){ const r=await fetch('./fallback-status.json',{cache:'no-store'}); data=await r.json(); data.runtime_state_error=String(e); }
  $('headline-status').textContent=data.status || 'UNKNOWN';
  $('skills').textContent=data.registry?.skills ?? 59; $('families').textContent=data.registry?.families ?? 7; $('bundles').textContent=data.registry?.bundles ?? 9;
  const current=data.current_batch || {}; $('batch').textContent=current.produced ?? '—'; $('tick').textContent=data.tick_id ? `${data.tick_id} · ${data.generated_at}` : 'Committed source; runtime tick readback pending.';
  const cumulative=data.cumulative?.packages ?? 0; $('produced').textContent=Math.min(cumulative,59); $('progress').style.width=`${Math.min(100,(Math.min(cumulative,59)/59)*100)}%`;
  $('ecac').textContent=current.commercial_ecac ?? 0; $('hold').textContent=current.commercial_hold ?? '—';
  const p=data.provider_state || {}; $('github').textContent=p.github_workflow || 'UNKNOWN'; applyBadge('github-badge',p.github_workflow || 'UNKNOWN');
  $('vercel').textContent=p.vercel_command_center || 'UNKNOWN'; applyBadge('vercel-badge',p.vercel_command_center || 'UNKNOWN');
  $('drive').textContent=p.drive_master_ledger || 'UNKNOWN'; applyBadge('drive-badge',p.drive_master_ledger || 'UNKNOWN');
  $('commerce').textContent=p.live_commerce || 'UNKNOWN'; applyBadge('commerce-badge',p.live_commerce || 'UNKNOWN');
  $('clock').textContent=`${data.hourly_clock || '17 * * * * UTC'} · ${data.timezone || 'America/New_York'}`; applyBadge('clock-badge',data.hourly_clock || 'CONFIGURED');
  $('observed').textContent=`Observed: ${data.observed_at || new Date().toISOString()} · ${data.source || 'fallback'}`;
}
load(); setInterval(load,60000);