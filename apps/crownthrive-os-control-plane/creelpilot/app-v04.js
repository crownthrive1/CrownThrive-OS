(()=>{
  const PACK_KEY='creelpilot:fieldPack';
  const PRO_SESSION_KEY='creelpilot:proSession';
  const PRO_STATE_KEY='creelpilot:proState';
  const extraDen=['fridge','garage','game','grill','locker','reset','yard','edc'];
  const clean=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const json=(key,fallback=null)=>{try{return JSON.parse(localStorage.getItem(key)||'null')??fallback}catch{return fallback}};
  const put=(key,value)=>{try{localStorage.setItem(key,JSON.stringify(value));return true}catch{return false}};

  async function extraNearby(lat,lon){
    const radius=50000;
    const q=`[out:json][timeout:20];(nwr(around:${radius},${lat},${lon})["leisure"="slipway"];nwr(around:${radius},${lat},${lon})["leisure"="fishing"];nwr(around:${radius},${lat},${lon})["sport"="fishing"];nwr(around:${radius},${lat},${lon})["man_made"="pier"];nwr(around:${radius},${lat},${lon})["amenity"="drinking_water"];nwr(around:${radius},${lat},${lon})["vending"="ice"];nwr(around:${radius},${lat},${lon})["shop"="general"];);out center tags;`;
    const r=await fetch('https://overpass-api.de/api/interpreter?data='+encodeURIComponent(q));
    if(!r.ok)throw new Error('access-nearby');
    const j=await r.json();
    return (j.elements||[]).map(x=>{
      const la=x.lat??x.center?.lat,lo=x.lon??x.center?.lon,t=x.tags||{};
      if(!la||!lo)return null;
      let category='outdoors',kind=t.leisure||t.sport||t.man_made||t.amenity||t.vending||t.shop||'access';
      if(t.leisure==='slipway')category='marina';
      if(t.amenity==='drinking_water'||t.vending==='ice'||t.shop==='general')category='supplies';
      const fallback=t.leisure==='slipway'?'Boat ramp':t.leisure==='fishing'||t.sport==='fishing'?'Fishing access':t.man_made==='pier'?'Pier':t.vending==='ice'?'Ice stop':t.amenity==='drinking_water'?'Water stop':'General supply';
      return {name:t.name||fallback,kind,category,lat:la,lon:lo,addr:[t['addr:housenumber'],t['addr:street'],t['addr:city']].filter(Boolean).join(' '),phone:t.phone||t['contact:phone']||'',website:t.website||t['contact:website']||'',dist:km(lat,lon,la,lo)};
    }).filter(Boolean).filter(x=>x.dist<85).sort((a,b)=>a.dist-b.dist).slice(0,30);
  }

  if(typeof getNearby==='function'){
    const priorGetNearby=getNearby;
    getNearby=async function(lat,lon){
      const base=await priorGetNearby(lat,lon).catch(()=>[]);
      const extra=await extraNearby(lat,lon).catch(()=>[]);
      const seen=new Set();
      return [...base,...extra].filter(x=>{
        const key=`${String(x.name||'').toLowerCase()}|${Number(x.lat).toFixed(4)}|${Number(x.lon).toFixed(4)}`;
        if(seen.has(key))return false;seen.add(key);return true;
      }).sort((a,b)=>(a.dist??999)-(b.dist??999)).slice(0,60);
    };
  }

  function routePoint(href){
    try{
      const u=new URL(href,location.href),route=u.searchParams.get('route');
      const end=route?.split(';').pop()?.split(',').map(Number);
      return end?.length===2&&end.every(Number.isFinite)?{lat:end[0],lon:end[1]}:null;
    }catch{return null}
  }

  function mapBar(){
    let bar=document.querySelector('#mapFocusBar');
    if(bar)return bar;
    const frame=document.querySelector('#mapFrame');if(!frame)return null;
    bar=document.createElement('div');bar.id='mapFocusBar';bar.className='map-focus-bar';bar.hidden=true;
    frame.parentElement?.insertBefore(bar,frame);
    return bar;
  }

  function focusStop(name,point){
    const frame=document.querySelector('#mapFrame');if(!frame||!point)return;
    frame.src=mapURL(point.lat,point.lon);document.querySelector('#mapEmpty')?.classList.add('hide');
    const bar=mapBar();if(bar){bar.hidden=false;bar.innerHTML=`<div><span>MAP FOCUS</span><b>${clean(name)}</b></div><button id="mapReturn">My area</button>`;bar.querySelector('#mapReturn').onclick=()=>{if(coords){frame.src=mapURL(coords.lat,coords.lon);bar.hidden=true}else useLocation()};}
    frame.scrollIntoView({behavior:'smooth',block:'center'});toast(`${name} focused on the field map.`);
  }

  function enhanceNearby(){
    document.querySelectorAll('#nearbyList .nearbyitem').forEach(item=>{
      if(item.querySelector('[data-map-stop]'))return;
      const route=item.querySelector('a[href*="openstreetmap.org/directions"]'),point=routePoint(route?.href);if(!point)return;
      const name=item.querySelector('b')?.textContent||'Local stop';
      const button=document.createElement('button');button.type='button';button.dataset.mapStop='1';button.className='map-stop';button.textContent='Map';button.onclick=()=>focusStop(name,point);
      const actions=item.querySelector('.near-actions')||route?.parentElement||item;actions.insertBefore(button,route||null);
    });
  }

  const nearbyRoot=document.querySelector('#nearbyList');
  if(nearbyRoot){new MutationObserver(enhanceNearby).observe(nearbyRoot,{childList:true,subtree:true});enhanceNearby();}

  function packPayload(){
    const den={};extraDen.forEach(k=>den[k]=json(`creelpilot:den:${k}`,[]));
    return {
      schema:'creelpilot.field-pack.v1',
      saved_at:new Date().toISOString(),
      plan:json('creelpilot:lastPlan',null),
      saved_stops:json('creelpilot:savedStops',[]),
      tackle_box:json('creelpilot:gear',[]),
      recent_catches:json('creelpilot:catches',[]).slice(0,8),
      den,
      field_conditions:{weather:typeof wx==='object'?{temp:wx.temp,wind:wx.wind,code:wx.code,sunrise:wx.sunrise,source:wx.source}:null,coordinates:coords?{lat:+coords.lat.toFixed(4),lon:+coords.lon.toFixed(4)}:null},
      offline_note:'App shell and this field pack are saved locally. Live map tiles, weather, alerts and local-business refresh still require a connection.'
    };
  }

  function packStatus(){
    const root=document.querySelector('#fieldPackState');if(!root)return;
    const pack=json(PACK_KEY,null);
    if(!pack){root.textContent='No offline field pack saved yet.';return}
    const count=(pack.saved_stops?.length||0)+(pack.tackle_box?.length||0);
    root.textContent=`Saved ${new Date(pack.saved_at).toLocaleString()} · ${count} tackle + stop items · ${pack.plan?'plan included':'build a plan to include it'}`;
  }

  function savePack(){
    const pack=packPayload();
    if(!put(PACK_KEY,pack))return toast('This browser could not save the field pack.');
    navigator.storage?.persist?.().catch(()=>{});packStatus();toast('Offline field pack saved on this device.');
  }

  async function copyPack(){
    const p=json(PACK_KEY,null)||packPayload();
    const text=[
      'CreelPilot Field Pack',
      p.plan?`${p.plan.sp} · ${p.plan.water} · ${p.plan.h} hr`:'No field plan saved',
      `${p.tackle_box?.length||0} tackle items · ${p.saved_stops?.length||0} saved stops`,
      p.field_conditions?.weather?`${p.field_conditions.weather.temp}° · ${p.field_conditions.weather.wind} mph`:'No current conditions saved',
      'Check current access, regulations, weather and safety before departure.'
    ].join('\n');
    try{await navigator.clipboard.writeText(text);toast('Field pack summary copied.')}catch{toast('Clipboard is unavailable in this browser.')}
  }

  function injectFieldPack(){
    if(document.querySelector('#fieldPack'))return;
    const host=document.querySelector('#quickStops')||document.querySelector('#nearby');if(!host)return;
    const box=document.createElement('div');box.id='fieldPack';box.className='field-pack app-reveal';
    box.innerHTML='<div class="field-pack-copy"><span>OFFLINE FIELD PACK</span><b>Grab the plan before signal gets weak.</b><p id="fieldPackState">No offline field pack saved yet.</p><small>Stores plan, tackle, saved stops, recent catches and Den inventory locally. Map tiles and live provider data are not represented as offline.</small></div><div class="field-pack-actions"><button class="primary" id="fieldPackSave">Save pack</button><button class="secondary" id="fieldPackCopy">Copy summary</button><button class="ghost" id="fieldPackClear">Clear</button></div>';
    host.append(box);box.querySelector('#fieldPackSave').onclick=savePack;box.querySelector('#fieldPackCopy').onclick=copyPack;box.querySelector('#fieldPackClear').onclick=()=>{localStorage.removeItem(PACK_KEY);packStatus();toast('Offline field pack cleared.')};packStatus();requestAnimationFrame(()=>box.classList.add('visible'));
  }

  function setProUi(mode,status){
    const state=document.querySelector('#proState');
    if(state)state.textContent=status;
    document.body.classList.toggle('cp-pro',mode==='verified');
    document.body.classList.toggle('cp-pro-cached',mode==='cached');
    let badge=document.querySelector('#proBadge');
    if(!badge){badge=document.createElement('span');badge.id='proBadge';badge.className='pro-badge';document.querySelector('.topactions')?.prepend(badge)}
    if(badge){badge.hidden=mode==='free';badge.textContent=mode==='verified'?'PRO VERIFIED':mode==='cached'?'PRO OFFLINE':'VERIFYING';}
  }

  async function verifyPro(){
    const session=sessionStorage.getItem('creelpilot:checkout-session')||localStorage.getItem(PRO_SESSION_KEY)||'';
    const previous=json(PRO_STATE_KEY,null);
    if(!session){setProUi('free','Free plan · Pro is $4.99/month');return}
    if(!navigator.onLine&&previous?.verified){setProUi('cached','Pro status cached locally · reconnect to reverify');return}
    setProUi('checking','Verifying Pro subscription…');
    try{
      const r=await fetch(`/api/creelpilot-entitlement?session_id=${encodeURIComponent(session)}`,{cache:'no-store',headers:{Accept:'application/json'}}),j=await r.json();
      if(!r.ok||!j.verified)throw Object.assign(new Error(j.status||'not-active'),{payload:j});
      localStorage.setItem(PRO_SESSION_KEY,session);put(PRO_STATE_KEY,{verified:true,status:j.subscription_status,checked_at:j.checked_at});sessionStorage.removeItem('creelpilot:checkout-session');
      setProUi('verified',`Pro verified · ${j.subscription_status}`);toast('CreelPilot Pro verified.');
    }catch(error){
      const status=error?.payload?.status;
      localStorage.removeItem(PRO_STATE_KEY);
      if(status==='STRIPE_SERVER_BINDING_REQUIRED')setProUi('free','Checkout received · secure Stripe server binding is required before Pro unlocks');
      else if(!navigator.onLine&&previous?.verified)setProUi('cached','Pro status cached locally · reconnect to reverify');
      else setProUi('free','Pro not verified · Free remains active');
    }
  }

  function injectAppPulse(){
    if(document.querySelector('#v04Pulse'))return;
    const host=document.querySelector('.heroactions');if(!host)return;
    const pulse=document.createElement('span');pulse.id='v04Pulse';pulse.className='v04-pulse';pulse.innerHTML='<i></i> APP v0.4 · FIELD PACK + ACCESS MAP';host.append(pulse);
  }

  injectFieldPack();injectAppPulse();mapBar();verifyPro();
  addEventListener('online',verifyPro);
})();
