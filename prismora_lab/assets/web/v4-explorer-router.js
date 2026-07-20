(() => {
  'use strict';

  const VIEW_KEY = 'prismora.v4.exploreView';
  const SESSION_KEY = 'prismora.v4.session';
  const VIEWS = ['understand', 'compare', 'baselines', 'interventions'];
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const lang = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let activeView = VIEWS.includes(localStorage.getItem(VIEW_KEY)) ? localStorage.getItem(VIEW_KEY) : 'understand';
  let scheduled = false;
  let runtimeArtifact = null;
  let runtimeSourceType = null;

  const copy = { fr: { interventions: 'Interventions' }, en: { interventions: 'Interventions' } };
  const isArtifact = (value) => value?.schema === 'prismora.run/v2';

  function storedSession() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null'); }
    catch { return null; }
  }

  function currentSession() {
    const saved = storedSession() || {};
    if (isArtifact(saved.artifact)) runtimeArtifact = saved.artifact;
    if (saved.sourceType) runtimeSourceType = saved.sourceType;
    return { ...saved, artifact: runtimeArtifact || saved.artifact || null, sourceType: runtimeSourceType || saved.sourceType || null };
  }

  function normalizeNative(value, filename) {
    if (!(value?.version === 1 && ['chat', 'completion'].includes(value?.kind) && Array.isArray(value?.tokens))) return null;
    const messages = Array.isArray(value.messages) ? value.messages : [];
    const last = (role) => [...messages].reverse().find((message) => message?.role === role)?.content || '';
    const layersByType = value.meta?.layers_by_type || {};
    return {
      schema: 'prismora.run/v2',
      run_id: `neuronpedia-${String(value.modelId || 'model').replace(/[^a-zA-Z0-9._-]+/g, '-')}-${String(value.exportedAt || filename).replace(/[^a-zA-Z0-9._-]+/g, '-')}`,
      request: { backend: 'neuronpedia_export', prompt: value.kind === 'completion' ? String(value.prompt || '') : last('user'), messages, model: { model_id: value.modelId || value.meta?.model || 'unknown-model' } },
      result: { tokens: value.tokens, meta: { ...value.meta, layers_by_type: layersByType }, done: { completion: value.kind === 'chat' ? last('assistant') : value.tokens.filter((token) => token?.is_generated).map((token) => token?.token || '').join('') } },
      coverage: { captured_layers: layersByType.JACOBIAN_LENS || [], lens_types: Object.keys(layersByType) },
      provenance: { backend: 'neuronpedia_export', source: 'local-file', original_filename: filename },
    };
  }

  function ensureHost() {
    const screen = $('.screen[data-screen="explore"]');
    if (!screen) return null;
    const cards = screen.querySelector(':scope > .cards');
    if (cards) {
      cards.classList.add('explorer-overview-cards');
      [...cards.children].forEach((card, index) => {
        const view = VIEWS[index];
        if (!view) return;
        card.dataset.explorerView = view;
        card.setAttribute('role', 'button');
        card.tabIndex = 0;
      });
    }
    let host = $('#explorer-subview-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'explorer-subview-host';
      host.className = 'explorer-subview-host';
      screen.insertBefore(host, $('#legacy-explore') || null);
    }
    let understand = $('#explorer-understand-view');
    if (!understand) {
      understand = document.createElement('div');
      understand.id = 'explorer-understand-view';
      understand.className = 'explorer-subview explorer-subview-stack';
      understand.dataset.explorerPanel = 'understand';
      host.append(understand);
    }
    adoptExistingPanels(understand);
    return host;
  }

  function adoptExistingPanels(understand) {
    for (const id of ['understand-panel', 'lens-comparison-panel']) {
      const panel = $(`#${id}`);
      if (panel && panel.parentElement !== understand) understand.append(panel);
    }
  }

  function ensureInterventionsNav() {
    const nav = $('#sidebar-nav');
    if (!nav || !$('#lvl-explore')?.classList.contains('active')) return;
    let button = nav.querySelector('[data-nav="interventions"]');
    if (!button) {
      button = document.createElement('button');
      button.type = 'button';
      button.className = 'nav-button';
      button.dataset.nav = 'interventions';
      nav.insertBefore(button, nav.querySelector('[data-nav="models"]') || null);
    }
    button.textContent = copy[lang()].interventions;
  }

  function sync() {
    const host = ensureHost();
    if (!host) return;
    ensureInterventionsNav();
    adoptExistingPanels($('#explorer-understand-view'));
    $$('[data-explorer-panel]').forEach((panel) => { panel.hidden = panel.dataset.explorerPanel !== activeView; });
    $$('.explorer-overview-cards [data-explorer-view]').forEach((card) => card.classList.toggle('active', card.dataset.explorerView === activeView));
    $$('#sidebar-nav [data-nav]').forEach((button) => button.classList.toggle('active', button.dataset.nav === activeView));
    document.dispatchEvent(new CustomEvent('prismora:explorer-view', { detail: { view: activeView, locale: lang(), session: currentSession() } }));
  }

  function activate(view) {
    activeView = VIEWS.includes(view) ? view : 'understand';
    localStorage.setItem(VIEW_KEY, activeView);
    sync();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => { scheduled = false; sync(); }));
  }

  function boot() {
    const saved = storedSession();
    if (isArtifact(saved?.artifact)) { runtimeArtifact = saved.artifact; runtimeSourceType = saved.sourceType || null; }
    ensureHost();
    const screen = $('.screen[data-screen="explore"]');
    if (screen) new MutationObserver(schedule).observe(screen, { childList: true });
    for (const selector of ['#tokens', '#layer-rail', '[data-shared-artifact]']) {
      const node = $(selector);
      if (node) new MutationObserver(schedule).observe(node, { childList: true, subtree: true, characterData: true });
    }
    new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    schedule();
  }

  document.addEventListener('prismora:explorer-refresh', schedule);
  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.id !== 'import-form' || event.submitter?.value === 'cancel') return;
    for (const file of [...($('#import-files')?.files || [])]) {
      if (!file.name.toLowerCase().endsWith('.json')) continue;
      try {
        const value = JSON.parse(await file.text());
        const found = isArtifact(value) ? value : value?.artifact || value?.run || value?.data || normalizeNative(value, file.name);
        if (isArtifact(found)) { runtimeArtifact = found; runtimeSourceType = 'import'; schedule(); return; }
      } catch { /* The normal import path owns user-facing errors. */ }
    }
  });
  document.addEventListener('click', (event) => {
    const nav = event.target.closest?.('[data-nav]');
    if (nav && VIEWS.includes(nav.dataset.nav)) { requestAnimationFrame(() => activate(nav.dataset.nav)); return; }
    const card = event.target.closest?.('[data-explorer-view]');
    if (card) { activate(card.dataset.explorerView); return; }
    if (event.target.closest?.('#lvl-explore, #details-button')) requestAnimationFrame(() => activate('understand'));
  });
  document.addEventListener('keydown', (event) => {
    const card = event.target.closest?.('[data-explorer-view]');
    if (!card || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault(); activate(card.dataset.explorerView);
  });

  if (document.readyState === 'loading') window.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
