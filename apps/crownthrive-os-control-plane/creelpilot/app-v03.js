(()=>{
  const CP={nearby:[],filter:'all',alert:null,watch:null,tripTimer:null};
  const miles=km=>`${(km*0.621371).toFixed(km<16?1:0)} mi`;
  const safe=s=>esc(s);
  const category=t=>{
    const v=String(t||'').toLowerCase();
    if(/fishing|tackle|bait/.test(v))return'tackle';
    if(/marina|boat/.test(v))return'marina';
    if(/fuel/.test(v))return'fuel';
    if(/hardware|doityourself/.test(v))return'hardware';
    if(/car_repair|car_parts|tyres/.test(v))return'auto';
    if(/camp|caravan/.test(v))return'camp';
    if(/convenience|supermarket/.test(v))return'supplies';
    return'outdoors';
  };
  const label=c=>({tackle:'Tackle',outdoors:'Outdoors',marina:'Marina',fuel:'Fuel',hardware:'Hardware',auto:'Auto',camp:'Camp',supplies:'Supplies'})[c]||'Nearby';
  const dedupe=items=>{
    const seen=new Set();
    return items.filter(x=>{const k=`${String(x.name).toLowerCase()}|${Number(x.lat).toFixed(4)}|${Number(x.lon).toFixed(4)}`;if(seen.has(k))return false;seen.add(k);return true});
  };
  async function overpass(lat,lon,radius){
    const q=`[out:json][timeout:22];(nwr(around:${radius},${lat},${lon})["shop"~"fishing|sports|outdoor|hunting|hardware|doityourself|car_repair|car_parts|convenience|supermarket|boat"];nwr(around:${radius},${lat},${lon})["leisure"="marina"];nwr(around:${radius},${lat},${lon})["amenity"~"boat_rental|fuel"];nwr(around:${radius},${lat},${lon})["tourism"~"camp_site|caravan_site"];);out center tags;`;
    const r=await fetch('https://overpass-api.de/api/interpreter?data='+encodeURIComponent(q));
    if(!r.ok)throw new Error('nearby');
    const j=await r.json();
    return (j.elements||[]).map(x=>{
      const la=x.lat??x.center?.lat,lo=x.lon??x.center?.lon,t=x.tags||{},kind=t.shop||t.leisure||t.amenity||t.tourism||'outdoor';
      return {name:t.name||t.brand||label(category(kind))+' stop',kind,category:category(`${kind} ${t.name||''}`),lat:la,lon:lo,addr:[t['addr:housenumber'],t['addr:street'],t['addr:city']].filter(Boolean).join(' '),phone:t.phone||t['contact:phone']||'',website:t.website||t['contact:website']||'',dist:(la&&lo)?km(lat,lon,la,lo):999};
    }).filter(x=>x.lat&&x.lon&&x.dist<85).sort((a,b)=>a.dist-b.dist);
  }
  const baseNearby=getNearby;
  getNearby=async function(lat,lon){
    try{
      let items=await overpass(lat,lon,35000);
      if(items.length<18){const wider=await overpass(lat,lon,80000);items=items.concat(wider)}
      items=dedupe(items).sort((a,b)=>a.dist-b.dist).slice(0,40);
      try{localStorage.setItem('creelpilot:nearbyCache',JSON.stringify({at:Date.now(),items}))}catch{}
      return items;
    }catch{
      try{const cached=JSON.parse(localStorage.getItem('creelpilot:nearbyCache')||'null');if(cached?.items?.length)return cached.items}catch{}
      return baseNearby(lat,lon);
    }
  };
  function filterButtons(){
    let root=document.querySelector('#nearbyFilters');
    if(!root){root=document.createElement('div');root.id='nearbyFilters';root.className='nearby-filters';document.querySelector('#nearbyList')?.before(root)}
    const cats=['all',...new Set(CP.nearby.map(x=>x.category||category(x.kind)))];
    root.innerHTML=cats.map(c=>`<button class="filterchip${CP.filter===c?' active':''}" data-nearfilter="${safe(c)}">${c==='all'?'All':label(c)}${c==='all'?` · ${CP.nearby.length}`:` · ${CP.nearby.filter(x=>(x.category||category(x.kind))===c).length}`}</button>`).join('');
    root.querySelectorAll('[data-nearfilter]').forEach(b=>b.onclick=()=>{CP.filter=b.dataset.nearfilter;filterButtons();drawNearby()});
  }
  function drawNearby(){
    const root=document.querySelector('#nearbyList');if(!root)return;
    const items=CP.filter==='all'?CP.nearby:CP.nearby.filter(x=>(x.category||category(x.kind))===CP.filter);
    root.innerHTML='';
    if(!items.length){root.innerHTML='<div class="empty">No matching local stops are mapped in this radius. Try All or refresh nearby.</div>';return}
    items.forEach((x,i)=>{
      const e=document.createElement('div');e.className='nearbyitem app-reveal';
      const c=document.createElement('div'),b=document.createElement('b'),s=document.createElement('span'),actions=document.createElement('div');
      b.textContent=x.name;s.textContent=`${label(x.category||category(x.kind))} · ${miles(x.dist)}${x.addr?' · '+x.addr:''}`;
      const route=document.createElement('a');route.textContent='Route';route.href=osmDirections(x.lat,x.lon);route.target='_blank';route.rel='noopener';
      const saveBtn=document.createElement('button');saveBtn.className='save-stop';saveBtn.textContent='Save';saveBtn.onclick=()=>saveStop(x);
      actions.className='near-actions';actions.append(saveBtn,route);c.append(b,s);e.append(c,actions);root.append(e);
      requestAnimationFrame(()=>setTimeout(()=>e.classList.add('visible'),Math.min(i*28,300)));
    });
  }
  renderNearby=function(items){
    CP.nearby=(items||[]).map(x=>({...x,category:x.category||category(`${x.kind} ${x.name}`)}));
    document.querySelector('#storeCount').textContent=`${CP.nearby.length} nearby`;
    filterButtons();drawNearby();renderStopBoard();
  };
  function getSavedStops(){try{return JSON.parse(localStorage.getItem('creelpilot:savedStops'))||[]}catch{return[]}}
  function saveStop(x){
    let a=getSavedStops();if(!a.some(y=>y.name===x.name&&Math.abs(y.lat-x.lat)<.0001)){a.unshift({name:x.name,category:x.category,lat:x.lat,lon:x.lon,addr:x.addr,dist:x.dist});a=a.slice(0,12);localStorage.setItem('creelpilot:savedStops',JSON.stringify(a));toast('Stop saved for the next run.');haptic()}else toast('That stop is already saved.');renderStopBoard();
  }
  function renderStopBoard(){
    const root=document.querySelector('#quickStopList');if(!root)return;
    const a=getSavedStops();root.innerHTML=a.length?a.map((x,i)=>`<div class="quick-stop"><div><b>${safe(x.name)}</b><span>${safe(label(x.category))}${Number.isFinite(x.dist)?' · '+miles(x.dist):''}</span></div><button data-stoprm="${i}" aria-label="Remove saved stop">×</button></div>`).join(''):'<div class="empty">Save tackle, fuel, marina or supply stops from Nearby and they stay here.</div>';
    root.querySelectorAll('[data-stoprm]').forEach(b=>b.onclick=()=>{const a=getSavedStops();a.splice(+b.dataset.stoprm,1);localStorage.setItem('creelpilot:savedStops',JSON.stringify(a));renderStopBoard()});
  }
  async function weatherAlerts(lat,lon){
    try{
      const r=await fetch(`https://api.weather.gov/alerts/active?point=${lat},${lon}`,{headers:{Accept:'application/geo+json'}});if(!r.ok)throw 0;
      const j=await r.json();const f=(j.features||[])[0];return f?{event:f.properties?.event||'Weather alert',headline:f.properties?.headline||'',severity:f.properties?.severity||'Unknown',url:f.properties?.uri||''}:null;
    }catch{return null}
  }
  const baseLoadLocal=loadLocal;
  loadLocal=async function(lat,lon){
    await baseLoadLocal(lat,lon);
    CP.alert=await weatherAlerts(lat,lon);renderAlert();
  };
  function renderAlert(){
    let e=document.querySelector('#fieldAlert');
    if(!e){e=document.createElement('div');e.id='fieldAlert';e.className='field-alert';document.querySelector('.sonar-card')?.append(e)}
    if(!CP.alert){e.innerHTML='<span>FIELD STATUS</span><b>No active NWS alert returned for this point.</b>';e.classList.remove('active');return}
    e.classList.add('active');e.innerHTML=`<span>${safe(CP.alert.severity)} WEATHER ALERT</span><b>${safe(CP.alert.event)}</b><small>${safe(CP.alert.headline)}</small>`;
  }
  function haptic(){try{navigator.vibrate?.(18)}catch{}}
  function tripMinutes(){const s=Number(localStorage.getItem('creelpilot:tripStart')||0);return s?Math.max(0,Math.floor((Date.now()-s)/60000)):0}
  function renderTrip(){
    const e=document.querySelector('#tripState');if(!e)return;const s=Number(localStorage.getItem('creelpilot:tripStart')||0),m=tripMinutes();
    e.textContent=s?`Field session · ${Math.floor(m/60)}h ${m%60}m`:'No field session active';
    const b=document.querySelector('#tripStart');if(b)b.textContent=s?'End field session':'Start field session';
  }
  async function tripToggle(){
    const s=Number(localStorage.getItem('creelpilot:tripStart')||0);
    if(s){localStorage.removeItem('creelpilot:tripStart');if(CP.watch){try{await CP.watch.release()}catch{}CP.watch=null}toast('Field session closed. Catch log and gear stay saved.');}
    else{localStorage.setItem('creelpilot:tripStart',String(Date.now()));try{if('wakeLock'in navigator)CP.watch=await navigator.wakeLock.request('screen')}catch{}toast('Field session started. Screen wake lock requested.');haptic()}
    renderTrip();
  }
  async function sharePlan(){
    let p;try{p=JSON.parse(localStorage.getItem('creelpilot:lastPlan')||'null')}catch{}
    const text=p?`CreelPilot field plan: ${p.sp} · ${p.water} · ${p.h} hr · ${p.wx?.temp??'—'}° · ${p.wx?.wind??'—'} mph. Safety, access and regulations still need a current check.`:'CreelPilot — field planning, tackle, local stops and the Den.';
    try{if(navigator.share)await navigator.share({title:'CreelPilot field plan',text,url:location.origin+'/creelpilot'});else if(navigator.clipboard){await navigator.clipboard.writeText(text);toast('Field plan copied.')}}catch{}
  }
  function injectFieldTools(){
    const p=document.querySelector('.planner-actions');if(!p||document.querySelector('#fieldTools'))return;
    const e=document.createElement('div');e.id='fieldTools';e.className='field-tools';e.innerHTML='<div><span class="field-tool-label">FIELD SESSION</span><b id="tripState">No field session active</b></div><div class="field-tool-actions"><button class="secondary" id="sharePlan">Share plan</button><button class="primary" id="tripStart">Start field session</button></div>';
    p.after(e);e.querySelector('#tripStart').onclick=tripToggle;e.querySelector('#sharePlan').onclick=sharePlan;renderTrip();CP.tripTimer=setInterval(renderTrip,30000);
  }
  function injectQuickStops(){
    const near=document.querySelector('#nearby');if(!near||document.querySelector('#quickStops'))return;
    const e=document.createElement('div');e.id='quickStops';e.className='quick-stops';e.innerHTML='<div class="quick-stops-head"><div><span>RUN BOARD</span><b>Saved local stops</b></div><button class="secondary" id="clearStops">Clear</button></div><div id="quickStopList"></div>';
    near.append(e);e.querySelector('#clearStops').onclick=()=>{localStorage.removeItem('creelpilot:savedStops');renderStopBoard();};renderStopBoard();
  }
  function injectDenModules(){
    const grid=document.querySelector('.den-grid');if(!grid)return;
    const extras=[['yard','YARD + PROPERTY','Fuel, trimmer line, blades, gloves, seed, storm prep','Trimmer line · gas · work gloves'],['edc','EVERYDAY CARRY','Wallet, keys, charger, sunglasses, meds, work carry','Charger · sunglasses · spare cable']];
    extras.forEach(([k,title,copy,placeholder])=>{
      if(document.querySelector(`#${k}List`))return;
      const d=document.createElement('div');d.className='den-module app-reveal';d.innerHTML=`<span>${title}</span><b>${copy}</b><div class="den-add"><input id="${k}Input" placeholder="${placeholder}"/><button data-extra-den="${k}">Add</button></div><div class="den-list" id="${k}List"></div>`;grid.append(d);denKeys.push(k);renderDen(k);d.querySelector('[data-extra-den]').onclick=()=>addDen(k);requestAnimationFrame(()=>d.classList.add('visible'));
    });
  }
  function injectProValue(){
    const pro=document.querySelector('#pro .procopy');if(!pro||document.querySelector('#proValue'))return;
    const e=document.createElement('div');e.id='proValue';e.className='pro-value';e.innerHTML='<span>Tackle Vault</span><span>Deeper local discovery</span><span>Trip history</span><span>Den sync layer</span><span>Smart reminders</span><span>Future CrownRewards perks</span>';pro.querySelector('.proactions')?.before(e);
  }
  function injectDock(){
    if(document.querySelector('#appDock'))return;const n=document.createElement('nav');n.id='appDock';n.className='app-dock';n.setAttribute('aria-label','CreelPilot app navigation');n.innerHTML='<a href="#field"><b>⌁</b><span>Field</span></a><a href="#nearby"><b>⌖</b><span>Nearby</span></a><a href="#tackle"><b>▤</b><span>Tackle</span></a><a href="#den"><b>⌂</b><span>Den</span></a><a href="#pro"><b>★</b><span>Pro</span></a>';document.body.append(n);
  }
  function injectStatus(){
    const a=document.querySelector('.topactions');if(!a||document.querySelector('#netState'))return;const s=document.createElement('span');s.id='netState';s.className='net-state';a.prepend(s);const draw=()=>{s.textContent=navigator.onLine?'Online':'Offline-ready';s.classList.toggle('offline',!navigator.onLine)};addEventListener('online',draw);addEventListener('offline',draw);draw();
  }
  function installHero(){
    const actions=document.querySelector('.heroactions');if(!actions||document.querySelector('#installHero'))return;const b=document.createElement('button');b.id='installHero';b.className='secondary install-hero';b.hidden=true;b.textContent='Install CreelPilot';actions.append(b);
    addEventListener('beforeinstallprompt',()=>{b.hidden=false});b.onclick=async()=>{if(!deferredInstall)return toast('Use your browser menu to install CreelPilot.');deferredInstall.prompt();await deferredInstall.userChoice;deferredInstall=null;b.hidden=true};addEventListener('appinstalled',()=>{b.hidden=true;toast('CreelPilot installed.')});
  }
  function reveal(){
    if(!('IntersectionObserver'in window))return;const io=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){x.target.classList.add('visible');io.unobserve(x.target)}}),{threshold:.08});document.querySelectorAll('.card,.den-module').forEach(e=>{e.classList.add('app-reveal');io.observe(e)});
  }
  injectFieldTools();injectQuickStops();injectDenModules();injectProValue();injectDock();injectStatus();installHero();renderAlert();reveal();
})();
