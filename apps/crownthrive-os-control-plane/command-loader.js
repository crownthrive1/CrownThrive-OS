(() => {
  'use strict';

  const CANONICAL_SHELL = '/command-v3.html';
  const VERSION = '4.0.0';
  const RELEASE = 'ct.command.governed-estate.v4.0.0.20260910';
  const MARKETPLACE_LINK = '<a href="/store" data-marketplace-link><b>81</b>Marketplace</a>';
  const ESTATE_LINK = '<a href="/estate" data-estate-link><b>79</b>Estate</a>';
  const RELEASE_META = `<meta name="ct-command-release" content="${RELEASE}">`;
  const ENHANCEMENT_STYLE = '<link rel="stylesheet" href="/command-enhancements.css" data-command-extension-style>';
  const ESTATE_STYLE = '<link rel="stylesheet" href="/command-estate.css" data-command-estate-style>';
  const ENHANCEMENT_SCRIPT = '<script src="/command-enhancements.js" defer data-command-extension-script></script>';
  const ESTATE_SCRIPT = '<script src="/command-estate.js" defer data-command-estate-script></script>';

  function showFailure(error) {
    const status = document.querySelector('#command-loader-status');
    if (status) status.textContent = `Command shell readback failed: ${String(error?.message || error)}`;
    const link = document.querySelector('#command-loader-direct');
    if (link) link.hidden = false;
    document.documentElement.dataset.commandLoaderState = 'failed';
  }

  function injectRelease(html) {
    let output = html.replace(
      /data-command-version="[^"]+"/i,
      `data-command-version="${VERSION}" data-command-extension="executive-pulse governed-estate" data-command-release="${RELEASE}"`,
    );

    if (!output.includes('name="ct-command-release"')) {
      output = output.replace('</head>', `${RELEASE_META}${ENHANCEMENT_STYLE}${ESTATE_STYLE}</head>`);
    } else {
      if (!output.includes('data-command-extension-style')) output = output.replace('</head>', `${ENHANCEMENT_STYLE}</head>`);
      if (!output.includes('data-command-estate-style')) output = output.replace('</head>', `${ESTATE_STYLE}</head>`);
    }

    if (!output.includes('data-estate-link')) output = output.replace('</nav>', `${ESTATE_LINK}</nav>`);
    if (!output.includes('data-marketplace-link')) output = output.replace('</nav>', `${MARKETPLACE_LINK}</nav>`);
    if (!output.includes('data-command-extension-script')) output = output.replace('</body>', `${ENHANCEMENT_SCRIPT}</body>`);
    if (!output.includes('data-command-estate-script')) output = output.replace('</body>', `${ESTATE_SCRIPT}</body>`);
    return output;
  }

  async function load() {
    document.documentElement.dataset.commandLoaderState = 'reading';
    const response = await fetch(CANONICAL_SHELL, {
      cache: 'no-store',
      credentials: 'same-origin',
      headers: { Accept: 'text/html' },
    });
    if (!response.ok) throw new Error(`command_shell_${response.status}`);

    const shell = await response.text();
    if (!shell.includes('CrownThrive Command') || !shell.includes('CHLOM Wallet') || !shell.includes('Three DAIL')) {
      throw new Error('command_shell_contract_invalid');
    }

    const html = injectRelease(shell);
    document.open();
    document.write(html);
    document.close();
  }

  load().catch(showFailure);
})();
