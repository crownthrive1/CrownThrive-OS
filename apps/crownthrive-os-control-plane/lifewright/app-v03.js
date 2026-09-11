(()=>{
  const read=(key,fallback=null)=>{try{return JSON.parse(localStorage.getItem(key)||'null')??fallback}catch{return fallback}};
  function restoreDay(){
    const d=read('lifewright:lastDay');if(!d)return;
    const set=(id,value)=>{const e=document.querySelector(id);if(e&&value!==undefined&&value!==null)e.value=Array.isArray(value)?value.join('\n'):String(value)};
    set('#must',d.must);set('#should',d.should);set('#want',d.want);set('#hours',d.hours);set('#protect',d.protect);
    const hint=document.querySelector('#locHint');if(hint)hint.textContent='Last day restored locally · rebuild when priorities change';
  }
  function escapeCard(){
    if(document.querySelector('#escapeReady'))return;
    const host=document.querySelector('#life');if(!host)return;
    const last=read('creelpilot:lastPlan'),gear=read('creelpilot:gear',[]),pack=read('creelpilot:fieldPack');
    const e=document.createElement('div');e.id='escapeReady';e.className='escape-ready';
    e.innerHTML=`<div><span>ESCAPE HANDOFF</span><b>${last?`${esc(last.sp)} · ${esc(last.water)} · ${esc(last.h)} hr`:'CreelPilot is ready when you are.'}</b><p>${gear.length} tackle item${gear.length===1?'':'s'} saved${pack?' · offline field pack ready':''}. LifeWright handles the day; CreelPilot handles the fishing lane.</p></div><a href="/creelpilot" class="escape-go">Open CreelPilot →</a>`;
    host.append(e);
  }
  function appDock(){
    if(document.querySelector('#lifeDock'))return;
    const n=document.createElement('nav');n.id='lifeDock';n.className='life-dock';n.setAttribute('aria-label','LifeWright app navigation');
    n.innerHTML='<a href="#day"><b>✓</b><span>Today</span></a><a href="#life"><b>⌂</b><span>Life</span></a><a href="/creelpilot"><b>≈</b><span>Escape</span></a><a href="#partners"><b>↗</b><span>Help</span></a><a href="#os"><b>◆</b><span>OS</span></a>';
    document.body.append(n);
    n.querySelectorAll('a[href^="#"]').forEach(a=>a.onclick=()=>localStorage.setItem('lifewright:lastLane',a.getAttribute('href')));
  }
  function status(){
    const top=document.querySelector('.barin');if(!top||document.querySelector('#lifeNet'))return;
    const s=document.createElement('span');s.id='lifeNet';s.className='life-net';top.insertBefore(s,document.querySelector('#installBtn'));
    const draw=()=>{s.textContent=navigator.onLine?'Online':'Offline-ready';s.classList.toggle('offline',!navigator.onLine)};addEventListener('online',draw);addEventListener('offline',draw);draw();
  }
  function version(){
    document.querySelectorAll('.foot div').forEach(e=>{if(e.textContent.includes('PWA v0.2'))e.textContent=e.textContent.replace('PWA v0.2','PWA v0.3')});
  }
  function pulse(){
    const actions=document.querySelector('.heroactions');if(!actions||document.querySelector('#lwPulse'))return;
    const p=document.createElement('span');p.id='lwPulse';p.className='lw-pulse';p.innerHTML='<i></i> APP v0.3 · LOCAL-FIRST';actions.append(p);
  }
  restoreDay();escapeCard();appDock();status();version();pulse();
})();
