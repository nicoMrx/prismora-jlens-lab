(() => {
  'use strict';

  const VIEW_KEY = 'prismora.v4.controlView';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';

  const state = {
    legacy: null,
    preview: null,
    campaignId: null,
    status: null,
    busy: false,
    log: [],
  };

  const copy = {
    fr: {
      nav: 'Campagnes', title: 'Centre de campagnes',
      lede: 'Transformer un protocole en matrice vérifiable, passer les portes GO/NO-GO, puis exécuter seulement les runs manquants.',
      signature: 'Signature de recherche : NicoMrx', source: 'Source de campagne',
      choose: 'Choisir un campaign_01.json', demo: 'Charger Campagne 01', preview: 'Prévisualiser',
      noSource: 'Chargez le kit de démonstration ou sélectionnez un fichier JSON.',
      conditions: 'Conditions', repeats: 'Répétitions', runs: 'Runs planifiés', models: 'Modèles', storage: 'Raw estimé',
      modelBreakdown: 'Répartition par modèle', warnings: 'Portes et avertissements', conditionMatrix: 'Matrice des conditions',
      cond: 'Cond.', domain: 'Domaine', lang: 'Langue', model: 'Modèle', filter: 'Filtre', prompt: 'Prompt',
      yes: 'oui', no: 'non', showAll: 'Afficher les 29 conditions',
      save: 'Enregistrer dans Prismora', saved: 'Campagne enregistrée', lock: 'Verrouiller le protocole',
      preflight: 'Préflight · 1 run', nextBatch: 'Lancer le prochain lot', refresh: 'Actualiser',
      batch: 'Taille du lot', pace: 'Pause entre runs (s)', progress: 'Progression',
      draft: 'brouillon', locked: 'verrouillée', complete: 'terminée',
      completed: 'terminés', remaining: 'restants',
      loading: 'Chargement…', previewing: 'Compilation et validation des 29 conditions…',
      saving: 'Enregistrement des ExperimentSpec…', locking: 'Verrouillage des protocoles…',
      running: 'Exécution du lot…', noCampaign: 'Aucune campagne enregistrée.',
      openRuns: 'Ouvrir les exécutions historiques', error: 'Erreur',
    },
    en: {
      nav: 'Campaigns', title: 'Campaign Center',
      lede: 'Turn a protocol into a verifiable matrix, pass GO/NO-GO gates, then execute only missing runs.',
      signature: 'Research signature: NicoMrx', source: 'Campaign source',
      choose: 'Choose campaign_01.json', demo: 'Load Campaign 01', preview: 'Preview',
      noSource: 'Load the demo kit or select a JSON file.',
      conditions: 'Conditions', repeats: 'Repeats', runs: 'Planned runs', models: 'Models', storage: 'Estimated raw',
      modelBreakdown: 'Runs by model', warnings: 'Gates and warnings', conditionMatrix: 'Condition matrix',
      cond: 'Cond.', domain: 'Domain', lang: 'Language', model: 'Model', filter: 'Filter', prompt: 'Prompt',
      yes: 'yes', no: 'no', showAll: 'Show all 29 conditions',
      save: 'Save in Prismora', saved: 'Campaign saved', lock: 'Lock protocol',
      preflight: 'Preflight · 1 run', nextBatch: 'Run next batch', refresh: 'Refresh',
      batch: 'Batch size', pace: 'Pause between runs (s)', progress: 'Progress',
      draft: 'draft', locked: 'locked', complete: 'complete',
      completed: 'completed', remaining: 'remaining',
      loading: 'Loading…', previewing: 'Compiling and validating the 29 conditions…',
      saving: 'Saving ExperimentSpec records…', locking: 'Locking protocols…',
      running: 'Executing batch…', noCampaign: 'No saved campaign.',
      openRuns: 'Open legacy run archive', error: 'Error',
    },
  };

  const t = (key) => copy[language()][key] ?? key;

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { 'content-type': 'application/json', ...(options.headers || {}) },
    });
    const text = await response.text();
    let value;
    try { value = text ? JSON.parse(text) : null; } catch { value = text; }
    if (!response.ok) {
      const message = value?.detail?.message || value?.detail || value?.message || text || String(response.status);
      throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
    }
    return value;
  }

  function formatBytes(value) {
    const bytes = Number(value || 0);
    if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(2)} Go`;
    if (bytes >= 1_000_000) return `${Math.round(bytes / 1_000_000)} Mo`;
    return `${Math.round(bytes / 1_000)} Ko`;
  }

  function ensureNav() {
    const nav = $('#sidebar-nav');
    if (!nav || !$('#lvl-control')?.classList.contains('active')) return null;
    let button = nav.querySelector('[data-nav="campaigns"]');
    if (!button) {
      button = document.createElement('button');
      button.type = 'button';
      button.className = 'nav-button';
      button.dataset.nav = 'campaigns';
      nav.insertBefore(button, nav.querySelector('[data-nav="runs"]') || null);
    }
    button.textContent = t('nav');
    return button;
  }

  function ensurePanel() {
    const screen = $('.screen[data-screen="control"]');
    if (!screen) return null;
    const cards = screen.querySelector(':scope > .cards');
    const campaignCard = cards?.children?.[1];
    if (campaignCard) {
      campaignCard.dataset.controlView = 'campaigns';
      campaignCard.setAttribute('role', 'button');
      campaignCard.tabIndex = 0;
    }
    let panel = $('#campaign-center-panel');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'campaign-center-panel';
      panel.className = 'campaign-center card';
      panel.hidden = true;
      screen.insertBefore(panel, $('#legacy-control') || null);
    }
    if (!panel.dataset.ready) buildPanel(panel);
    return panel;
  }

  function buildPanel(panel) {
    panel.dataset.ready = '1';
    panel.innerHTML = `
      <h2></h2><p class="campaign-center-lede"></p><span class="campaign-signature"></span>
      <div class="campaign-source">
        <label><span></span><input class="campaign-file" type="file" accept="application/json,.json"></label>
        <button class="secondary campaign-demo" type="button"></button>
        <button class="primary campaign-preview" type="button"></button>
      </div>
      <p class="campaign-message" role="status"></p>
      <div class="campaign-preview-host"></div>
      <div class="campaign-status-host"></div>`;
    $('h2', panel).textContent = t('title');
    $('.campaign-center-lede', panel).textContent = t('lede');
    $('.campaign-signature', panel).textContent = t('signature');
    $('.campaign-source label span', panel).textContent = t('choose');
    $('.campaign-demo', panel).textContent = t('demo');
    $('.campaign-preview', panel).textContent = t('preview');

    $('.campaign-file', panel).addEventListener('change', async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      try {
        state.legacy = JSON.parse(await file.text());
        state.preview = null;
        setMessage(panel, file.name, false);
        renderPreview(panel);
      } catch (error) {
        setMessage(panel, error.message, true);
      }
    });
    $('.campaign-demo', panel).addEventListener('click', () => loadDemo(panel));
    $('.campaign-preview', panel).addEventListener('click', () => preview(panel));
  }

  function setBusy(panel, busy, message = '') {
    state.busy = busy;
    $$('button, input, select', panel).forEach((node) => { node.disabled = busy; });
    if (message) setMessage(panel, message, false);
  }

  function setMessage(panel, message, error = false) {
    const node = $('.campaign-message', panel);
    node.textContent = message || '';
    node.style.color = error ? 'var(--danger)' : '';
  }

  async function loadDemo(panel) {
    setBusy(panel, true, t('loading'));
    try {
      state.legacy = await api('/api/demo/campaign-01');
      await preview(panel);
    } catch (error) {
      setMessage(panel, `${t('error')} : ${error.message}`, true);
    } finally {
      setBusy(panel, false);
    }
  }

  async function preview(panel) {
    if (!state.legacy) {
      setMessage(panel, t('noSource'), true);
      return;
    }
    setBusy(panel, true, t('previewing'));
    try {
      state.preview = await api('/api/campaigns/legacy/preview', {
        method: 'POST', body: JSON.stringify(state.legacy),
      });
      state.campaignId = state.preview.campaign_id;
      setMessage(panel, `${state.preview.condition_count} ${t('conditions')} · ${state.preview.run_count} ${t('runs')}`, false);
      renderPreview(panel);
      await loadStatus(panel, false);
    } catch (error) {
      setMessage(panel, `${t('error')} : ${error.message}`, true);
    } finally {
      setBusy(panel, false);
    }
  }

  function metric(label, value) {
    const card = document.createElement('div');
    card.className = 'campaign-metric';
    const name = document.createElement('span'); name.textContent = label;
    const data = document.createElement('strong'); data.textContent = String(value);
    card.append(name, data);
    return card;
  }

  function renderPreview(panel) {
    const host = $('.campaign-preview-host', panel);
    host.replaceChildren();
    const plan = state.preview;
    if (!plan) return;

    const metrics = document.createElement('div');
    metrics.className = 'campaign-metrics';
    metrics.append(
      metric(t('conditions'), plan.condition_count), metric(t('repeats'), plan.repeats),
      metric(t('runs'), plan.run_count), metric(t('models'), Object.keys(plan.by_model || {}).length),
      metric(t('storage'), formatBytes(plan.estimated_raw_bytes)),
    );
    host.append(metrics);

    const models = document.createElement('section');
    models.className = 'campaign-models';
    const modelTitle = document.createElement('h3'); modelTitle.textContent = t('modelBreakdown');
    const modelGrid = document.createElement('div'); modelGrid.className = 'campaign-model-grid';
    Object.entries(plan.by_model || {}).forEach(([model, count]) => {
      const row = document.createElement('span'); row.textContent = `${model} · ${count} runs`; modelGrid.append(row);
    });
    models.append(modelTitle, modelGrid);
    host.append(models);

    const warnings = document.createElement('section');
    warnings.className = 'campaign-warnings';
    const warningTitle = document.createElement('h3'); warningTitle.textContent = t('warnings');
    const list = document.createElement('ul');
    (plan.warnings || []).forEach((warning) => { const item = document.createElement('li'); item.textContent = warning; list.append(item); });
    warnings.append(warningTitle, list);
    host.append(warnings);

    const conditions = document.createElement('section');
    conditions.className = 'campaign-conditions';
    const conditionTitle = document.createElement('h3'); conditionTitle.textContent = t('conditionMatrix');
    const details = document.createElement('details'); details.open = false;
    const summary = document.createElement('summary'); summary.textContent = t('showAll');
    const table = document.createElement('table');
    table.innerHTML = `<thead><tr><th>${t('cond')}</th><th>${t('domain')}</th><th>${t('lang')}</th><th>${t('model')}</th><th>${t('filter')}</th><th>${t('prompt')}</th></tr></thead>`;
    const body = document.createElement('tbody');
    (plan.conditions || []).forEach((row) => {
      const tr = document.createElement('tr');
      [row.condition_id, row.domain, row.language, row.model_id, row.filter_nonword_tokens ? t('yes') : t('no')].forEach((value) => {
        const td = document.createElement('td'); td.textContent = value; tr.append(td);
      });
      const prompt = document.createElement('td'); prompt.className = 'prompt'; prompt.textContent = row.prompt; prompt.title = row.prompt; tr.append(prompt);
      body.append(tr);
    });
    table.append(body); details.append(summary, table); conditions.append(conditionTitle, details); host.append(conditions);

    const actions = document.createElement('div');
    actions.className = 'campaign-actions';
    const save = document.createElement('button'); save.type = 'button'; save.className = 'primary'; save.textContent = t('save');
    save.addEventListener('click', () => saveCampaign(panel));
    actions.append(save);
    host.append(actions);
  }

  async function saveCampaign(panel) {
    if (!state.legacy) return;
    setBusy(panel, true, t('saving'));
    try {
      state.status = await api('/api/campaigns/legacy/save', { method: 'POST', body: JSON.stringify(state.legacy) });
      state.campaignId = state.status.campaign_id;
      state.log.unshift(`${new Date().toLocaleTimeString()} · ${t('saved')} · ${state.campaignId}`);
      setMessage(panel, `${t('saved')} · ${state.campaignId}`, false);
      renderStatus(panel);
    } catch (error) {
      setMessage(panel, `${t('error')} : ${error.message}`, true);
    } finally {
      setBusy(panel, false);
    }
  }

  async function loadStatus(panel, announce = true) {
    if (!state.campaignId) return;
    try {
      state.status = await api(`/api/campaigns/${encodeURIComponent(state.campaignId)}`);
      if (announce) setMessage(panel, `${t('progress')} · ${state.status.completed_runs}/${state.status.planned_runs}`, false);
      renderStatus(panel);
    } catch {
      if (announce) setMessage(panel, t('noCampaign'), true);
    }
  }

  function renderStatus(panel) {
    const host = $('.campaign-status-host', panel);
    host.replaceChildren();
    const status = state.status;
    if (!status) return;
    const card = document.createElement('section'); card.className = 'campaign-progress-card';
    const title = document.createElement('h3');
    const prereg = status.preregistration?.status || 'draft';
    title.textContent = `${t('progress')} · ${status.campaign_id} · ${t(prereg)}`;
    const bar = document.createElement('div'); bar.className = 'campaign-progress';
    const fill = document.createElement('i'); fill.style.width = `${Math.max(0, Math.min(100, Number(status.progress || 0) * 100))}%`; bar.append(fill);
    const meta = document.createElement('div'); meta.className = 'campaign-progress-meta';
    const left = document.createElement('span'); left.textContent = `${status.completed_runs} ${t('completed')}`;
    const right = document.createElement('span'); right.textContent = `${status.remaining_runs} ${t('remaining')}`;
    meta.append(left, right);

    const actions = document.createElement('div'); actions.className = 'campaign-actions';
    const lock = document.createElement('button'); lock.type = 'button'; lock.className = 'secondary'; lock.textContent = t('lock');
    lock.disabled = prereg === 'locked'; lock.addEventListener('click', () => lockCampaign(panel));
    const preflight = document.createElement('button'); preflight.type = 'button'; preflight.className = 'secondary'; preflight.textContent = t('preflight');
    preflight.addEventListener('click', () => execute(panel, '/preflight', {}));
    const batchLabel = document.createElement('label'); batchLabel.textContent = t('batch');
    const batch = document.createElement('select'); batch.className = 'campaign-batch';
    [1, 3, 8].forEach((value) => { const option = document.createElement('option'); option.value = value; option.textContent = value; batch.append(option); });
    batch.value = '3'; batchLabel.append(batch);
    const paceLabel = document.createElement('label'); paceLabel.textContent = t('pace');
    const pace = document.createElement('input'); pace.className = 'campaign-pace'; pace.type = 'number'; pace.min = '0'; pace.max = '30'; pace.step = '0.5'; pace.value = '3'; paceLabel.append(pace);
    const run = document.createElement('button'); run.type = 'button'; run.className = 'primary'; run.textContent = t('nextBatch');
    run.disabled = status.remaining_runs === 0; run.addEventListener('click', () => execute(panel, '/execute', { limit: Number(batch.value), pace_seconds: Number(pace.value) }));
    const refresh = document.createElement('button'); refresh.type = 'button'; refresh.className = 'secondary'; refresh.textContent = t('refresh'); refresh.addEventListener('click', () => loadStatus(panel));
    const legacy = document.createElement('a'); legacy.href = '/#runs'; legacy.textContent = t('openRuns');
    actions.append(lock, preflight, batchLabel, paceLabel, run, refresh, legacy);

    const log = document.createElement('pre'); log.className = 'campaign-run-log'; log.textContent = state.log.join('\n') || '—';
    card.append(title, bar, meta, actions, log); host.append(card);
  }

  async function lockCampaign(panel) {
    setBusy(panel, true, t('locking'));
    try {
      state.status = await api(`/api/campaigns/${encodeURIComponent(state.campaignId)}/lock`, { method: 'POST', body: '{}' });
      state.log.unshift(`${new Date().toLocaleTimeString()} · ${t('locked')} · NicoMrx`);
      renderStatus(panel);
      setMessage(panel, `${state.campaignId} · ${t('locked')}`, false);
    } catch (error) {
      setMessage(panel, `${t('error')} : ${error.message}`, true);
    } finally {
      setBusy(panel, false);
    }
  }

  async function execute(panel, suffix, payload) {
    setBusy(panel, true, t('running'));
    try {
      const result = await api(`/api/campaigns/${encodeURIComponent(state.campaignId)}${suffix}`, {
        method: 'POST', body: JSON.stringify(payload),
      });
      state.status = result.status;
      (result.completed || []).forEach((row) => state.log.unshift(`${new Date().toLocaleTimeString()} · OK · ${row.condition_id} · ${row.run_id}`));
      (result.errors || []).forEach((row) => state.log.unshift(`${new Date().toLocaleTimeString()} · ERROR · ${row.condition_id} · ${row.error}`));
      renderStatus(panel);
      setMessage(panel, `${result.completed?.length || 0} ${t('completed')} · ${result.errors?.length || 0} ${t('error')}`, Boolean(result.errors?.length));
    } catch (error) {
      setMessage(panel, `${t('error')} : ${error.message}`, true);
    } finally {
      setBusy(panel, false);
    }
  }

  function activate() {
    localStorage.setItem(VIEW_KEY, 'campaigns');
    const panel = ensurePanel();
    if (!panel) return;
    $$('.screen').forEach((node) => node.classList.toggle('active', node.dataset.screen === 'control'));
    $$('.levels button').forEach((node) => node.classList.toggle('active', node.dataset.level === 'control'));
    ensureNav();
    panel.hidden = false;
    $$('#sidebar-nav [data-nav]').forEach((node) => node.classList.toggle('active', node.dataset.nav === 'campaigns'));
    $$('.screen[data-screen="control"] [data-control-view]').forEach((node) => node.classList.toggle('active', node.dataset.controlView === 'campaigns'));
  }

  function deactivate() {
    const panel = $('#campaign-center-panel');
    if (panel) panel.hidden = true;
  }

  document.addEventListener('click', (event) => {
    const campaignTarget = event.target.closest('[data-nav="campaigns"], [data-control-view="campaigns"]');
    if (campaignTarget) { event.preventDefault(); activate(); return; }
    const nav = event.target.closest('#sidebar-nav [data-nav]');
    if (nav && nav.dataset.nav !== 'campaigns') deactivate();
    const level = event.target.closest('[data-level]');
    if (level && level.dataset.level !== 'control') deactivate();
  });

  document.addEventListener('keydown', (event) => {
    const card = event.target.closest?.('[data-control-view="campaigns"]');
    if (!card || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault(); activate();
  });

  window.addEventListener('DOMContentLoaded', () => {
    ensurePanel(); ensureNav();
    const observer = new MutationObserver(() => { ensureNav(); ensurePanel(); });
    observer.observe($('#sidebar-nav') || document.body, { childList: true, subtree: true });
    new MutationObserver(() => {
      const panel = $('#campaign-center-panel');
      if (panel) { panel.dataset.ready = ''; panel.replaceChildren(); buildPanel(panel); renderPreview(panel); renderStatus(panel); }
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    if (localStorage.getItem(VIEW_KEY) === 'campaigns' && $('#lvl-control')?.classList.contains('active')) activate();
  });
})();
