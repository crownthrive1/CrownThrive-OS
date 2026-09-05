(() => {
  const CANONICAL_SHELL = '/command-v3.html';
  const MARKETPLACE_LINK = '<a href="/store" data-marketplace-link><b>10</b>Marketplace</a>';
  const ENHANCEMENT_SCRIPT = '<script src="/command-enhancements.js" defer></script>';

  function showFailure(error) {
    const status = document.querySelector('#command-loader-status');
    if (status) status.textContent = `Command shell readback failed: ${String(error?.message || error)}`;
    const link = document.querySelector('#command-loader-direct');
    if (link) link.hidden = false;
  }

  async function load() {
    const response = await fetch(CANONICAL_SHELL, {
      cache: 'no-store',
      headers: { Accept: 'text/html' },
    });
    if (!response.ok) throw new Error(`command_shell_${response.status}`);

    let html = await response.text();
    if (!html.includes('data-marketplace-link')) {
      html = html.replace('</nav>', `${MARKETPLACE_LINK}</nav>`);
    }
    if (!html.includes('/command-enhancements.js')) {
      html = html.replace('</body>', `${ENHANCEMENT_SCRIPT}</body>`);
    }

    document.open();
    document.write(html);
    document.close();
  }

  load().catch(showFailure);
})();
