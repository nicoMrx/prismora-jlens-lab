(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const VIEW_KEY = 'prismora.v4.exploreView';
  const VIEWS = ['understand', 'compare', 'baselines', 'interventions'];
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';

  let activeView = VIEWS.includes(localStorage.getItem(VIEW_KEY)) ? localStorage.getItem(VIEW_KEY) : 'understand';
  let currentArtifact = null;
  let scheduled = false;
  let compareSequence = 0;

  const copy = {
    fr: {
      interventionsNav: 'Interventions', compareTitle: 'Comparaison A/B',
      compareSubtitle: 'Comparer deux artifacts vérifiés sans modifier les données chargées.',
      compareLoading: 'Chargement de la paire de démonstration vérifiée…',
      compareUnavailable: 'Un second artifact compatible est nécessaire. Le run chargé reste intact et aucune comparaison n’est inventée.',
      compareError: 'La comparaison vérifiée n’a pas pu être produite.',
      demoPair: 'Paire A vérifiée · contrôle ↔ variation', fullComparison: 'Ouvrir la comparaison A/B complète',
      why: 'Pourquoi cette phrase ?', rule: 'Règle', evidence: 'Preuves',
      referencesTitle: 'Références', referencesSubtitle: 'Provenance, couverture et limites de l’artifact actuellement chargé.',
      interventionsTitle: 'Interventions', interventionsSubtitle: 'Déclarations présentes dans la requête, sans déduire un effet causal.',
      noArtifact: 'Chargez une démo ou un export local pour ouvrir cette sous-vue.',
      run: 'Exécution', model: 'Modèle', source: 'Source', sourceFile: 'Fichier source',
      lenses: 'Lentilles disponibles', layers: 'Couches capturées', coverage: 'Couverture', status: 'Statut',
      complete: 'complète', partial: 'partielle', unknown: 'inconnue',
      syntheticYes: 'Démonstration synthétique', syntheticNo: 'Artifact mesuré',
      noIntervention: 'Aucune intervention n’est déclarée dans cet artifact.',
      operation: 'Opération', declaredLayers: 'Couches déclarées', strength: 'Force',
      steerTokens: 'Tokens dirigés', swapToken: 'Token de remplacement', ablation: 'Ablation',
      yes: 'oui', no: 'non', unavailable: 'non disponible',
      causalGuard: 'Une intervention déclarée et une divergence mesurée ne constituent pas, à elles seules, une preuve causale.',
      openBaselines: 'Ouvrir le laboratoire de référence', openCausal: 'Ouvrir le laboratoire causal',
      openRuns: 'Ouvrir les exécutions et données brutes',
    },
    en: {
      interventionsNav: 'Interventions', compareTitle: 'A/B comparison',
      compareSubtitle: 'Compare two verified artifacts without modifying the loaded data.',
      compareLoading: 'Loading the verified demo pair…',
      compareUnavailable: 'A second compatible artifact is required. The loaded run remains intact and no comparison is invented.',
      compareError: 'The verified comparison could not be produced.',
      demoPair: 'Verified Pair A · control ↔ shift', fullComparison: 'Open the complete A/B comparison',
      why: 'Why this sentence?', rule: 'Rule', evidence: 'Evidence',
      referencesTitle: 'References', referencesSubtitle: 'Provenance, coverage and limitations of the currently loaded artifact.',
      interventionsTitle: 'Interventions', interventionsSubtitle: 'Declarations present in the request, without inferring a causal effect.',
      noArtifact: 'Load a demo or local export to open this subview.',
      run: 'Run', model: 'Model', source: 'Source', sourceFile: 'Source file',
      lenses: 'Available lenses', layers: 'Captured layers', coverage: 'Coverage', status: 'Status',
      complete: 'complete', partial: 'partial', unknown: 'unknown',
      syntheticYes: 'Synthetic demonstration', syntheticNo: 'Measured artifact',
      noIntervention: 'No intervention is declared in this artifact.',
      operation: 'Operation', declaredLayers: 'Declared layers', strength: 'Strength',
      steerTokens: 'Steered tokens', swapToken: 'Swap token', ablation: 'Ablation',
      yes: 'yes', no: 'no', unavailable: 'unavailable',
      causalGuard: 'A declared intervention and a measured divergence do not, by themselves, establish causal proof.',
      openBaselines: 'Open Baseline Lab', openCausal: 'Open Causal Lab',
      openRuns: 'Open runs and exact raw data',
    },
  };

  const t = (key) => copy[language()][key] ?? key;
  const isArtifact = (value) => value?.schema === 'prismora.run/v2';

  function sessionPayload() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null'); }
    catch { return null; }
  }

  function sessionArtifact() {
    const value = sessionPayload()?.artifact;
    return isArtifact(value) ? value : null;
  }

  function normalizeNative(value, filename) {
    if (!(value?.version === 1 && ['chat', 'completion'].includes(value?.kind) && Array.isArray(value?.tokens))) return null;
    const messages = Array.isArray(value.messages) ? value.messages : [];
    const last = (role) => [...messages].reverse().find((message) => message?.role === role)?.content || '';
    const layersByType = value.meta?.layers_by_type || {};
    return {
      schema: 'prismora.run/v2',
      run_id: `neuronpedia-${String(value.modelId || 'model').replace(/[^a-zA-Z0-9._-]+/g, '-')}-${String(value.exportedAt || filename).replace(/[^a-zA-Z0-9._-]+/g, '-')}`,
      request: {
        backend: 'neuronpedia_export',
        prompt: value.kind === 'completion' ? String(value.prompt || '') : last('user'),
        messages,
        model: { model_id: value.modelId || value.meta?.model || 'unknown-model' },
      },
      result: {
        tokens: value.tokens,
        meta: { ...value.meta, layers_by_type: layersByType },
        done: {
          completion: value.kind === 'chat'
            ? last('assistant')
            : value.tokens.filter((token) => token?.is_generated).map((token) => token?.token || '').join(''),
        },
      },
      coverage: { captured_layers: layersByType.JACOBIAN_LENS || [], lens_types: Object.keys(layersByType) },
      provenance: { backend: 'neuronpedia_export', source: 'local-file', original_filename: filename },
    };
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
      let panel = $(`#${id}`);
      if (!panel) {
        panel = document.createElement('section');
        panel.id = id;
        panel.className = 'explorer-subview card';
      }
      if (panel.parentElement !== host) host.append(panel);
    }
    adoptInstrumentPanels();
    ensureInterventionsNav();
    return host;
  }

  function adoptInstrumentPanels() {
    const understand = $('#explorer-understand-view');
    if (!understand) return;
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
    button.textContent = t('interventionsNav');
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

  function coverageText(value) {
    const status = value?.coverage?.status;
    return ['complete', 'partial', 'unknown'].includes(status) ? t(status) : status || t('unavailable');
  }

  function renderReferences() {
    const panel = $('#explorer-references-view');
    if (!panel) return;
    heading(panel, t('referencesTitle'), t('referencesSubtitle'));
    if (!currentArtifact) {
      const empty = document.createElement('p');
      empty.className = 'explorer-subview-empty';
      empty.textContent = t('noArtifact');
      panel.append(empty);
      return;
    }
    const layersByType = currentArtifact?.result?.meta?.layers_by_type || {};
    const allLayers = [...new Set(Object.values(layersByType).flat().filter(Number.isFinite))].sort((a, b) => a - b);
    const lenses = Object.keys(layersByType);
    const source = currentArtifact?.provenance?.backend || currentArtifact?.request?.backend || t('unavailable');
    const sourceFile = currentArtifact?.provenance?.original_filename || currentArtifact?.provenance?.source || t('unavailable');
    const synthetic = Boolean(currentArtifact?.result?.meta?.mock || currentArtifact?.request?.factors?.demo || sessionPayload()?.sourceType === 'demo');
    const grid = document.createElement('div');
    grid.className = 'explorer-fact-grid';
    grid.append(
      fact(t('run'), currentArtifact.run_id || 'local'),
      fact(t('model'), currentArtifact?.request?.model?.model_id || t('unavailable')),
      fact(t('source'), source),
      fact(t('sourceFile'), sourceFile),
      fact(t('lenses'), lenses.join(', ') || t('unavailable')),
      fact(t('layers'), allLayers.length ? `${allLayers.length} · ${allLayers[0]}–${allLayers.at(-1)}` : t('unavailable')),
      fact(t('coverage'), coverageText(currentArtifact)),
      fact(t('status'), synthetic ? t('syntheticYes') : t('syntheticNo')),
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
    return {
      declared: Boolean(Object.keys(explicit).length || layers.length || steerTokens.length || swapToken || ablation || strength !== null),
      layers: [...new Set(layers)].sort((a, b) => a - b), steerTokens, swapToken, ablation, strength,
    };
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
    if (!currentArtifact) {
      const empty = document.createElement('p');
      empty.className = 'explorer-subview-empty';
      empty.textContent = t('noArtifact');
      panel.append(empty);
      return;
    }
    const data = interventionData(currentArtifact);
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

  function renderSentence(sentence) {
    const card = document.createElement('article');
    card.className = `explorer-sentence ${sentence.severity || 'info'}`;
    const text = document.createElement('p');
    text.textContent = sentence.text || '';
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = t('why');
    const rule = document.createElement('div');
    rule.className = 'explorer-rule';
    rule.textContent = `${t('rule')} : ${sentence.rule_id || '—'} · ${sentence.template_id || '—'}`;
    const evidence = document.createElement('pre');
    evidence.textContent = `${t('evidence')}\n${JSON.stringify(sentence.evidence || [], null, 2)}`;
    details.append(summary, rule, evidence);
    card.append(text, details);
    return card;
  }

  async function renderComparison() {
    const panel = $('#explorer-compare-view');
    if (!panel) return;
    heading(panel, t('compareTitle'), t('compareSubtitle'));
    if (!['demo-pair-a-control', 'demo-pair-a-shift'].includes(currentArtifact?.run_id)) {
      const empty = document.createElement('p');
      empty.className = 'explorer-subview-empty';
      empty.textContent = t('compareUnavailable');
      panel.append(empty);
      addActions(panel, [[t('fullComparison'), '/#visualizer']]);
      return;
    }
    const sequence = ++compareSequence;
    const loading = document.createElement('p');
    loading.textContent = t('compareLoading');
    panel.append(loading);
    try {
      const result = await api('/api/demo/build-week/understand/compare', {
        method: 'POST',
        body: JSON.stringify({
          run_a: 'demo-pair-a-control', run_b: 'demo-pair-a-shift',
          lens: $('#lens-select')?.value || 'JACOBIAN_LENS', scope: 'all',
          locale: language(), probability_abs_tolerance: 0,
        }),
      });
      if (sequence !== compareSequence || activeView !== 'compare') return;
      heading(panel, t('compareTitle'), t('compareSubtitle'));
      const badge = document.createElement('span');
      badge.className = 'explorer-pair-badge';
      badge.textContent = t('demoPair');
      const list = document.createElement('div');
      list.className = 'explorer-sentence-list';
      list.replaceChildren(...(result.sentences || []).map(renderSentence));
      panel.append(badge, list);
      addActions(panel, [[t('fullComparison'), '/#visualizer']]);
    } catch (error) {
      if (sequence !== compareSequence) return;
      heading(panel, t('compareTitle'), t('compareSubtitle'));
      const message = document.createElement('p');
      message.className = 'explorer-subview-error';
      message.textContent = `${t('compareError')} ${error.message}`;
      panel.append(message);
    }
  }

  function activateView(view) {
    if (!VIEWS.includes(view)) view = 'understand';
    activeView = view;
    localStorage.setItem(VIEW_KEY, view);
    ensureStructure();
    $$('.explorer-overview-cards [data-explorer-view]').forEach((card) => {
      const active = card.dataset.explorerView === view;
      card.classList.toggle('active', active);
      card.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    $$('#sidebar-nav [data-nav]').forEach((button) => {
      if (VIEWS.includes(button.dataset.nav)) button.classList.toggle('active', button.dataset.nav === view);
    });
    const panels = {
      understand: '#explorer-understand-view', compare: '#explorer-compare-view',
      baselines: '#explorer-references-view', interventions: '#explorer-interventions-view',
    };
    Object.entries(panels).forEach(([name, selector]) => {
      const panel = $(selector);
      if (panel) panel.hidden = name !== view;
    });
    if (view === 'compare') renderComparison();
    if (view === 'baselines') renderReferences();
    if (view === 'interventions') renderInterventions();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      scheduled = false;
      currentArtifact = sessionArtifact() || currentArtifact;
      ensureStructure();
      activateView(activeView);
    }));
  }

  document.addEventListener('click', (event) => {
    const card = event.target.closest('[data-explorer-view]');
    if (card) return activateView(card.dataset.explorerView);
    const nav = event.target.closest('#sidebar-nav [data-nav]');
    if (nav && VIEWS.includes(nav.dataset.nav)) activateView(nav.dataset.nav);
    if (event.target.closest('[data-level="explore"], #details-button')) schedule();
  });

  document.addEventListener('keydown', (event) => {
    const card = event.target.closest?.('[data-explorer-view]');
    if (!card || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    activateView(card.dataset.explorerView);
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.id !== 'import-form' || event.submitter?.value === 'cancel') return;
    const file = $('#import-files')?.files?.[0];
    if (!file) return;
    try {
      const value = JSON.parse(await file.text());
      const candidate = isArtifact(value) ? value : value?.artifact || value?.run || value?.data || normalizeNative(value, file.name);
      if (isArtifact(candidate)) currentArtifact = candidate;
    } catch {
      // The ordinary import path owns visible errors.
    }
    schedule();
  });

  document.addEventListener('change', (event) => {
    if (event.target.closest('#lens-select, #language')) schedule();
  });

  window.addEventListener('DOMContentLoaded', () => {
    currentArtifact = sessionArtifact();
    ensureStructure();
    const explore = $('.screen[data-screen="explore"]');
    if (explore) {
      const panelObserver = new MutationObserver(() => {
        const understand = $('#explorer-understand-view');
        const waiting = ['understand-panel', 'lens-comparison-panel']
          .map((id) => $(`#${id}`))
          .some((panel) => panel && panel.parentElement !== understand);
        if (waiting) schedule();
      });
      panelObserver.observe(explore, { childList: true });
    }
    const shared = $('[data-shared-artifact]');
    if (shared) new MutationObserver(schedule).observe(shared, { childList: true, subtree: true, characterData: true });
    new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    activateView(activeView);
  });
})();