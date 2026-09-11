(()=>{
  const css=document.createElement('link');css.rel='stylesheet';css.href='/brand-worlds-v02.css';document.head.append(css);
  const body=document.body;
  const safe=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const read=(key,fallback=[])=>{try{return JSON.parse(localStorage.getItem(key)||'null')??fallback}catch{return fallback}};
  const write=(key,value)=>localStorage.setItem(key,JSON.stringify(value));
  const insert=section=>{const footer=document.querySelector('footer.foot');if(footer)footer.before(section);else document.querySelector('main')?.append(section)};

  function zazaStack(){
    const key='zaza:night-stack';
    const s=document.createElement('section');s.className='section world-v2';
    s.innerHTML='<div class="sectionhead"><div><div class="kicker">Listening room stack</div><h2>Build tonight without building another feed.</h2></div><span class="signal">Saved on this device</span></div><div class="world-v2-grid"><div class="world-v2-card"><small>TONIGHT’S STACK</small><h3>Records, ideas, conversations.</h3><p>Queue what belongs in the room. No recommendation algorithm is required.</p><div class="world-v2-row"><input id="zazaStackInput" maxlength="120" placeholder="Record, topic, poem, film, thought…"><button id="zazaStackAdd">Add to room</button></div><div class="world-v2-list" id="zazaStackList"></div></div><div class="world-v2-card"><small>ROOM RULE</small><h3>Presence over scroll.</h3><p>The ZaZa Room is a music, culture and after-dark listening environment. It is not a cannabis storefront, marketplace, delivery service, or sourcing surface.</p><div class="world-v2-stat"><span>Virality Music</span><span>Backroad FM</span><span>MusiqHead</span><span>Melanated Voices</span></div><div class="world-v2-note">Local room state stays in your browser in this release.</div></div></div>';
    insert(s);const input=s.querySelector('#zazaStackInput'),list=s.querySelector('#zazaStackList');
    const draw=()=>{const a=read(key);list.innerHTML=a.length?a.map((x,i)=>`<div class="world-v2-item"><div><b>${safe(x.text)}</b><span>${safe(x.mode||'Room stack')}</span></div><button data-zrm="${i}" aria-label="Remove">×</button></div>`).join(''):'<div class="world-v2-note">Nothing queued. A quiet room is still a room.</div>';list.querySelectorAll('[data-zrm]').forEach(b=>b.onclick=()=>{const a=read(key);a.splice(+b.dataset.zrm,1);write(key,a);draw()})};
    const add=()=>{const text=input.value.trim();if(!text)return;const mode=document.querySelector('#roomLabel')?.textContent||'Room stack',a=read(key);a.unshift({text,mode,at:new Date().toISOString()});write(key,a.slice(0,24));input.value='';draw()};s.querySelector('#zazaStackAdd').onclick=add;input.onkeydown=e=>{if(e.key==='Enter')add()};draw();
  }

  function musiqDesk(){
    const key='musiqhead:release-desk';
    const s=document.createElement('section');s.className='section world-v2';
    s.innerHTML='<div class="sectionhead"><div><div class="kicker">Release desk</div><h2>Package the record before the record moves.</h2></div><span class="signal">Local workboard · no upload</span></div><div class="world-v2-grid"><div class="world-v2-card"><small>NEW WORK ITEM</small><div class="world-v2-fields"><input id="mhTitle" class="wide" maxlength="120" placeholder="Work title"><input id="mhVersion" maxlength="80" placeholder="Version / mix"><select id="mhState"><option value="vault_only">Vault only</option><option value="distribution_candidate">Distribution candidate</option><option value="licensing_candidate">Licensing candidate</option><option value="hold">Hold</option></select></div><div class="world-v2-actions"><button class="primary" id="mhSave">Save to workboard</button></div><div class="world-v2-note">This board does not claim distribution, clearance, registration, licensing approval, or release. Those remain provider/evidence-gated states.</div></div><div class="world-v2-card"><small>WORKBOARD</small><div class="world-v2-list" id="mhList"></div></div></div>';
    insert(s);const list=s.querySelector('#mhList');
    const labels={vault_only:'Vault only',distribution_candidate:'Distribution candidate',licensing_candidate:'Licensing candidate',hold:'Hold'};
    const draw=()=>{const a=read(key);list.innerHTML=a.length?a.map((x,i)=>`<div class="world-v2-item"><div><b>${safe(x.title)}${x.version?' · '+safe(x.version):''}</b><span>${safe(labels[x.state]||x.state)} · local workboard</span></div><button data-mhrm="${i}" aria-label="Remove">×</button></div>`).join(''):'<div class="world-v2-note">No work items yet. Rights readiness above stays the governing checklist.</div>';list.querySelectorAll('[data-mhrm]').forEach(b=>b.onclick=()=>{const a=read(key);a.splice(+b.dataset.mhrm,1);write(key,a);draw()})};
    s.querySelector('#mhSave').onclick=()=>{const title=s.querySelector('#mhTitle').value.trim();if(!title)return;const a=read(key);a.unshift({title,version:s.querySelector('#mhVersion').value.trim(),state:s.querySelector('#mhState').value,at:new Date().toISOString()});write(key,a.slice(0,50));s.querySelector('#mhTitle').value='';s.querySelector('#mhVersion').value='';draw()};draw();
  }

  function magicShelf(){
    const key='mm-suite:shelf-board';
    const s=document.createElement('section');s.className='section world-v2';
    s.innerHTML='<div class="sectionhead"><div><div class="kicker">Backbar + shelf board</div><h2>Know what is on hand before the chair needs it.</h2></div><span class="signal">Local operator board</span></div><div class="world-v2-grid"><div class="world-v2-card"><small>ADD ITEM</small><div class="world-v2-fields"><input id="mmItem" class="wide" maxlength="120" placeholder="Product / backbar item"><input id="mmOnHand" type="number" min="0" step="1" value="6" aria-label="On hand"><input id="mmReorder" type="number" min="0" step="1" value="3" aria-label="Reorder at"></div><div class="world-v2-actions"><button class="primary" id="mmShelfAdd">Add to shelf</button></div><div class="world-v2-note">Use this as an operator planning layer. Wholesale availability, pricing, MOQ and fulfillment terms should be confirmed at the current Melanin Magic commerce surface.</div></div><div class="world-v2-card"><small>REORDER BOARD</small><div class="world-v2-list" id="mmShelfList"></div><div class="world-v2-stat" id="mmShelfStats"></div></div></div>';
    insert(s);const list=s.querySelector('#mmShelfList'),stats=s.querySelector('#mmShelfStats');
    const draw=()=>{const a=read(key),low=a.filter(x=>x.onHand<=x.reorder).length;stats.innerHTML=`<span>${a.length} tracked</span><span>${low} reorder now</span>`;list.innerHTML=a.length?a.map((x,i)=>`<div class="world-v2-item${x.onHand<=x.reorder?' world-v2-low':''}"><div><b>${safe(x.item)}</b><span>${x.onHand} on hand · reorder at ${x.reorder}${x.onHand<=x.reorder?' · REORDER':''}</span></div><button data-mmsrm="${i}" aria-label="Remove">×</button></div>`).join(''):'<div class="world-v2-note">Nothing tracked yet. Add retail or backbar inventory above.</div>';list.querySelectorAll('[data-mmsrm]').forEach(b=>b.onclick=()=>{const a=read(key);a.splice(+b.dataset.mmsrm,1);write(key,a);draw()})};
    s.querySelector('#mmShelfAdd').onclick=()=>{const item=s.querySelector('#mmItem').value.trim();if(!item)return;const a=read(key);a.unshift({item,onHand:Math.max(0,+s.querySelector('#mmOnHand').value||0),reorder:Math.max(0,+s.querySelector('#mmReorder').value||0),at:new Date().toISOString()});write(key,a.slice(0,80));s.querySelector('#mmItem').value='';draw()};draw();
  }

  if(body.classList.contains('zaza'))zazaStack();
  if(body.classList.contains('musiq'))musiqDesk();
  if(body.classList.contains('magic'))magicShelf();
})();
