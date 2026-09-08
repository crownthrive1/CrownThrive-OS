/* AdLuxe Places responsive enhancement. Existing React handlers remain authoritative. */
(() => {
 'use strict';
 if (window.__adluxeResponsiveV1) return;
 window.__adluxeResponsiveV1 = true;
 const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
 let root = null, resize = null, mediaObserver = null, userPaused = false, frame = 0;
 let seenVideos = new WeakSet();
 let visibleVideos = new WeakMap();
 const isPaused = () => motion.matches || userPaused;
 function applyMedia(video) {
  if (isPaused() || document.hidden || !visibleVideos.get(video)) video.pause();
  else if (video.autoplay && video.muted) video.play().catch(() => {});
 }
 function refreshMedia() {
  if (!root) return;
  root.dataset.motionPaused = String(isPaused());
  root.querySelectorAll('video').forEach(video => {
   if (!seenVideos.has(video)) { seenVideos.add(video); mediaObserver.observe(video); }
   applyMedia(video);
  });
  const button = root.querySelector('.al-motion-toggle');
  if (button) {
   button.setAttribute('aria-pressed', String(isPaused()));
   const label = motion.matches ? 'Motion reduced by device settings' : userPaused ? 'Resume motion' : 'Pause motion';
   if (button.textContent !== label) button.textContent = label;
   button.disabled = motion.matches;
  }
 }
 function layout() {
  if (!root) return;
  const header = root.querySelector('header'), row = header?.querySelector('.container>div');
  if (!header || !row) return;
  const menu = header.querySelector('#landing-mobile-menu');
  const baseHeight = row.getBoundingClientRect().height + 25;
  root.style.setProperty('--al-nav-offset', `${Math.ceil(baseHeight)}px`);
  const nav = row.querySelector(':scope>nav'), actions = row.querySelector(':scope>div.hidden.shrink-0'), logo = row.querySelector(':scope>a');
  // Start with the desktop dimensions, then use actual content width for translated navigation.
  header.dataset.alCompact = 'false';
  const required = [logo, nav, actions].reduce((sum, el) => sum + (el ? Math.max(el.scrollWidth, el.getBoundingClientRect().width) : 0), 0) + 40;
  const compact = window.innerWidth < 1280 || required > row.clientWidth;
  header.dataset.alCompact = String(compact);
  if (!compact && menu) header.querySelector('button[aria-controls="landing-mobile-menu"]')?.click();
 }
 function queueLayout() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(layout);
 }
 function bind() {
  const next = [...document.querySelectorAll('.adluxe')].find(el => el.querySelector(':scope>main#main'));
  if (!next) { root = null; resize?.disconnect(); mediaObserver?.disconnect(); return; }
  if (root !== next) {
   resize?.disconnect(); mediaObserver?.disconnect(); root = next;
   seenVideos = new WeakSet(); visibleVideos = new WeakMap();
   root.classList.add('al-responsive-home');
   resize = new ResizeObserver(queueLayout);
   const row = root.querySelector('header .container>div');
   if (row) resize.observe(row);
   mediaObserver = new IntersectionObserver(entries => entries.forEach(entry => {
    visibleVideos.set(entry.target, entry.isIntersecting);
    applyMedia(entry.target);
   }), { threshold: .1 });
  }
  const hero = root.querySelector('main>section:first-child .al-rise');
  if (hero && !hero.querySelector('.al-motion-toggle') && root.querySelector('video')) {
   const button = document.createElement('button');
   button.type = 'button'; button.className = 'al-motion-toggle';
   button.addEventListener('click', () => { userPaused = !userPaused; refreshMedia(); });
   hero.appendChild(button);
  }
  root.querySelectorAll('[role="tablist"]').forEach((list, index) => {
   if (!list.hasAttribute('aria-label')) list.setAttribute('aria-label', 'Platform preview');
   list.querySelectorAll('[role="tab"]').forEach((tab, i) => {
    if (!tab.id) tab.id = `al-preview-${index}-${i}`;
    tab.tabIndex = tab.getAttribute('aria-selected') === 'true' ? 0 : -1;
    if (tab.tabIndex === 0) {
     const panel = document.getElementById(tab.getAttribute('aria-controls'));
     if (panel) panel.setAttribute('aria-labelledby', tab.id);
    }
   });
  });
  refreshMedia(); queueLayout();
 }
 document.addEventListener('keydown', event => {
  if (!root) return;
  const toggle = root.querySelector('button[aria-controls="landing-mobile-menu"]');
  if (event.key === 'Escape' && toggle?.getAttribute('aria-expanded') === 'true') {
   toggle.click(); toggle.focus(); event.preventDefault(); return;
  }
  const tab = event.target.closest?.('[role="tab"]');
  if (!tab || !root.contains(tab) || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
  const tabs = [...tab.closest('[role="tablist"]').querySelectorAll('[role="tab"]')];
  const direction = root.dir === 'rtl' ? -1 : 1;
  let index = tabs.indexOf(tab);
  if (event.key === 'Home') index = 0;
  else if (event.key === 'End') index = tabs.length - 1;
  else index = (index + (event.key === 'ArrowRight' ? direction : -direction) + tabs.length) % tabs.length;
  event.preventDefault(); tabs[index].click(); tabs[index].focus(); requestAnimationFrame(bind);
 });
 document.addEventListener('click', event => {
  const anchor = event.target.closest?.('a[href]');
  if (!root || !anchor || !root.contains(anchor) || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
  const url = new URL(anchor.href, location.href);
  if (url.origin !== location.origin || !['/','/landing','/landing/'].includes(url.pathname) || !url.hash) return;
  const target = document.getElementById(decodeURIComponent(url.hash.slice(1)));
  if (!target) return;
  event.preventDefault(); history.replaceState(null, '', location.pathname + location.search + url.hash);
  target.scrollIntoView({ behavior: 'auto', block: 'start' });
 });
 document.addEventListener('visibilitychange', refreshMedia);
 motion.addEventListener('change', refreshMedia);
 window.addEventListener('resize', queueLayout, { passive: true });
 new MutationObserver(() => requestAnimationFrame(bind)).observe(document.documentElement, { childList: true, subtree: true });
 if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, { once: true });
 else bind();
})();
