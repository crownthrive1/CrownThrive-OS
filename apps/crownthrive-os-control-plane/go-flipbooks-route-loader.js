(() => {
  'use strict';

  const shellPath = '/go-flipbooks.html';

  function report(error) {
    const status = document.querySelector('[data-route-loader-status]');
    const direct = document.querySelector('[data-route-loader-direct]');
    if (status) status.textContent = `The Go Flipbooks shell could not be loaded: ${String(error?.message || error)}`;
    if (direct) direct.hidden = false;
  }

  async function load() {
    const response = await fetch(shellPath, {
      cache: 'no-store',
      headers: { Accept: 'text/html' }
    });
    if (!response.ok) throw new Error(`shell_${response.status}`);
    const html = await response.text();
    if (!html.includes('data-gf-lane="overview"') || !html.includes('/go-flipbooks.js')) {
      throw new Error('shell_contract_invalid');
    }
    document.open();
    document.write(html);
    document.close();
  }

  load().catch(report);
})();
