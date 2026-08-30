const coreSystems = [
  {name:'CrownThrive OS',tag:'Institutional control + truth',desc:'Canonical institutional source of truth for current phase, policy, release lineage, stable identities, evidence boundaries, component state, and convergent operations.'},
  {name:'CHLOM',tag:'Rights · Rules · Roles · Revenue · Records · Remedies',desc:'Compliance Hybrid Licensing and Ownership Model. Governs bounded authority, licensing, rights, roles, records, commercial rules, and remedies.'},
  {name:'Cultural Imprint Engine',tag:'Cultural governance',desc:'Governs cultural meaning, narrative continuity, representation, imprint identity, aesthetics, editorial integrity, and responsible reuse.'},
  {name:'ThriveBase',tag:'Durable operational state',desc:'Operational substrate for workflow, queues, evidence, registries, scheduling, automation, state, and durable execution.'},
  {name:'PENTA Fabric',tag:'Execution grammar',desc:'The shared Discover → Govern → Execute → Verify → Preserve vocabulary spanning routes, queues, factories, tests, deploys, reconciliation, and recovery.'},
  {name:'PentaGreen',tag:'Economic activation',desc:'Governed commerce and economic activation authority connecting approved offers, revenue surfaces, distribution, and measurable economic circulation.'},
  {name:'PentaDocs',tag:'Institutional knowledge',desc:'Human and machine-readable knowledge projection for doctrine, current state, glossary terms, histories, runbooks, and successor links.'},
  {name:'PentaGeneration',tag:'Seven-generation continuity',desc:'Long-horizon succession, stewardship, portability, archives, handoff, recovery, provenance, and institutional memory.'}
];

const systems = [
  ['Convergent Ecosystem','Core','Ecosystem architecture and operating field','Institutional architecture'],
  ['Thrive Flywheel','Core','Compounding discovery, engagement, value, circulation, retention, and expansion','Momentum engine'],
  ['Cultural Imprint Engine','Governance','Imprint classification, narrative doctrine, aesthetics, and cultural integrity','Cultural governance'],
  ['CHLOM','Governance','Rights, rules, roles, licensing, records, compliance, and remedies','Governance architecture'],
  ['PENTA Fabric','Core','Discover, Govern, Execute, Verify, Preserve across human and machine operations','Operating grammar'],
  ['ThriveBase','Infrastructure','Queues, workflow, evidence, registry, scheduling, automation, and state','Operational substrate'],
  ['PentaGreen','Commerce','Governed commerce and economic activation','Economic authority'],
  ['PentaDocs','Infrastructure','Institutional documentation and machine-readable knowledge projection','Knowledge layer'],
  ['PentaGeneration','Governance','Succession, portability, provenance, recovery, and seven-generation stewardship','Continuity layer'],
  ['CrownThrive IO','Infrastructure','QR, URL, identity, routing, and utility infrastructure','Digital utility'],
  ['CrownPulse','Infrastructure','Visitor signals, performance intelligence, and real-time operational insight','Signal intelligence'],
  ['CrownLytics','Infrastructure','Analytics, heatmaps, session intelligence, measurement, and optimization','Analytics'],
  ['ThrivePush','Infrastructure','Audience segmentation and automated web-push communication flows','Messaging infrastructure'],
  ['ThriveTools','Infrastructure','Utility, converter, checker, and operator productivity tools','Tooling'],
  ['ThriveTools SEO','Infrastructure','Scheduled audits, SEO analysis, diagnostics, and optimization','Search intelligence'],
  ['ThriveTools OPT','Infrastructure','Cloud optimization, compression, storage, and automation API utilities','Optimization tooling'],
  ['Thrive AI Studio','Infrastructure','AI-powered content, analytics, assistants, and workflow capabilities','AI platform'],
  ['NeuralCraft','Infrastructure','Industry-specific AI solutions, prebuilt assistants, and integrations','AI solutions'],
  ['ThriveApps','Infrastructure','Web-to-app conversion, app publishing, and custom application delivery','Application platform'],
  ['BrandCards','Infrastructure','Digital identity, QR routing, and lead-capture experiences','Identity surface'],
  ['ThriveKiosks','Infrastructure','Kiosk builder, lead capture, and QR-based physical-to-digital routing','Physical-digital infrastructure'],
  ['My CrownOasis','Infrastructure','AI website generation and conversion-oriented web experiences','Website platform'],
  ['ThriveMaps','Community','Feedback, voting, public roadmaps, changelogs, and community prioritization','Feedback infrastructure'],
  ['FindCliques','Community','Discovery and relationship formation across interest and business communities','Community discovery'],
  ['NFTCliques','Community','Network and community corridor for NFT-aligned participation','Community network'],
  ['ChainCliques','Community','Networking, project promotion, and community discovery','Web3 community'],
  ['ThrivePeer','Community','Mentorship, portfolio development, peer exchange, and professional connection','Peer network'],
  ['ThriveSeat','Community','Service-provider discovery, booking, and integrated transaction pathways','Marketplace infrastructure'],
  ['Collab Portal','Community','Performance tracking, resource coordination, partner and program oversight','Collaboration control'],
  ['Collab Portal OS','Infrastructure','Execution workflow, signatures, versioning, audit logs, and controlled access','Operations workspace'],
  ['The Mane Experience','Beauty','Community engagement, culture, education, and beauty-industry storytelling','Beauty + culture community'],
  ['Locticians','Beauty','Loc-care professional discovery, client acquisition, education, and community networking','Beauty professional network'],
  ['Melanin Magic','Beauty','Product development, e-commerce, retail, and culturally aligned beauty commerce','Beauty brand'],
  ['Melanin Magic Wholesale','Beauty','Wholesale access, product distribution, and partner growth','Wholesale corridor'],
  ['Melanin Magic Suites / MM Suites','Beauty','Suite Pro empowerment, operator pathways, mentorship, and monetization','Physical operating model'],
  ['Melanin Magic Cafe','Commerce','Small-batch coffee, pods, grounds, and cold-brew experiences','Consumer brand'],
  ['Get Kenetic!','Commerce','Performance nutrition, supplements, and routine stacks','Wellness commerce'],
  ['Good Shit Only','Commerce','Lifestyle brand, merch drops, and cultural commerce','Lifestyle brand'],
  ['Tears of Defeat','Commerce','Novelty gifts, humor merchandise, and limited-run drops','Novelty commerce'],
  ['ThriveSip','Commerce','Coffee, tea, functional blends, and subscription products','Beverage brand'],
  ['ThriveWick','Commerce','Candles, diffusers, and ritual-oriented home products','Home + ritual brand'],
  ['ThriveThreads','Commerce','Streetwear, limited drops, and lifestyle fashion','Apparel brand'],
  ['AdLuxe Network','Commerce','Display, video, campaign, and cross-ecosystem advertising infrastructure','Advertising network'],
  ['CrownRewards','Commerce','Loyalty, partner integration, staff tools, and member reward logic','Loyalty engine'],
  ['CrownFluence','Commerce','Influencer discovery, recruitment, campaigns, and monetization','Influence network'],
  ['Crown Affiliates','Commerce','Affiliate distribution, partner commissions, and product promotion','Affiliate engine'],
  ['Crown Ambassadors','Commerce','Ambassador activation, premium access, referrals, and advocacy','Ambassador network'],
  ['ThrivePerks','Commerce','Challenges, bounties, pilot incentives, credits, and promotional rewards','Activation incentives'],
  ['ThriveTickets','Commerce','Event management, ticketing, and attendee engagement','Ticketing platform'],
  ['Luxperiences','Commerce','Curated luxury travel, bespoke itineraries, and premium experiences','Experience commerce'],
  ['Go-Flipbooks','Media','Interactive flipbooks, transformed documents, lookbooks, and digital publishing','Publishing platform'],
  ['Melanated TV','Media','Culturally rich streaming, programming, education, and community media','Television network'],
  ['Melanated Voices','Media','Streaming, discovery, creator exposure, and monetization','Creator media'],
  ['Virality Music by CrownThrive','Media','Music releases, artist collaboration, marketing, publishing, and evidence','Music ecosystem'],
  ['CrownThrive Studios / ThriveStudio','Media','Video, podcast, audio, campaign, and production capability','Production studio'],
  ['Melanated Vault','Media','Art marketplace, creator commerce, live auctions, and protected cultural assets','Creator marketplace'],
  ['Melanated Stock','Media','Archived stock-media lineage retained for provenance and successor mapping','Archived media surface'],
  ['Lyfted Society','Media','Short-form creator monetization, community subscriptions, and audience growth','Creator network'],
  ['The Artful Mane Gallery','Culture','Curated art, artist spotlights, marketplace discovery, and cultural commerce','Art gallery'],
  ['The Sermon Toolkit','Education','Multimedia sermon development, learning resources, and ministry tools','Faith + education'],
  ['CrownThriveU','Education','Expert-led learning, professional certification, networking, and skills development','Education platform'],
  ['CrownInsights','Education','Visual guides, learning guides, demonstrations, and knowledge translation','Learning media'],
  ['QuizNuggets','Education','Micro-learning, knowledge checks, onboarding, streaks, and skill validation','Learning engine'],
  ['ThriveAlumni','Education','Long-term learning-community relationships and alumni continuity','Alumni network'],
  ['CrownThrive Impact Institute','Impact','Measurable outcomes, impact standards, sustainability, accountability, and programs','Impact institution'],
  ['ThriveFund Capital Engine','Impact','Ecosystem funding, resource allocation, milestones, reinvestment, and proof','Capital engine'],
  ['Hybrid Incubator','Core','Venture incubation, operator development, and governed launch framework','Incubation model'],
  ['Seat Model','Governance','Participation architecture, role design, identity, and contribution logic','Participation model'],
  ['Entry + Gateways','Governance','Onboarding, routing, gateway coordination, and first-win conversion','Entry architecture'],
  ['Corridors + Infrastructure','Governance','Corridor scope, anti-overlap discipline, shared infrastructure, and ownership','Integration architecture'],
  ['IP Ownership','Governance','Rights protection, licensing standards, eligibility, and enforcement','IP governance'],
  ['Governance Stack','Governance','Authority maps, decision rights, standards, enforcement, and dispute continuity','Authority architecture'],
  ['Corridor Integration Rules','Governance','CIE-governed routing, cross-corridor standards, identity, and proof loops','Integration rules'],
  ['dS-CaaS','Governance','Always-on compliance logic, eligibility, permission automation, and audit proof','Compliance service'],
  ['Compensation Structure','Governance','Ownership alignment, commissions, payouts, and generational guardrails','Economic governance'],
  ['Succession + Gen. Lock','Governance','Stewardship succession, knowledge transfer, and long-horizon protections','Succession architecture'],
  ['InfoSec + Signatures','Governance','Access control, signatures, incident discipline, security, and auditability','Security governance'],
  ['Help Center Architecture','Infrastructure','Policies, runbooks, support knowledge, source-of-truth projection, and consistency','Knowledge operations'],
  ['Risk + D&O + Data','Governance','Institutional risk controls, leadership protection, data retention, and defensibility','Risk governance'],
  ['Operating Rhythm','Core','Daily execution, weekly alignment, quarterly strategy, and institutional cadence','Operating cadence'],
  ['Roster + Brand Directory','Core','Official inventory, naming, status, routing consistency, and auditability','Registry control'],
  ['Operating Spine','Core','Governance, documentation, execution, compliance, measurement, and routing backbone','Institutional backbone'],
  ['Network Status','Infrastructure','Operational availability, maintenance, and incident visibility','Status surface'],
  ['ThriveSupport','Infrastructure','Help center, support system, and live-assistance routing','Support infrastructure'],
  ['CrownThrive Roadmap','Core','Public progress, ecosystem enhancements, and operating priorities','Roadmap projection']
].map(([name,category,desc,role])=>({name,category,desc,role}));

const categoryOrder=['All','Core','Governance','Infrastructure','Community','Beauty','Media','Commerce','Education','Impact','Culture'];
const registryGrid=document.querySelector('#registryGrid');
const registrySearch=document.querySelector('#registrySearch');
const filterRow=document.querySelector('#filterRow');
const registryCount=document.querySelector('#registryCount');
const emptyState=document.querySelector('#emptyState');
let activeCategory='All';

function escapeHTML(value){return String(value).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}

function renderCore(){
  document.querySelector('#coreGrid').innerHTML=coreSystems.map((item,index)=>`<article class="core-card reveal"><div class="core-index"><span>0${index+1}</span><span>${escapeHTML(item.tag)}</span></div><h3>${escapeHTML(item.name)}</h3><p>${escapeHTML(item.desc)}</p><span class="core-tag">Bounded institutional role</span></article>`).join('');
}

function renderFilters(){
  filterRow.innerHTML=categoryOrder.map(category=>`<button type="button" class="filter-btn${category===activeCategory?' active':''}" data-category="${category}">${category}</button>`).join('');
  filterRow.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>{activeCategory=btn.dataset.category;renderFilters();renderRegistry();}));
}

function getFilteredSystems(query=''){
  const q=query.trim().toLowerCase();
  return systems.filter(item=>{
    const categoryOK=activeCategory==='All'||item.category===activeCategory;
    const queryOK=!q||`${item.name} ${item.category} ${item.desc} ${item.role}`.toLowerCase().includes(q);
    return categoryOK&&queryOK;
  });
}

function renderRegistry(){
  const visible=getFilteredSystems(registrySearch.value);
  registryCount.textContent=`${visible.length} ${visible.length===1?'system':'systems'}`;
  emptyState.hidden=visible.length>0;
  registryGrid.innerHTML=visible.map(item=>`<article class="registry-card"><div class="registry-card-head"><small>${escapeHTML(item.category)}</small><i aria-hidden="true"></i></div><h3>${escapeHTML(item.name)}</h3><p>${escapeHTML(item.desc)}</p><span class="registry-role">${escapeHTML(item.role)}</span></article>`).join('');
}

registrySearch.addEventListener('input',renderRegistry);
renderCore();renderFilters();renderRegistry();

document.querySelector('#year').textContent=new Date().getFullYear();
window.addEventListener('scroll',()=>document.querySelector('#topbar').classList.toggle('scrolled',window.scrollY>12),{passive:true});

const revealObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');revealObserver.unobserve(entry.target);}}),{threshold:.08,rootMargin:'0px 0px -40px'});
function observeReveals(){document.querySelectorAll('.reveal:not(.visible)').forEach(el=>revealObserver.observe(el));}
observeReveals();

fetch('/build.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('build proof unavailable');return r.json();}).then(build=>{
  document.querySelector('#deployState').textContent='Bound';
  const sha=build.commit&&build.commit!=='local'?build.commit.slice(0,8):'local';
  document.querySelector('#buildCommit').textContent=`source ${sha} · ${build.branch||'local'}`;
  const date=new Date(build.builtAt);
  document.querySelector('#buildTime').textContent=Number.isNaN(date.getTime())?'':date.toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
}).catch(()=>{
  document.querySelector('#deployState').textContent='Unbound';
  document.querySelector('#buildCommit').textContent='deployment proof unavailable';
});

const commandDialog=document.querySelector('#commandDialog');
const commandTrigger=document.querySelector('#commandTrigger');
const commandInput=document.querySelector('#commandInput');
const commandResults=document.querySelector('#commandResults');

function commandItems(q=''){
  const value=q.trim().toLowerCase();
  const all=[
    {name:'Operating Core',category:'Navigation',desc:'CrownThrive OS, CHLOM, CIE, ThriveBase, PENTA, PentaGreen, PentaDocs, PentaGeneration',anchor:'#operating-core'},
    {name:'PENTA Lifecycle',category:'Navigation',desc:'Discover → Govern → Execute → Verify → Preserve',anchor:'#penta'},
    {name:'Ecosystem Registry',category:'Navigation',desc:'Search the CrownThrive operating field',anchor:'#ecosystem'},
    {name:'Deployment Continuity',category:'Navigation',desc:'Git-to-Vercel build proof and daily reconciliation',anchor:'#continuity'},
    ...systems.map(item=>({...item,anchor:'#ecosystem'}))
  ];
  return all.filter(item=>!value||`${item.name} ${item.category} ${item.desc||''} ${item.role||''}`.toLowerCase().includes(value)).slice(0,12);
}
function renderCommand(q=''){
  const items=commandItems(q);
  commandResults.innerHTML=items.length?items.map((item,index)=>`<button type="button" class="command-item" data-index="${index}" data-anchor="${item.anchor}"><span><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.desc||item.role||'')}</small></span><span>${escapeHTML(item.category)}</span></button>`).join(''):'<div class="empty-state">No OS result found.</div>';
  commandResults.querySelectorAll('.command-item').forEach(btn=>btn.addEventListener('click',()=>{
    const selected=items[Number(btn.dataset.index)];
    commandDialog.close();
    if(selected.anchor==='#ecosystem'&&!['Ecosystem Registry'].includes(selected.name)){
      activeCategory='All';renderFilters();registrySearch.value=selected.name;renderRegistry();
    }
    document.querySelector(selected.anchor)?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  }));
}
function openCommand(){renderCommand('');commandDialog.showModal();setTimeout(()=>commandInput.focus(),0);}
commandTrigger.addEventListener('click',openCommand);
commandInput.addEventListener('input',()=>renderCommand(commandInput.value));
commandDialog.addEventListener('close',()=>{commandInput.value='';});
document.addEventListener('keydown',event=>{
  if(event.key==='/'&&!commandDialog.open&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)){event.preventDefault();openCommand();}
});
