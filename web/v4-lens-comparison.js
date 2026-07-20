(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const runtime = { artifact: null, scheduled: false };
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const lang = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';

  const copy = {
    fr: {
      title: 'Comparer Jacobian et Logit',
      subtitle: 'Deux lectures séparées, puis une superposition contrôlée.',
      jacobian: 'Tableau Jacobian Lens',
      logit: 'Tableau Logit Lens',
      overlay: 'Superposition des trajectoires top-1',
      layer: 'Couche',
      candidate: 'Candidat',
      probability: 'Probabilité',
      noBoth: 'Cet artifact doit contenir Jacobian Lens et Logit Lens pour activer cette comparaison.',
      noRows: 'Aucun candidat mesuré à cette couche.',
      referenceLayer: 'Couche comparée',
      agreement: 'Accord top-1',
      firstDifference: 'Première divergence top-1',
      none: 'aucune dans les couches communes',
      commonLayers: 'couches communes',
      guard: 'La superposition suit le top-1 propre à chaque lentille. Elle compare des sorties mesurées, mais ne prétend pas que Jacobian et Logit représentent le même mécanisme interne.',
      legendJacob: 'Top-1 Jacobian',
      legendLogit: 'Top-1 Logit',
      layerShort: 'L',
    },
    en: {
      title: 'Compare Jacobian and Logit',
      subtitle: 'Two separate readings, followed by a controlled overlay.',
      jacobian: 'Jacobian Lens table',
      logit: 'Logit Lens table',
      overlay: 'Top-1 trajectory overlay',
      layer: 'Layer',
      candidate: 'Candidate',
      probability: 'Probability',
      noBoth: 'This artifact must contain both Jacobian Lens and Logit Lens to enable this comparison.',
      noRows: 'No measured candidate at this layer.',
      referenceLayer: 'Compared layer',
      agreement: 'Top-1 agreement',
      firstDifference: 'First top-1 divergence',
      none: 'none across common layers',
      commonLayers: 'common layers',
      guard: 'The overlay follows each lens’s own top-1. It compares measured outputs, but does not claim that Jacobian and Logit represent the same internal mechanism.',
      legendJacob: 'Jacobian top-1',
      legendLogit: 'Logit top-1',
      layerShort: 'L',
    },
  };

  const t = (key) => copy[lang()][key];
  const isArtifact = (value) => value?.schema === 'prismora.run/v2';
  const generatedTokens = (artifact) => (artifact?.result?.tokens || []).filter((token) => token?.is_generated);
  const layersFor = (artifact, lens) => artifact?.result?.meta?.layers_by_type?.[lens] || [];
  const resultFor = (token, lens) => (token?.results || []).find((row) => row?.type === lens) || null;

  function candidatesFor(artifact, token, lens, layer) {
    const layers = layersFor(artifact, lens);
    const index = layers.indexOf(layer);
    const result = resultFor(token, lens);
    if (index < 0 || !result) return [];
    return (result.top_tokens?.[index] || []).map((name, candidateIndex) => [
      String(name),
      Number(result.top_probs?.[index]?.[candidateIndex] || 0),
    ]);
  }

  function artifactFromSession() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
      return isArtifact(saved?.artifact) ? saved.artifact : null;
    } catch {
      return null;
    }
  }

  function activeToken() {
    const tokens = generatedTokens(runtime.artifact);
    const buttons = $$('#tokens .token');
    const index = buttons.findIndex((button) => button.classList.contains('active'));
    return tokens[index >= 0 ? index : 0] || tokens[0] || null;
  }

  function activeLayer() {
    const buttons = $$('#layer-rail .layer-button');
    const numbers = $$('#layer-rail .layer-number');
    const index = buttons.findIndex((button) => button.classList.contains('active'));
    return index >= 0 ? Number(numbers[index]?.textContent) : null;
  }

  function nearestLayer(layers, requested) {
    if (!layers.length) return null;
    if (requested === null || Number.isNaN(requested)) return layers.at(-1);
    return layers.reduce((best, layer) => Math.abs(layer - requested) < Math.abs(best - requested) ? layer : best, layers[0]);
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
        done: { completion: value.kind === 'chat' ? last('assistant') : value.tokens.filter((token) => token?.is_generated).map((token) => token?.token || '').join('') },
      },
      coverage: { captured_layers: layersByType.JACOBIAN_LENS || [], lens_types: Object.keys(layersByType) },
      provenance: { backend: 'neuronpedia_export', source: 'local-file', original_filename: filename },
    };
  }

  function ensurePanel() {
    const screen = $('.screen[data-screen="explore"]');
    if (!screen) return null;
    let panel = $('#lens-comparison-panel');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'lens-comparison-panel';
      panel.className = 'lens-comparison-panel card';
      const legacy = $('#legacy-explore');
      screen.insertBefore(panel, legacy || null);
    }
    return panel;
  }

  function tableCard(title, rows, className) {
    const card = document.createElement('article');
    card.className = `lens-table-card ${className}`;
    const heading = document.createElement('h3');
    heading.textContent = title;
    card.append(heading);

    if (!rows.length) {
      const empty = document.createElement('p');
      empty.textContent = t('noRows');
      card.append(empty);
      return card;
    }

    const table = document.createElement('table');
    table.innerHTML = `<thead><tr><th>#</th><th>${t('candidate')}</th><th>${t('probability')}</th></tr></thead>`;
    const body = document.createElement('tbody');
    rows.slice(0, 8).forEach(([name, probability], index) => {
      const row = document.createElement('tr');
      const rank = document.createElement('td');
      rank.textContent = String(index + 1);
      const candidate = document.createElement('td');
      const strong = document.createElement('strong');
      strong.textContent = name;
      candidate.append(strong);
      const probabilityCell = document.createElement('td');
      probabilityCell.textContent = probability.toFixed(4);
      row.append(rank, candidate, probabilityCell);
      body.append(row);
    });
    table.append(body);
    card.append(table);
    return card;
  }

  function seriesFor(artifact, token, lens, commonLayers) {
    return commonLayers.map((layer) => {
      const top = candidatesFor(artifact, token, lens, layer)[0];
      return { layer, token: top?.[0] || null, probability: top?.[1] ?? null };
    });
  }

  function pathFor(series, x, y) {
    const points = series.filter((point) => point.probability !== null);
    return points.map((point, index) => `${index ? 'L' : 'M'} ${x(point.layer).toFixed(2)} ${y(point.probability).toFixed(2)}`).join(' ');
  }

  function overlayCard(artifact, token, commonLayers, jacobianSeries, logitSeries) {
    const card = document.createElement('article');
    card.className = 'lens-overlay-card';
    const heading = document.createElement('div');
    heading.className = 'lens-overlay-heading';
    const title = document.createElement('h3');
    title.textContent = t('overlay');
    const legend = document.createElement('div');
    legend.className = 'lens-overlay-legend';
    legend.innerHTML = `<span class="jacobian"><i></i>${t('legendJacob')}</span><span class="logit"><i></i>${t('legendLogit')}</span>`;
    heading.append(title, legend);
    card.append(heading);

    if (!commonLayers.length) {
      const empty = document.createElement('p');
      empty.textContent = t('noBoth');
      card.append(empty);
      return card;
    }

    const width = 1000;
    const height = 260;
    const padX = 48;
    const padTop = 24;
    const padBottom = 34;
    const minLayer = commonLayers[0];
    const maxLayer = commonLayers.at(-1);
    const x = (layer) => padX + ((layer - minLayer) / Math.max(1, maxLayer - minLayer)) * (width - padX * 2);
    const y = (probability) => padTop + (1 - Math.max(0, Math.min(1, probability))) * (height - padTop - padBottom);

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.classList.add('lens-overlay-chart');

    [0, 0.25, 0.5, 0.75, 1].forEach((probability) => {
      const line = document.createElementNS(svg.namespaceURI, 'line');
      line.setAttribute('x1', padX);
      line.setAttribute('x2', width - padX);
      line.setAttribute('y1', y(probability));
      line.setAttribute('y2', y(probability));
      line.classList.add('overlay-grid');
      svg.append(line);
      const label = document.createElementNS(svg.namespaceURI, 'text');
      label.setAttribute('x', 4);
      label.setAttribute('y', y(probability) + 4);
      label.textContent = probability.toFixed(2);
      label.classList.add('overlay-axis-label');
      svg.append(label);
    });

    const addSeries = (series, className) => {
      const path = document.createElementNS(svg.namespaceURI, 'path');
      path.setAttribute('d', pathFor(series, x, y));
      path.classList.add('overlay-line', className);
      svg.append(path);
      series.filter((point) => point.probability !== null).forEach((point) => {
        const circle = document.createElementNS(svg.namespaceURI, 'circle');
        circle.setAttribute('cx', x(point.layer));
        circle.setAttribute('cy', y(point.probability));
        circle.setAttribute('r', 5);
        circle.classList.add('overlay-point', className);
        const tooltip = document.createElementNS(svg.namespaceURI, 'title');
        tooltip.textContent = `${t('layerShort')}${point.layer} · ${point.token || '—'} · p=${point.probability.toFixed(4)}`;
        circle.append(tooltip);
        svg.append(circle);
      });
    };

    addSeries(jacobianSeries, 'jacobian');
    addSeries(logitSeries, 'logit');

    const labelLayers = [...new Set([minLayer, ...commonLayers.filter((layer) => layer % 8 === 0), maxLayer])];
    labelLayers.forEach((layer) => {
      const label = document.createElementNS(svg.namespaceURI, 'text');
      label.setAttribute('x', x(layer));
      label.setAttribute('y', height - 7);
      label.textContent = layer;
      label.classList.add('overlay-layer-label');
      svg.append(label);
    });

    card.append(svg);

    const agreementCount = commonLayers.filter((layer, index) => jacobianSeries[index]?.token && jacobianSeries[index]?.token === logitSeries[index]?.token).length;
    const firstDifferenceIndex = commonLayers.findIndex((layer, index) => jacobianSeries[index]?.token && logitSeries[index]?.token && jacobianSeries[index].token !== logitSeries[index].token);
    const stats = document.createElement('div');
    stats.className = 'lens-overlay-stats';
    const agreement = document.createElement('strong');
    agreement.textContent = `${t('agreement')} : ${agreementCount}/${commonLayers.length} ${t('commonLayers')}`;
    const difference = document.createElement('span');
    difference.textContent = `${t('firstDifference')} : ${firstDifferenceIndex >= 0 ? `${t('layerShort')}${commonLayers[firstDifferenceIndex]} · ${jacobianSeries[firstDifferenceIndex].token} / ${logitSeries[firstDifferenceIndex].token}` : t('none')}`;
    stats.append(agreement, difference);
    card.append(stats);

    const guard = document.createElement('p');
    guard.className = 'lens-comparison-guard';
    guard.textContent = t('guard');
    card.append(guard);
    return card;
  }

  function render() {
    const panel = ensurePanel();
    if (!panel) return;
    const artifact = runtime.artifact || artifactFromSession();
    runtime.artifact = artifact;
    panel.replaceChildren();

    const title = document.createElement('h2');
    title.textContent = t('title');
    const subtitle = document.createElement('p');
    subtitle.className = 'lens-comparison-subtitle';
    subtitle.textContent = t('subtitle');
    panel.append(title, subtitle);

    if (!artifact) {
      const empty = document.createElement('p');
      empty.textContent = t('noBoth');
      panel.append(empty);
      return;
    }

    const token = activeToken();
    const jacobianLayers = layersFor(artifact, 'JACOBIAN_LENS');
    const logitLayers = layersFor(artifact, 'LOGIT_LENS');
    if (!token || !jacobianLayers.length || !logitLayers.length) {
      const empty = document.createElement('p');
      empty.textContent = t('noBoth');
      panel.append(empty);
      return;
    }

    const requestedLayer = activeLayer();
    const jacobianLayer = nearestLayer(jacobianLayers, requestedLayer);
    const logitLayer = nearestLayer(logitLayers, requestedLayer);
    const commonLayers = jacobianLayers.filter((layer) => logitLayers.includes(layer));
    const tables = document.createElement('div');
    tables.className = 'lens-table-grid';
    const jacobianRows = candidatesFor(artifact, token, 'JACOBIAN_LENS', jacobianLayer);
    const logitRows = candidatesFor(artifact, token, 'LOGIT_LENS', logitLayer);
    const jacobianCard = tableCard(`${t('jacobian')} · ${t('layer')} ${jacobianLayer}`, jacobianRows, 'jacobian');
    const logitCard = tableCard(`${t('logit')} · ${t('layer')} ${logitLayer}`, logitRows, 'logit');
    tables.append(jacobianCard, logitCard);
    panel.append(tables);

    const jacobianSeries = seriesFor(artifact, token, 'JACOBIAN_LENS', commonLayers);
    const logitSeries = seriesFor(artifact, token, 'LOGIT_LENS', commonLayers);
    panel.append(overlayCard(artifact, token, commonLayers, jacobianSeries, logitSeries));
  }

  function schedule() {
    if (runtime.scheduled) return;
    runtime.scheduled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      runtime.scheduled = false;
      render();
    }));
  }

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.id !== 'import-form' || event.submitter?.value === 'cancel') return;
    const file = $('#import-files')?.files?.[0];
    if (!file) return;
    try {
      const value = JSON.parse(await file.text());
      const artifact = isArtifact(value) ? value : value?.artifact || value?.run || value?.data || normalizeNative(value, file.name);
      if (isArtifact(artifact)) runtime.artifact = artifact;
    } catch {
      // The normal import path owns user-facing errors.
    }
    schedule();
  });

  document.addEventListener('click', (event) => {
    if (event.target.closest('.token, .layer-button, [data-level], [data-nav], #details-button, #load-demo')) schedule();
  });
  document.addEventListener('change', (event) => {
    if (event.target.closest('#lens-select, #language')) schedule();
  });

  window.addEventListener('DOMContentLoaded', () => {
    runtime.artifact = artifactFromSession();
    ensurePanel();
    const observe = ['#tokens', '#layer-rail', '#candidate-list'];
    observe.forEach((selector) => {
      const node = $(selector);
      if (!node) return;
      const observer = new MutationObserver(schedule);
      observer.observe(node, { childList: true, subtree: true });
    });
    const languageObserver = new MutationObserver(schedule);
    languageObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    schedule();
  });
})();
