import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';

test('browser display rejects malformed timestamps instead of normalizing them', async () => {
  const source = await readFile(new URL('../storage-command.js', import.meta.url), 'utf8');

  async function render(lastRunAt) {
    const created = [];
    class Element {
      constructor(tagName) {
        this.tagName = tagName;
        this.children = [];
        this.dataset = {};
        this.attributes = {};
        this.listeners = {};
        this.textContent = '';
        created.push(this);
      }
      append(...items) { this.children.push(...items); }
      appendChild(item) { this.children.push(item); return item; }
      replaceChildren(...items) { this.children = items; }
      setAttribute(name, value) { this.attributes[name] = String(value); }
      addEventListener(name, callback) { this.listeners[name] = callback; }
      querySelector() { return null; }
      click() {}
    }

    const pageNames = ['overview', 'dail', 'infrastructure', 'commerce', 'evidence', 'integrations'];
    const pageRoots = new Map(pageNames.map((name) => [name, new Element('section')]));
    const nav = new Element('nav');
    const fresh = new Element('div');
    const refresh = new Element('button');
    const document = {
      hidden: false,
      documentElement: { dataset: {} },
      createElement: (tag) => new Element(tag),
      createTextNode: (value) => { const item = new Element('#text'); item.textContent = String(value); return item; },
      querySelector(selector) {
        if (selector.startsWith('[data-page="') && selector.endsWith('"]')) {
          const pageName = selector.slice(12, -2);
          return pageRoots.get(pageName) ?? null;
        }
        if (selector === '#nav') return nav;
        if (selector === '#fresh') return fresh;
        if (selector === '#refresh') return refresh;
        return null;
      },
      addEventListener() {},
    };
    const payload = {
      schema: 'ct.command.storage-status.v1',
      status: 'OBSERVED',
      retrieved_at: new Date().toISOString(),
      archive: {
        total_archived_events: 510000,
        section_no: 1,
        section_events: 510000,
        section_target_events: 1000000,
        section_progress_percent: 51,
        sealed_sections_in_status: 0,
        state: 'COPYING',
        next_shard_no: 71,
        last_run_at: lastRunAt,
        last_run_events_copied: 15000,
        source_pruning_enabled: false,
      },
      commerce: { sales_enabled: false, activation_state: 'UNKNOWN', offers: [] },
      custody: { consumers: [], buckets: [], registered_bytes: 0, external_delivery_enabled_count: 0 },
      controls: { write_admission_state: 'UNKNOWN', balancer_mode: 'UNKNOWN', pressure: null },
    };

    runInNewContext(source, {
      document,
      location: { hash: '' },
      window: { addEventListener() {} },
      MutationObserver: class { observe() {} disconnect() {} },
      requestAnimationFrame() {},
      fetch: async () => ({ ok: true, json: async () => payload }),
      AbortController,
      Date,
      Intl,
      setTimeout: () => 1,
      clearTimeout() {},
      URL,
      Blob,
    });
    await new Promise((resolve) => setImmediate(resolve));
    return created.filter((element) => element.textContent).map((element) => element.textContent);
  }

  for (const malformed of ['2026-09-31T21:00:00Z', '2026-09-16T21:00:00']) {
    const rendered = await render(malformed);
    assert.ok(
      rendered.filter((text) => text === 'Last archive work: Not observed. Last copied batch: 15,000 events.').length >= 2,
      `malformed timestamp was displayed: ${malformed}`,
    );
  }

  const valid = await render('2026-09-16T21:00:00.000Z');
  assert.ok(valid.some((text) => text.startsWith('Last archive work: ') && !text.includes('Not observed')));
});
