(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const PAIR_B_KEY = 'prismora.v4.comparisonB';
  const CAMPAIGN_DEMO_KEY = 'prismora.v4.loadCampaignDemo';
  const $ = (selector, root = document) => root.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let manifest = null;
  let loading = false;

  const copy = {
    fr: {
      nav: 'Démos', trigger: 'Données de démonstration', title: 'Bibliothèque de démonstration',
      intro: 'Des données synthétiques déterministes et des exports Neuronpedia réels, vérifiés avant chargement. Les sous-ensembles réels conservent les hashes des raws immuables.',
      signature: 'Sélection et signature : NicoMrx', syntheticTitle: 'Démo synthétique vérifiée',
      syntheticText: 'La petite paire déterministe utilisée pour vérifier Lire, Explorer et les garde-fous causaux sans réseau.',
      real: 'données réelles', curated: 'sous-ensemble vérifié', offline: 'sans réseau',
      read: 'Ouvrir dans Lire', compare: 'Comparer A/B', campaign: 'Ouvrir Campagne 01',
      campaignTitle: 'Campagne 01 — 29 conditions / 87 runs',
      campaignText: 'Importer l’ancien kit, compiler les ExperimentSpec, vérifier la matrice et passer le préflight avant toute exécution massive.',
      limits: 'Limites : les numéros de couches ne sont pas supposés équivalents entre modèles ; un candidat décodable ne prouve ni conscience, ni intention, ni pensée cachée.',
      loading: 'Vérification des hashes et chargement…', error: 'Erreur de démonstration',
      channelFinal: 'final normalisé', crossModel: 'inter-modèles exploratoire',
      controls: 'contrôles A disponibles', close: 'Fermer',
    },
    en: {
      nav: 'Demos', trigger: 'Demo data', title: 'Demo Library',
      intro: 'Deterministic synthetic data and real Neuronpedia exports, verified before loading. Curated real subsets preserve immutable-raw hashes.',
      signature: 'Selection and signature: NicoMrx', syntheticTitle: 'Verified synthetic demo',
      syntheticText: 'The small deterministic pair used to verify Read, Explore and causal safeguards without network access.',
      real: 'real data', curated: 'verified subset', offline: 'offline',
      read: 'Open in Read', compare: 'Compare A/B', campaign: 'Open Campaign 01',
      campaignTitle: 'Campaign 01 — 29 conditions / 87 runs',
      campaignText: 'Import the legacy kit, compile ExperimentSpec records, verify the matrix and pass preflight before large execution.',
      limits: 'Limits: layer numbers are not assumed equivalent across models; a decodable candidate does not establish consciousness, intention or hidden thought.',
      loading: 'Verifying hashes and loading…', error: 'Demo error',
      channelFinal: 'normalized final', crossModel: 'exploratory cross-model',
      controls: 'A-branch controls available', close: 'Close',
    },
  };

  const t = (key) => copy[language()][key] ?? key;

  async function api(path) {
    const response = await fetch(path);
    const text = await response.text();
    let value;
    try { value = text ? JSON.parse(text) : null; } catch { value = text; }
    if (!response.ok) throw new Error(value?.detail || value?.message || text || String(response.status));
    return value;
  }

  function setStatus(message, error = false) {
    const node = $('#demo-library-status');
    if (!node) return;
    node.textContent = message || '';
    node.style.color = error ? 'var(--danger)' : '';
  }

  function ensureTrigger() {
    const nav = $('#sidebar-nav');
    if (nav && !nav.querySelector('[data-nav="demos"]')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'nav-button';
      button.dataset.nav = 'demos';
      button.textContent = t('nav');
      const before = nav.querySelector('[data-nav="models"]');
      nav.insertBefore(button, before || null);
    } else if (nav?.querySelector('[data-nav="demos"]')) {
      nav.querySelector('[data-nav="demos"]').textContent = t('nav');
    }

    const actions = $('.demo-actions');
    if (actions && !$('#open-demo-library')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'open-demo-library';
      button.className = 'secondary demo-library-trigger';
      button.textContent = t('trigger');
      actions.insertBefore(button, $('#reader-status') || null);
    } else if ($('#open-demo-library')) {
      $('#open-demo-library').textContent = t('trigger');
    }
  }

  function ensureDialog() {
    let dialog = $('#demo-library-dialog');
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.id = 'demo-library-dialog';
      dialog.className = 'demo-library-dialog';
      document.body.append(dialog);
    }
    return dialog;
  }

  function badges(values) {
    const row = document.createElement('div');
    row.className = 'demo-badges';
    values.forEach((value) => { const badge = document.createElement('span'); badge.textContent = value; row.append(badge); });
    return row;
  }

  function cardShell(title, text, className = '') {
    const card = document.createElement('article');
    card.className = `demo-card ${className}`.trim();
    const heading = document.createElement('h3'); heading.textContent = title;
    const description = document.createElement('p'); description.textContent = text;
    card.append(heading, description);
    return card;
  }

  function actionButton(label, className, handler) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = className; button.textContent = label;
    button.addEventListener('click', handler);
    return button;
  }

  function renderDialog() {
    const dialog = ensureDialog();
    dialog.replaceChildren();
    const header = document.createElement('header'); header.className = 'modal-head';
    const title = document.createElement('h2'); title.textContent = t('title');
    const close = document.createElement('button'); close.type = 'button'; close.className = 'modal-close'; close.textContent = '×'; close.setAttribute('aria-label', t('close')); close.onclick = () => dialog.close();
    header.append(title, close);
    const body = document.createElement('div'); body.className = 'demo-library-body';
    const intro = document.createElement('p'); intro.className = 'demo-library-intro'; intro.textContent = t('intro');
    const signature = document.createElement('span'); signature.className = 'demo-library-signature'; signature.textContent = t('signature');
    const grid = document.createElement('div'); grid.className = 'demo-library-grid';

    const synthetic = cardShell(t('syntheticTitle'), t('syntheticText'));
    synthetic.append(badges([t('offline'), 'prismora.run/v2']));
    const syntheticActions = document.createElement('div'); syntheticActions.className = 'demo-card-actions';
    syntheticActions.append(actionButton(t('read'), 'primary', () => {
      dialog.close(); $('#load-demo')?.click();
    }));
    synthetic.append(syntheticActions); grid.append(synthetic);

    (manifest?.cards || []).forEach((item) => {
      const titleText = language() === 'fr' ? item.title_fr : item.title_en;
      const observations = language() === 'fr' ? (item.observations_fr || []) : (item.observations_en || item.observations_fr || []);
      const card = cardShell(titleText, observations[0] || '', 'real');
      if (observations.length > 1) {
        const list = document.createElement('ul');
        observations.slice(1).forEach((value) => { const li = document.createElement('li'); li.textContent = value; list.append(li); });
        card.append(list);
      }
      const extra = [t('real'), t('curated'), t('crossModel')];
      if (item.demo_id === 'same-question') extra.push(t('channelFinal'));
      if (item.controls) extra.push(t('controls'));
      card.append(badges(extra));
      const actions = document.createElement('div'); actions.className = 'demo-card-actions';
      actions.append(
        actionButton(t('read'), 'secondary', () => loadSingle(item.artifact_a)),
        actionButton(t('compare'), 'primary', () => loadPair(item.artifact_a, item.artifact_b)),
      );
      card.append(actions); grid.append(card);
    });

    const campaign = cardShell(t('campaignTitle'), t('campaignText'), 'campaign');
    campaign.append(badges(['29 conditions', '3×', '87 runs', 'NicoMrx']));
    const campaignActions = document.createElement('div'); campaignActions.className = 'demo-card-actions';
    campaignActions.append(actionButton(t('campaign'), 'primary', openCampaign));
    campaign.append(campaignActions); grid.append(campaign);

    const limits = document.createElement('p'); limits.className = 'demo-library-limits'; limits.textContent = t('limits');
    const status = document.createElement('p'); status.id = 'demo-library-status'; status.className = 'demo-library-status'; status.setAttribute('role', 'status');
    body.append(intro, signature, grid, limits, status); dialog.append(header, body);
  }

  async function openLibrary() {
    const dialog = ensureDialog();
    renderDialog(); dialog.showModal();
    if (manifest || loading) return;
    loading = true; setStatus(t('loading'));
    try {
      manifest = await api('/api/demo/showcase');
      renderDialog();
    } catch (error) {
      setStatus(`${t('error')} : ${error.message}`, true);
    } finally {
      loading = false;
    }
  }

  function sessionFor(artifact, level) {
    return {
      version: 1, artifact, sourceType: 'demo-library', selectedToken: 0,
      selectedLayer: null, level,
    };
  }

  async function loadSingle(runId) {
    setStatus(t('loading'));
    try {
      const artifact = await api(`/api/demo/showcase/${encodeURIComponent(runId)}`);
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionFor(artifact, 'read')));
      localStorage.setItem('prismora.level', 'read');
      location.assign('/v4.html?demo=' + encodeURIComponent(runId));
    } catch (error) {
      setStatus(`${t('error')} : ${error.message}`, true);
    }
  }

  async function loadPair(runA, runB) {
    setStatus(t('loading'));
    try {
      const [a, b] = await Promise.all([
        api(`/api/demo/showcase/${encodeURIComponent(runA)}`),
        api(`/api/demo/showcase/${encodeURIComponent(runB)}`),
      ]);
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionFor(a, 'explore')));
      sessionStorage.setItem(PAIR_B_KEY, JSON.stringify(b));
      localStorage.setItem('prismora.level', 'explore');
      localStorage.setItem('prismora.v4.exploreView', 'compare');
      location.assign('/v4.html?pair=' + encodeURIComponent(runA + '--' + runB));
    } catch (error) {
      setStatus(`${t('error')} : ${error.message}`, true);
    }
  }

  function openCampaign() {
    localStorage.setItem('prismora.level', 'control');
    localStorage.setItem('prismora.v4.controlView', 'campaigns');
    sessionStorage.setItem(CAMPAIGN_DEMO_KEY, '1');
    location.assign('/v4.html?campaign=campaign-01');
  }

  function restoreComparisonB() {
    const raw = sessionStorage.getItem(PAIR_B_KEY);
    if (!raw) return;
    let artifact;
    try { artifact = JSON.parse(raw); } catch { sessionStorage.removeItem(PAIR_B_KEY); return; }
    let attempts = 0;
    const attach = () => {
      const input = $('.user-comparison-b');
      if (!input) {
        attempts += 1;
        if (attempts < 80) requestAnimationFrame(attach);
        return;
      }
      try {
        const transfer = new DataTransfer();
        transfer.items.add(new File([JSON.stringify(artifact)], `${artifact.run_id || 'demo-b'}.json`, { type: 'application/json' }));
        input.files = transfer.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        sessionStorage.removeItem(PAIR_B_KEY);
      } catch {
        // Manual selection remains available if the browser blocks DataTransfer.
      }
    };
    attach();
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('#open-demo-library, [data-nav="demos"]')) {
      event.preventDefault(); openLibrary();
    }
  });

  window.addEventListener('DOMContentLoaded', () => {
    ensureTrigger(); restoreComparisonB();
    new MutationObserver(ensureTrigger).observe($('#sidebar-nav') || document.body, { childList: true, subtree: true });
    new MutationObserver(() => { manifest = null; ensureTrigger(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  });
})();
