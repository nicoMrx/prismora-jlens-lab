(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const $ = (selector, root = document) => root.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  const state = { a: null, b: null, manifest: null, scheduled: false };

  const copy = {
    fr: {
      metaTitle: 'Meta Capture — lecture instrumentale',
      metaLead: 'Le même candidat exact « meta » est suivi dans les readouts, puis séparé de sa lexicalisation dans la réponse finale.',
      sameTitle: 'Qwen ↔ GPT-OSS — profil de la paire',
      sameLead: 'Le prompt textuel et les paramètres sont identiques. La comparaison reste exploratoire car les tokenizers et les architectures diffèrent.',
      model: 'Modèle', top8: 'Cellules top-8', positions: 'Positions', top1: 'Cellules top-1', max: 'Probabilité max.', lexicalized: 'Lexicalisé dans le final',
      yes: 'oui', no: 'non', promptTokens: 'Tokens du prompt', layers: 'Couches du modèle', analysis: 'Canal analysis', final: 'Canal comparé',
      normalizedFinal: 'final normalisé', control: 'Contrôles branche A',
      controlText: (qwen, gpt) => `Qwen : ${qwen} cellule top-1 · GPT-OSS : ${gpt} cellule top-1`,
      caution: 'Un candidat décodable ne prouve ni conscience, ni intention, ni pensée cachée. Les numéros de couches ne sont pas supposés équivalents entre modèles.',
    },
    en: {
      metaTitle: 'Meta Capture — instrumental reading',
      metaLead: 'The exact candidate “meta” is tracked in readouts, then separated from lexicalization in the final answer.',
      sameTitle: 'Qwen ↔ GPT-OSS — pair profile',
      sameLead: 'The textual prompt and parameters are identical. The comparison remains exploratory because tokenizers and architectures differ.',
      model: 'Model', top8: 'Top-8 cells', positions: 'Positions', top1: 'Top-1 cells', max: 'Max probability', lexicalized: 'Lexicalized in final',
      yes: 'yes', no: 'no', promptTokens: 'Prompt tokens', layers: 'Model layers', analysis: 'Analysis channel', final: 'Compared channel',
      normalizedFinal: 'normalized final', control: 'A-branch controls',
      controlText: (qwen, gpt) => `Qwen: ${qwen} top-1 cell · GPT-OSS: ${gpt} top-1 cell`,
      caution: 'A decodable candidate does not establish consciousness, intention or hidden thought. Layer numbers are not assumed equivalent across models.',
    },
  };
  const t = (key) => copy[language()][key] ?? key;

  function sessionArtifact() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null')?.artifact || null; }
    catch { return null; }
  }

  function completion(value) {
    return String(value?.result?.done?.completion || value?.result?.completion || '');
  }

  function lexicalized(value) {
    return /(^|[^\p{L}])(méta|meta)(?=$|[^\p{L}])/iu.test(completion(value));
  }

  function requestedLayerCount(value) {
    const requested = value?.coverage?.requested_layers;
    if (Array.isArray(requested) && requested.length) return requested.length;
    const byType = value?.result?.meta?.layers_by_type || {};
    return Math.max(0, ...Object.values(byType).map((layers) => Array.isArray(layers) ? layers.length : 0));
  }

  function promptLength(value) {
    return value?.result?.meta?.prompt_len ?? value?.result?.done?.prompt_len ?? '—';
  }

  function metric(label, value) {
    const row = document.createElement('div');
    row.className = 'showcase-metric';
    const term = document.createElement('span'); term.textContent = label;
    const data = document.createElement('strong'); data.textContent = String(value);
    row.append(term, data);
    return row;
  }

  function modelCard(value, trace) {
    const card = document.createElement('article');
    card.className = 'showcase-model-card';
    const heading = document.createElement('h4');
    heading.textContent = value?.request?.model?.model_id || t('model');
    const grid = document.createElement('div'); grid.className = 'showcase-metric-grid';
    grid.append(
      metric(t('top8'), trace?.cells_top8 ?? '—'),
      metric(t('positions'), trace?.positions ?? '—'),
      metric(t('top1'), trace?.top1_cells ?? '—'),
      metric(t('max'), trace?.max_probability ?? '—'),
      metric(t('lexicalized'), lexicalized(value) ? t('yes') : t('no')),
    );
    card.append(heading, grid);
    return card;
  }

  function pairProfileCard(value) {
    const card = document.createElement('article');
    card.className = 'showcase-model-card';
    const heading = document.createElement('h4');
    heading.textContent = value?.request?.model?.model_id || t('model');
    const grid = document.createElement('div'); grid.className = 'showcase-metric-grid';
    grid.append(
      metric(t('promptTokens'), promptLength(value)),
      metric(t('layers'), requestedLayerCount(value)),
      metric(t('analysis'), value?.result?.meta?.channels?.analysis?.present ? t('yes') : t('no')),
      metric(t('final'), value?.result?.meta?.default_channel === 'final' ? t('normalizedFinal') : value?.result?.meta?.default_channel || '—'),
    );
    card.append(heading, grid);
    return card;
  }

  async function loadManifest() {
    if (state.manifest) return state.manifest;
    try {
      const response = await fetch('/api/demo/showcase');
      if (response.ok) state.manifest = await response.json();
    } catch {
      state.manifest = null;
    }
    return state.manifest;
  }

  function insertPanel(workbench, panel) {
    const anchor = $('.user-comparison-compatibility', workbench) || $('.user-comparison-controls', workbench);
    workbench.insertBefore(panel, anchor || null);
  }

  async function render() {
    const workbench = $('.user-comparison-workbench');
    const compareView = $('#explorer-compare-view');
    if (!workbench || !compareView) return;
    $('.showcase-insights', workbench)?.remove();
    compareView.classList.remove('showcase-pair-active');
    if (!state.a || !state.b) return;

    const traceA = state.a?.derived?.concept_traces?.meta;
    const traceB = state.b?.derived?.concept_traces?.meta;
    const isMeta = Boolean(traceA && traceB);
    const sameQuestion = String(state.a?.run_id || '').includes('same-question') && String(state.b?.run_id || '').includes('same-question');
    if (!isMeta && !sameQuestion) return;

    compareView.classList.add('showcase-pair-active');
    const panel = document.createElement('section');
    panel.className = `showcase-insights ${isMeta ? 'meta' : 'same-question'}`;
    const heading = document.createElement('h3');
    heading.textContent = isMeta ? t('metaTitle') : t('sameTitle');
    const lead = document.createElement('p');
    lead.textContent = isMeta ? t('metaLead') : t('sameLead');
    const grid = document.createElement('div'); grid.className = 'showcase-model-grid';
    if (isMeta) grid.append(modelCard(state.a, traceA), modelCard(state.b, traceB));
    else grid.append(pairProfileCard(state.a), pairProfileCard(state.b));
    panel.append(heading, lead, grid);

    if (isMeta) {
      const manifest = await loadManifest();
      const controls = manifest?.cards?.find((card) => card.demo_id === 'meta-capture')?.controls;
      if (controls) {
        const control = document.createElement('p');
        control.className = 'showcase-control';
        control.innerHTML = `<strong>${t('control')}</strong><span>${t('controlText')(controls.qwen_branch_a?.top1_cells ?? '—', controls.gpt_oss_branch_a?.top1_cells ?? '—')}</span>`;
        panel.append(control);
      }
    }
    const caution = document.createElement('p'); caution.className = 'showcase-caution'; caution.textContent = t('caution');
    panel.append(caution);
    insertPanel(workbench, panel);
  }

  async function readInput(input, side) {
    const file = input.files?.[0];
    if (!file) return;
    try { state[side] = JSON.parse(await file.text()); }
    catch { state[side] = null; }
    schedule();
  }

  function schedule() {
    if (state.scheduled) return;
    state.scheduled = true;
    requestAnimationFrame(() => {
      state.scheduled = false;
      render();
    });
  }

  document.addEventListener('change', (event) => {
    if (event.target.matches?.('.user-comparison-a')) readInput(event.target, 'a');
    if (event.target.matches?.('.user-comparison-b')) readInput(event.target, 'b');
  });
  document.addEventListener('click', (event) => {
    if (event.target.closest('.user-comparison-loaded')) {
      state.a = sessionArtifact();
      schedule();
    }
  });

  window.addEventListener('DOMContentLoaded', () => {
    state.a = sessionArtifact();
    const view = $('#explorer-compare-view') || document.body;
    new MutationObserver(schedule).observe(view, { childList: true, subtree: true });
    new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    schedule();
  });
})();