(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const LENS_KEY = 'prismora.v4.lens';
  const runtime = {
    artifact: null,
    lens: localStorage.getItem(LENS_KEY) || 'JACOBIAN_LENS',
    selectedLayerByLens: {},
    scheduled: false,
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';

  const copy = {
    fr: {
      lens: 'Lentille',
      jacobian: 'Jacobian Lens',
      logit: 'Logit Lens',
      understand: 'Comprendre — lecture factuelle',
      guard: 'Cette lecture décrit uniquement les mesures présentes dans l’artifact. Elle n’infère ni intention, ni biais, ni censure, ni « pensée » cachée.',
      model: 'Modèle', run: 'Exécution', source: 'Source', generated: 'Tokens générés',
      available: 'Lentilles disponibles', measured: 'Couches mesurées', selectedToken: 'Token sélectionné',
      selectedLayer: 'Couche sélectionnée', topCandidate: 'Premier candidat mesuré',
      boundary: 'Frontière top-1 observée', gaps: 'Couches non mesurées', output: 'Surface générée',
      none: 'aucune', unavailable: 'non disponible', noArtifact: 'Chargez une démo ou un export pour produire la lecture factuelle.',
      stable: 'Aucun changement top-1 dans les couches mesurées.',
      firstChange: (layer, before, after) => `Premier changement top-1 observé à la couche ${layer} : « ${before} » → « ${after} ».`,
      probability: (token, probability) => `« ${token} » · p=${probability.toFixed(4)}`,
      gapList: (ranges) => ranges.map(([start, end]) => start === end ? `${start}` : `${start}–${end}`).join(', '),
    },
    en: {
      lens: 'Lens',
      jacobian: 'Jacobian Lens',
      logit: 'Logit Lens',
      understand: 'Understand — factual reading',
      guard: 'This reading describes only measurements present in the artifact. It does not infer intent, bias, censorship, or hidden “thought”.',
      model: 'Model', run: 'Run', source: 'Source', generated: 'Generated tokens',
      available: 'Available lenses', measured: 'Measured layers', selectedToken: 'Selected token',
      selectedLayer: 'Selected layer', topCandidate: 'First measured candidate',
      boundary: 'Observed top-1 boundary', gaps: 'Unmeasured layers', output: 'Generated surface',
      none: 'none', unavailable: 'unavailable', noArtifact: 'Load a demo or export to produce the factual reading.',
      stable: 'No top-1 change across measured layers.',
      firstChange: (layer, before, after) => `First observed top-1 change at layer ${layer}: “${before}” → “${after}”.`,
      probability: (token, probability) => `“${token}” · p=${probability.toFixed(4)}`,
      gapList: (ranges) => ranges.map(([start, end]) => start === end ? `${start}` : `${start}–${end}`).join(', '),
    },
  };

  const t = (key) => copy[language()][key];
  const isArtifact = (value) => value?.schema === 'prismora.run/v2';
  const generatedTokens = (artifact) => (artifact?.result?.tokens || []).filter((token) => token?.is_generated);
  const availableLenses = (artifact) => {
    const meta = Object.keys(artifact?.result?.meta?.layers_by_type || {});
    const resultTypes = (artifact?.result?.tokens || []).flatMap((token) => (token?.results || []).map((row) => row?.type)).filter(Boolean);
    return [...new Set([...meta, ...resultTypes])];
  };
  const layersFor = (artifact, lens) => artifact?.result?.meta?.layers_by_type?.[lens] || [];
  const resultFor = (token, lens) => (token?.results || []).find((row) => row?.type === lens) || null;
  const candidatesFor = (artifact, token, lens, layer) => {
    const layers = layersFor(artifact, lens);
    const index = layers.indexOf(layer);
    const result = resultFor(token, lens);
    if (index < 0 || !result) return [];
    return (result.top_tokens?.[index] || []).map((name, candidateIndex) => [
      String(name),
      Number(result.top_probs?.[index]?.[candidateIndex] || 0),
    ]);
  };

  function artifactFromSession() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
      return isArtifact(saved?.artifact) ? saved.artifact : null;
    } catch {
      return null;
    }
  }

  function currentTokenIndex() {
    const buttons = $$('#tokens .token');
    const index = buttons.findIndex((button) => button.classList.contains('active'));
    return index >= 0 ? index : 0;
  }

  function selectedToken() {
    return generatedTokens(runtime.artifact)[currentTokenIndex()] || generatedTokens(runtime.artifact)[0] || null;
  }

  function chooseLens() {
    const lenses = availableLenses(runtime.artifact);
    if (!lenses.length) return null;
    if (!lenses.includes(runtime.lens)) {
      runtime.lens = lenses.includes('JACOBIAN_LENS') ? 'JACOBIAN_LENS' : lenses[0];
      localStorage.setItem(LENS_KEY, runtime.lens);
    }
    return runtime.lens;
  }

  function defaultLayer(artifact, token, lens) {
    const measured = layersFor(artifact, lens);
    return [...measured].reverse().find((layer) => candidatesFor(artifact, token, lens, layer).length) ?? measured.at(-1) ?? null;
  }

  function sparsePositions(measured) {
    if (measured.length > 24) return measured.map((_, index) => 4 + (index / Math.max(1, measured.length - 1)) * 92);
    if (!measured.length) return [];
    const min = measured[0];
    const max = measured.at(-1);
    return measured.map((layer) => 4 + ((layer - min) / Math.max(1, max - min)) * 92);
  }

  function labelVisible(layer, index, count, selectedLayer) {
    return count <= 24 || index === 0 || index === count - 1 || layer === selectedLayer || layer % 8 === 0;
  }

  function ensureLensSelector() {
    const head = $('#jlens .jlens-head');
    if (!head) return null;
    let select = $('#lens-select');
    if (!select) {
      const oldBadge = [...head.querySelectorAll('.badge')].find((badge) => badge.id !== 'badge-measured');
      select = document.createElement('select');
      select.id = 'lens-select';
      select.className = 'badge lens-select';
      select.setAttribute('aria-label', t('lens'));
      if (oldBadge) oldBadge.replaceWith(select);
      else head.append(select);
      select.addEventListener('change', () => {
        runtime.lens = select.value;
        runtime.selectedLayerByLens[runtime.lens] = null;
        localStorage.setItem(LENS_KEY, runtime.lens);
        renderInstrument();
      });
    }

    const lenses = availableLenses(runtime.artifact);
    select.replaceChildren(...lenses.map((lens) => {
      const option = document.createElement('option');
      option.value = lens;
      option.textContent = lens === 'LOGIT_LENS' ? t('logit') : lens === 'JACOBIAN_LENS' ? t('jacobian') : lens;
      return option;
    }));
    select.disabled = lenses.length < 2;
    if (lenses.includes(runtime.lens)) select.value = runtime.lens;
    select.setAttribute('aria-label', t('lens'));
    return select;
  }

  function renderRail(artifact, token, lens, selectedLayer) {
    const measured = layersFor(artifact, lens);
    const positions = sparsePositions(measured);
    const rail = $('#layer-rail');
    if (!rail) return;
    rail.replaceChildren();
    rail.classList.toggle('dense', measured.length > 24);

    const line = document.createElement('div');
    line.className = 'layer-line';
    rail.append(line);

    measured.forEach((layer, index) => {
      if (index && layer - measured[index - 1] > 1) {
        const left = positions[index - 1] + 1;
        const right = positions[index] - 1;
        const gap = document.createElement('div');
        gap.className = 'layer-gap';
        gap.style.left = `${left}%`;
        gap.style.width = `${Math.max(0, right - left)}%`;
        rail.append(gap);
        const label = document.createElement('span');
        label.className = 'layer-gap-label';
        label.style.left = `${(left + right) / 2}%`;
        label.textContent = language() === 'fr'
          ? `couches ${measured[index - 1] + 1}–${layer - 1} non mesurées`
          : `layers ${measured[index - 1] + 1}–${layer - 1} unmeasured`;
        rail.append(label);
      }

      const button = document.createElement('button');
      button.type = 'button';
      button.className = `layer-button${layer === selectedLayer ? ' active' : ''}`;
      button.style.left = `${positions[index]}%`;
      button.setAttribute('aria-label', `${language() === 'fr' ? 'couche' : 'layer'} ${layer}`);
      button.addEventListener('click', () => {
        runtime.selectedLayerByLens[lens] = layer;
        renderInstrument();
      });
      rail.append(button);

      const number = document.createElement('span');
      number.className = 'layer-number';
      number.style.left = `${positions[index]}%`;
      number.textContent = layer;
      number.hidden = !labelVisible(layer, index, measured.length, selectedLayer);
      rail.append(number);
    });
  }

  function renderCandidates(artifact, token, lens, selectedLayer) {
    const rows = candidatesFor(artifact, token, lens, selectedLayer);
    const title = $('#top-title');
    if (title) title.textContent = `Top ${Math.min(8, rows.length)} · ${language() === 'fr' ? 'couche' : 'layer'} ${selectedLayer ?? '—'}`;
    const list = $('#candidate-list');
    if (!list) return rows;
    list.replaceChildren();
    const max = Math.max(...rows.map((row) => row[1]), 0.00001);
    rows.slice(0, 8).forEach(([name, probability], index) => {
      const candidate = document.createElement('div');
      candidate.className = 'candidate';
      candidate.innerHTML = '<span></span><strong></strong><span class="bar-track"><i class="bar"></i></span><span></span>';
      candidate.children[0].textContent = index + 1;
      candidate.children[1].textContent = name;
      candidate.querySelector('.bar').style.width = `${Math.max(2, probability / max * 100)}%`;
      candidate.children[3].textContent = probability.toFixed(3);
      list.append(candidate);
    });
    return rows;
  }

  function renderTrajectory(artifact, token, lens, selectedLayer, selectedCandidate) {
    const measured = layersFor(artifact, lens);
    const positions = sparsePositions(measured);
    const chart = $('#trajectory');
    if (!chart) return;
    chart.replaceChildren();
    chart.classList.toggle('dense', measured.length > 24);

    measured.forEach((layer, index) => {
      if (index && layer - measured[index - 1] > 1) {
        const left = positions[index - 1] + 1;
        const right = positions[index] - 1;
        const gap = document.createElement('div');
        gap.className = 'trajectory-gap';
        gap.style.left = `${left}%`;
        gap.style.width = `${Math.max(0, right - left)}%`;
        gap.innerHTML = language() === 'fr' ? 'silence<br>non mesuré' : 'unmeasured<br>gap';
        chart.append(gap);
      }

      const found = candidatesFor(artifact, token, lens, layer).find(([name]) => name === selectedCandidate);
      if (found) {
        const point = document.createElement('span');
        point.className = 'point';
        point.style.left = `${positions[index]}%`;
        point.style.bottom = `${18 + Math.min(1, found[1]) * 145}px`;
        point.title = `L${layer} · ${found[1].toFixed(4)}`;
        chart.append(point);
      }

      const label = document.createElement('span');
      label.className = 'trajectory-label';
      label.style.left = `${positions[index]}%`;
      label.textContent = layer;
      label.hidden = !labelVisible(layer, index, measured.length, selectedLayer);
      chart.append(label);
    });
  }

  function unmeasuredRanges(measured) {
    const ranges = [];
    for (let index = 1; index < measured.length; index += 1) {
      const start = measured[index - 1] + 1;
      const end = measured[index] - 1;
      if (start <= end) ranges.push([start, end]);
    }
    return ranges;
  }

  function firstTopOneChange(artifact, token, lens) {
    const measured = layersFor(artifact, lens);
    let previous = null;
    for (const layer of measured) {
      const current = candidatesFor(artifact, token, lens, layer)[0]?.[0] ?? null;
      if (previous !== null && current !== null && current !== previous) return { layer, before: previous, after: current };
      if (current !== null) previous = current;
    }
    return null;
  }

  function ensureUnderstandPanel() {
    const screen = $('.screen[data-screen="explore"]');
    if (!screen) return null;
    let panel = $('#understand-panel');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'understand-panel';
      panel.className = 'understand-panel card';
      const legacy = $('#legacy-explore');
      screen.insertBefore(panel, legacy || null);
    }
    return panel;
  }

  function fact(label, value) {
    const row = document.createElement('div');
    row.className = 'understand-fact';
    const term = document.createElement('span');
    term.textContent = label;
    const data = document.createElement('strong');
    data.textContent = value;
    row.append(term, data);
    return row;
  }

  function renderUnderstand(artifact, token, lens, selectedLayer, rows) {
    const panel = ensureUnderstandPanel();
    if (!panel) return;
    panel.replaceChildren();

    const title = document.createElement('h2');
    title.textContent = t('understand');
    panel.append(title);

    const guard = document.createElement('p');
    guard.className = 'understand-guard';
    guard.textContent = t('guard');
    panel.append(guard);

    if (!artifact || !token || !lens) {
      const empty = document.createElement('p');
      empty.textContent = t('noArtifact');
      panel.append(empty);
      return;
    }

    const measured = layersFor(artifact, lens);
    const ranges = unmeasuredRanges(measured);
    const change = firstTopOneChange(artifact, token, lens);
    const top = rows[0];
    const facts = document.createElement('div');
    facts.className = 'understand-grid';
    facts.append(
      fact(t('model'), artifact?.request?.model?.model_id || t('unavailable')),
      fact(t('run'), artifact.run_id || 'local'),
      fact(t('source'), artifact?.provenance?.backend || artifact?.request?.backend || t('unavailable')),
      fact(t('generated'), String(generatedTokens(artifact).length)),
      fact(t('available'), availableLenses(artifact).join(', ') || t('none')),
      fact(t('measured'), `${measured.length}${measured.length ? ` · ${measured[0]}–${measured.at(-1)}` : ''}`),
      fact(t('selectedToken'), token.token || t('unavailable')),
      fact(t('selectedLayer'), selectedLayer === null ? t('unavailable') : String(selectedLayer)),
      fact(t('topCandidate'), top ? t('probability')(top[0], top[1]) : t('unavailable')),
      fact(t('gaps'), ranges.length ? t('gapList')(ranges) : t('none')),
    );
    panel.append(facts);

    const boundary = document.createElement('div');
    boundary.className = 'understand-boundary';
    const boundaryTitle = document.createElement('strong');
    boundaryTitle.textContent = t('boundary');
    const boundaryText = document.createElement('p');
    boundaryText.textContent = change ? t('firstChange')(change.layer, change.before, change.after) : t('stable');
    boundary.append(boundaryTitle, boundaryText);
    panel.append(boundary);

    const output = document.createElement('details');
    output.className = 'understand-output';
    const summary = document.createElement('summary');
    summary.textContent = t('output');
    const pre = document.createElement('pre');
    pre.textContent = artifact?.result?.done?.completion || artifact?.result?.completion || t('unavailable');
    output.append(summary, pre);
    panel.append(output);
  }

  function renderInstrument() {
    const artifact = runtime.artifact || artifactFromSession();
    if (!artifact) {
      runtime.artifact = null;
      renderUnderstand(null, null, null, null, []);
      return;
    }
    runtime.artifact = artifact;
    const lens = chooseLens();
    const token = selectedToken();
    if (!lens || !token || $('#jlens')?.hidden) {
      renderUnderstand(artifact, token, lens, null, []);
      return;
    }

    ensureLensSelector();
    const current = runtime.selectedLayerByLens[lens];
    const measured = layersFor(artifact, lens);
    const selectedLayer = measured.includes(current) && candidatesFor(artifact, token, lens, current).length
      ? current
      : defaultLayer(artifact, token, lens);
    runtime.selectedLayerByLens[lens] = selectedLayer;

    renderRail(artifact, token, lens, selectedLayer);
    const rows = renderCandidates(artifact, token, lens, selectedLayer);
    renderTrajectory(artifact, token, lens, selectedLayer, rows[0]?.[0] || token.token);
    renderUnderstand(artifact, token, lens, selectedLayer, rows);
  }

  function scheduleRender() {
    if (runtime.scheduled) return;
    runtime.scheduled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      runtime.scheduled = false;
      renderInstrument();
    }));
  }

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.id !== 'import-form') return;
    if (event.submitter?.value === 'cancel') return;
    const input = $('#import-files');
    const file = input?.files?.[0];
    if (!file) return;
    try {
      const value = JSON.parse(await file.text());
      const artifact = isArtifact(value) ? value : value?.artifact || value?.run || value?.data;
      if (isArtifact(artifact)) runtime.artifact = artifact;
    } catch {
      // The normal import path will report incompatible files.
    }
    scheduleRender();
  });

  document.addEventListener('click', (event) => {
    if (event.target.closest('.token')) {
      const index = $$('#tokens .token').indexOf(event.target.closest('.token'));
      Object.keys(runtime.selectedLayerByLens).forEach((lens) => { runtime.selectedLayerByLens[lens] = null; });
      if (index >= 0) scheduleRender();
      return;
    }
    if (event.target.closest('[data-level], #details-button, [data-nav]')) scheduleRender();
  });

  window.addEventListener('DOMContentLoaded', () => {
    runtime.artifact = artifactFromSession();
    ensureUnderstandPanel();

    const jlens = $('#jlens');
    if (jlens) {
      const observer = new MutationObserver(() => scheduleRender());
      observer.observe(jlens, { attributes: true, attributeFilter: ['hidden'] });
    }

    const languageObserver = new MutationObserver(() => scheduleRender());
    languageObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    scheduleRender();
  });
})();
