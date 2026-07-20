(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const VIEW_KEY = 'prismora.v4.exploreView';
  const VIEWS = ['understand', 'compare', 'baselines', 'interventions'];
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const lang = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';

  let activeView = VIEWS.includes(localStorage.getItem(VIEW_KEY)) ? localStorage.getItem(VIEW_KEY) : 'understand';
  let scheduled = false;
  let compareRequest = 0;

  const copy = {
    fr: {
      interventionsNav: 'Interventions',
      compareTitle: 'Comparaison A/B',
      compareSubtitle: 'Comparer deux artifacts vérifiés sans modifier les données chargées.',
      compareLoading: 'Chargement de la paire de démonstration vérifiée…',
      compareUnavailable: 'Un second artifact compatible est nécessaire pour une comparaison A/B. Le run chargé reste intact.',
      compareError: 'La comparaison vérifiée n’a pas pu être produite.',
      demoPair: 'Paire A vérifiée · contrôle ↔ variation',
      fullComparison: 'Ouvrir la comparaison A/B complète',
      why: 'Pourquoi cette phrase ?',
      rule: 'Règle', evidence: 'Preuves',
      referencesTitle: 'Références',
      referencesSubtitle: 'Provenance, couverture et limites de l’artifact actuellement chargé.',
      interventionsTitle: 'Interventions',
      interventionsSubtitle: 'Déclarations présentes dans la requête, sans déduire un effet causal.',
      noArtifact: 'Chargez une démo ou un export local pour ouvrir cette sous-vue.',
      run: 'Exécution', model: 'Modèle', source: 'Source', file: 'Fichier source',
      lenses: 'Lentilles disponibles', layers: 'Couches capturées', coverage: 'Couverture',
      synthetic: 'Statut', syntheticYes: 'Démonstration synthétique', syntheticNo: 'Artifact mesuré',
      noIntervention: 'Aucune intervention n’est déclarée dans cet artifact.',
      operation: 'Opération', declaredLayers: 'Couches déclarées', strength: 'Force',
      steerTokens: 'Tokens dirigés', swapToken: 'Token de remplacement', ablation: 'Ablation',
      yes: 'oui', no: 'non', unavailable: 'non disponible',
      causalGuard: 'Une intervention déclarée et une divergence mesurée ne constituent pas, à elles seules, une preuve causale.',
      openBaselines: 'Ouvrir le laboratoire de référence',
      openCausal: 'Ouvrir le laboratoire causal',
      openRuns: 'Ouvrir les exécutions et données brutes',
    },
    en: {
      interventionsNav: 'Interventions',
      compareTitle: 'A/B comparison',
      compareSubtitle: 'Compare two verified artifacts without modifying the loaded data.',
      compareLoading: 'Loading the verified demo pair…',
      compareUnavailable: 'A second compatible artifact is required for an A/B comparison. The loaded run remains unchanged.',
      compareError: 'The verified comparison could not be produced.',
      demoPair: 'Verified Pair A · control ↔ shift',
      fullComparison: 'Open the complete A/B comparison',
      why: 'Why this sentence?',
      rule: 'Rule', evidence: 'Evidence',
      referencesTitle: 'References',
      referencesSubtitle: 'Provenance, coverage and limitations of the currently loaded artifact.',
      interventionsTitle: 'Interventions',
      interventionsSubtitle: 'Declarations present in the request, without inferring a causal effect.',
      noArtifact: 'Load a demo or local export to open this subview.',
      run: 'Run', model: 'Model', source: 'Source', file: 'Source file',
      lenses: 'Available lenses', layers: 'Captured layers', coverage: 'Coverage',
      synthetic: 'Status', syntheticYes: 'Synthetic demonstration', syntheticNo: 'Measured artifact',
      noIntervention: 'No intervention is declared in this artifact.',
      operation: 'Operation', declaredLayers: 'Declared layers', strength: 'Strength',
      steerTokens: 'Steered tokens', swapToken: 'Swap token', ablation: 'Ablation',
      yes: 'yes', no: 'no', unavailable: 'unavailable',
      causalGuard: 'A declared intervention and a measured divergence do not, by themselves, establish causal proof.',
      openBaselines: 'Open Baseline Lab',
      openCausal: 'Open Causal Lab',
      openRuns: 'Open runs and exact raw data',
    },
  };

  const t = (key) => copy[lang()][key] ?? key;

  function sessionPayload() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null'); }
    catch { return null; }
  }

  function artifact() {
    const value = sessionPayload()?.artifact;
    return value?.schema === 'prismora.run/v2' ? value : null;
  }

  function currentLens(value) {
    const lenses = Object.keys(value?.result?.meta?.layers_by_type || {});
    const selected = $('#lens-select')?.value;
    if (selected && lenses.includes(selected)) return selected;
    return lenses.includes('JACOBIAN_LENS') ? 'JACOBIAN_LENS' : lenses[0] || 'JACOBIAN_LENS';
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { 'content-type': 'application/json', ...(options.headers || {}) },
    });
    const text = await response.text();
    let payload;
    try { payload = text ? JSON.parse(text) : null; } catch { payload = text; }
    if (!response.ok) throw new Error(payload?.detail?.message || payload?.detail || payload?.message || text || String(response.status));
    return payload;
  }

  function makePanel(id) {
    let panel = $(`#${id}`);
    if (!panel) {
      panel = document.createElement('section');
      panel.id = id;
      panel.className = 'explorer-subview card';
    }
    return panel;
  }

  function ensureStructure() {
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
      host.append(understand);
    }

    for (const id of ['explorer-compare-view', 'explorer-references-view', 'explorer-interventions-view']) {
      const panel = makePanel(id);
      if (panel.parentElement !== host) host.append(panel);
    }

    adoptInstrumentPanels(understand);
    return host;
  }

  function adoptInstrumentPanels(understand) {
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
      const before = nav.querySelector('[data-nav="models"]');
      nav.insertBefore(button, before || null);
    }
    button.textContent = t('interventionsNav');
  }

  function fact(label, value) {
    const row = document.createElement('div');
    row.className = 'explorer-fact';
    const term = document.createElement('span');
    term.textContent = label;
    const data = document.createElement('strong');
    data.textContent = value ?? t('unavailable');
    row.append(term, data);
    return row;
  }

  function heading(panel, titleText, subtitleText) {
    panel.replaceChildren();
    const title = document.createElement('h2');
    title.textContent = titleText;
    const subtitle = document.createElement('p');
    subtitle.className = 'explorer-subview-subtitle';
    subtitle.textContent = subtitleText;
    panel.append(title, subtitle);
  }

  function addActions(panel, actions) {
    const row = document.createElement('div');
    row.className = 'explorer-subview-actions';
    for (const [label, href] of actions) {
      const link = document.createElement('a');
      link.href = href;
      link.textContent = label;
      row.append(link);
    }
    panel.append(row);
  }

  function renderReferences() {
    const panel = $('#explorer-references-view');
    if (!panel) return;
    heading(panel, t('referencesTitle'), t('referencesSubtitle'));
    const value = artifact();
    if (!value) {
      const empty = document.createElement('p');
      empty.textContent = t('noArtifact');
      panel.append(empty);
      return;
    }
    const layersByType = value?.result?.meta?.layers_by_type || {};
    const allLayers = [...new Set(Object.values(layersByType).flat().filter(Number.isFinite))].sort((a, b) => a - b);
    const lenses = Object.keys(layersByType);
    const coverage = value.coverage || {};
    const source = value?.provenance?.backend || value?.request?.backend || t('unavailable');
    const file = value?.provenance?.original_filename || value?.provenance?.source || t('unavailable');
    const synthetic = Boolean(value?.result?.meta?.mock || value?.request?.factors?.demo || sessionPayload()?.sourceType === 'demo');
    const grid = document.createElement('div');
    grid.className = 'explorer-fact-grid';
    grid.append(
      fact(t('run'), value.run_id || 'local'),
      fact(t('model'), value?.request?.model?.model_id || t('unavailable')),
      fact(t('source'), source),
      fact(t('file'), file),
      fact(t('lenses'), lenses.join(', ') || t('unavailable')),
      fact(t('layers'), allLayers.length ? `${allLayers.length} · ${allLayers[0]}–${allLayers.at(-1)}` : t('unavailable')),
      fact(t('coverage'), coverage.status || t('unavailable')),
      fact(t('synthetic'), synthetic ? t('syntheticYes') : t('syntheticNo')),
    );
    panel.append(grid);
    addActions(panel, [[t('openBaselines'), '/#baseline'], [t('openRuns'), '/#runs']]);
  }

  function interventionData(value) {
    const request = value?.request || {};
    const explicit = request.intervention || {};
    const layers = [];
    if (Number.isInteger(explicit.layer)) layers.push(explicit.layer);
    if (Array.isArray(explicit.layers)) layers.push(...explicit.layers.filter(Number.isInteger));
    if (Array.isArray(request.steerLayers)) layers.push(...request.steerLayers.filter(Number.isInteger));
    const steerTokens = explicit.steerTokens || request.steerTokens || [];
    const swapToken = explicit.swapToken || request.swapToken || null;
    const ablation = explicit.steerAblate ?? request.steerAblate ?? false;
    const strength = explicit.steerStrength ?? request.steerStrength ?? explicit.strength ?? null;
    const declared = Object.keys(explicit).length || layers.length || steerTokens.length || swapToken || ablation || strength !== null;
    return { declared: Boolean(declared), layers: [...new Set(layers)].sort((a, b) => a - b), steerTokens, swapToken, ablation, strength };
  }

  function tokenLabel(value) {
    if (!value) return t('unavailable');
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map(tokenLabel).join(', ');
    return value.token || value.name || JSON.stringify(value);
  }

  function renderInterventions() {
    const panel = $('#explorer-interventions-view');
    if (!panel) return;
    heading(panel, t('interventionsTitle'), t('interventionsSubtitle'));
    const value = artifact();
    if (!value) {
      const empty = document.createElement('p');
      empty.textContent = t('noArtifact');
      panel.append(empty);
      return;
    }
    const data = interventionData(value);
    if (!data.declared) {
      const empty = document.createElement('p');
      empty.className = 'explorer-subview-empty';
      empty.textContent = t('noIntervention');
      panel.append(empty);
    } else {
      const operations = [];
      if (data.steerTokens.length) operations.push('steer');
      if (data.swapToken) operations.push('swap');
      if (data.ablation) operations.push('ablation');
      const grid = document.createElement('div');
      grid.className = 'explorer-fact-grid';
      grid.append(
        fact(t('operation'), operations.join(' + ') || t('unavailable')),
        fact(t('declaredLayers'), data.layers.join(', ') || t('unavailable')),
        fact(t('strength'), data.strength === null ? t('unavailable') : String(data.strength)),
        fact(t('steerTokens'), tokenLabel(data.steerTokens)),
        fact(t('swapToken'), tokenLabel(data.swapToken)),
        fact(t('ablation'), data.ablation ? t('yes') : t('no')),
      );
      panel.append(grid);
    }
    const guard = document.createElement('p');
    guard.className = 'explorer-causal-guard';
    guard.textContent = t('causalGuard');
    panel.append(guard);
    addActions(panel, [[t('openCausal'), '/#causal']]);
  }

  function sentenceCard(sentence) {
    const article = document.createElement('article');
    article.className = `explorer-sentence ${sentence.severity || 'info'}`;
    const text = document.createElement('p');
    text.textContent = sentence.text || '';
    article.append(text);
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = t('why');
    const rule = document.createElement('div');
    rule.className = 'explorer-rule';
    rule.textContent = `${t('rule')} · ${sentence.rule_id || '—'} · ${sentence.template_id || '—'}`;
    const evidence = document.createElement('pre');
    evidence.textContent = `${t('evidence')}\n${JSON.stringify(sentence.evidence || [], null, 2)}`;
    details.append(summary, rule, evidence);
    article.append(details);
    return article;
  }

  async function renderComparison() {
    const panel = $('#explorer-compare-view');
    if (!panel) return;
    heading(panel, t('compareTitle'), t('compareSubtitle'));
    const value = artifact();
    const isDemoPair = value?.run_id?.startsWith('demo-pair-a-') || sessionPayload()?.sourceType === 'demo';
    if (!value || !isDemoPair) {
      const empty = document.createElement('p');
      empty.className = 'explorer-subview-empty';
      empty.textContent = value ? t('compareUnavailable') : t('noArtifact');
      panel.append(empty);
      addActions(panel, [[t('fullComparison'), '/#visualizer']]);
      return;
    }

    const loading = document.createElement('p');
    loading.className = 'explorer-subview-empty';
    loading.textContent = t('compareLoading');
    panel.append(loading);
    const requestId = ++compareRequest;
    const requestedLocale = lang();
    try {
      const payload = await api('/api/demo/build-week/understand/compare', {
        method: 'POST',
        body: JSON.stringify({
          run_a: 'demo-pair-a-control',
          run_b: 'demo-pair-a-shift',
          lens: currentLens(value),
          scope: 'all',
          locale: requestedLocale,
          probability_abs_tolerance: 0,
        }),
      });
      if (requestId !== compareRequest || requestedLocale !== lang() || activeView !== 'compare') return;
      heading(panel, t('compareTitle'), t('compareSubtitle'));
      const badge = document.createElement('div');
      badge.className = 'explorer-pair-badge';
      badge.textContent = t('demoPair');
      panel.append(badge);
      const list = document.createElement('div');
      list.className = 'explorer-sentence-list';
      (payload.sentences || []).forEach((sentence) => list.append(sentenceCard(sentence)));
      panel.append(list);
      addActions(panel, [[t('fullComparison'), '/#visualizer']]);
    } catch (error) {
      if (requestId !== compareRequest) return;
      heading(panel, t('compareTitle'), t('compareSubtitle'));
      const failure = document.createElement('p');
      failure.className = 'explorer-subview-error';
      failure.textContent = `${t('compareError')} ${error.message}`;
      panel.append(failure);
    }
  }

  function syncVisibility() {
    const host = ensureStructure();
    if (!host) return;
    adoptInstrumentPanels($('#explorer-understand-view'));
    const map = {
      understand: $('#explorer-understand-view'),
      compare: $('#explorer-compare-view'),
      baselines: $('#explorer-references-view'),
      interventions: $('#explorer-interventions-view'),
    };
    Object.entries(map).forEach(([view, node]) => { if (node) node.hidden = view !== activeView; });
    $$('.explorer-overview-cards [data-explorer-view]').forEach((card) => card.classList.toggle('active', card.dataset.explorerView === activeView));
    $$('#sidebar-nav [data-nav]').forEach((button) => button.classList.toggle('active', button.dataset.nav === activeView));
  }

  function renderActive() {
    ensureInterventionsNav();
    syncVisibility();
    if (activeView === 'compare') renderComparison();
    else if (activeView === 'baselines') renderReferences();
    else if (activeView === 'interventions') renderInterventions();
  }

  function scheduleRender() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      scheduled = false;
      renderActive();
    }));
  }

  function activate(view) {
    if (!VIEWS.includes(view)) view = 'understand';
    activeView = view;
    localStorage.setItem(VIEW_KEY, view);
    compareRequest += 1;
    renderActive();
  }

  document.addEventListener('click', (event) => {
    const nav = event.target.closest?.('[data-nav]');
    if (nav && VIEWS.includes(nav.dataset.nav)) {
      requestAnimationFrame(() => activate(nav.dataset.nav));
      return;
    }
    const card = event.target.closest?.('[data-explorer-view]');
    if (card) {
      activate(card.dataset.explorerView);
      return;
    }
    if (event.target.closest?.('#lvl-explore, #details-button')) requestAnimationFrame(() => activate('understand'));
  });

  document.addEventListener('keydown', (event) => {
    const card = event.target.closest?.('[data-explorer-view]');
    if (!card || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    activate(card.dataset.explorerView);
  });

  window.addEventListener('DOMContentLoaded', () => {
    ensureStructure();
    ensureInterventionsNav();
    const activeNav = $('#sidebar-nav .nav-button.active')?.dataset.nav;
    if (VIEWS.includes(activeNav)) activeView = activeNav;

    const screen = $('.screen[data-screen="explore"]');
    if (screen) {
      const observer = new MutationObserver(() => scheduleRender());
      observer.observe(screen, { childList: true });
    }
    for (const selector of ['#tokens', '#layer-rail', '[data-shared-artifact]']) {
      const node = $(selector);
      if (!node) continue;
      const observer = new MutationObserver(() => scheduleRender());
      observer.observe(node, { childList: true, subtree: true, characterData: true });
    }
    const languageObserver = new MutationObserver(() => scheduleRender());
    languageObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    scheduleRender();
  });
})();
