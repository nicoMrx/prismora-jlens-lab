(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const $ = (selector, root = document) => root.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';

  const state = {
    a: null,
    b: null,
    aLabel: null,
    bLabel: null,
    result: null,
    scheduled: false,
  };

  const copy = {
    fr: {
      title: 'Comparer deux artifacts choisis',
      subtitle: 'La comparaison est calculée localement à partir des fichiers sélectionnés. Aucun export n’est archivé automatiquement.',
      useLoaded: 'Utiliser l’artifact chargé comme A',
      chooseA: 'Choisir le fichier A', chooseB: 'Choisir le fichier B',
      artifactA: 'Artifact A', artifactB: 'Artifact B', missing: 'non sélectionné',
      lens: 'Lentille commune', scope: 'Portée', tolerance: 'Tolérance de probabilité',
      all: 'Prompt + réponse générée', prompt: 'Contexte du prompt', generated: 'Réponse générée par rang ordinal',
      compare: 'Comparer A et B', incompatible: 'Les deux artifacts ne partagent aucune lentille mesurée.',
      invalid: 'Le fichier ne contient pas un artifact Prismora ou un export Neuronpedia compatible.',
      needBoth: 'Sélectionnez deux artifacts compatibles pour lancer la comparaison.',
      localBadge: 'Comparaison locale déterministe', why: 'Pourquoi cette phrase ?',
      evidence: 'Preuves', noCommonLayers: 'Aucune couche commune n’est mesurée pour cette lentille.',
      sameSurface: 'La surface générée est identique pour cette paire.',
      differentSurface: 'La surface générée diffère entre A et B.',
      promptScope: 'Portée : contexte du prompt ; les tokens sont alignés uniquement lorsque leur position et leur identifiant sont identiques.',
      generatedScope: 'Portée : réponse générée ; les tokens sont alignés uniquement par rang ordinal, sans alignement sémantique.',
      noTop1: 'Aucune divergence top‑1 n’est mesurée dans la portée sélectionnée.',
      firstTop1: (layer, position) => `La première divergence top‑1 est mesurée à la couche ${layer}, position ${position}.`,
      noStrict: 'Aucune divergence stricte top‑k/probabilité n’est mesurée dans la portée sélectionnée.',
      firstStrict: (layer, position) => `La première divergence stricte top‑k/probabilité est mesurée à la couche ${layer}, position ${position}.`,
      intervention: (layers) => `L’artifact B déclare une intervention sur ${layers}.`,
      causal: 'Une divergence mesurée après une intervention déclarée ne constitue pas, à elle seule, une preuve causale.',
      missingCells: (count) => `${count} cellule(s) mesurée(s) manquent dans l’une des deux observations.`,
      generatedLength: 'Les deux réponses n’ont pas le même nombre de tokens générés ; seuls les rangs communs sont comparés.',
      promptAlignment: 'Certains tokens du prompt ne partagent pas le même identifiant et ne sont pas alignés.',
      run: 'Exécution', model: 'Modèle', file: 'Fichier', loaded: 'artifact chargé',
    },
    en: {
      title: 'Compare two selected artifacts',
      subtitle: 'The comparison is computed locally from the selected files. No export is archived automatically.',
      useLoaded: 'Use the loaded artifact as A',
      chooseA: 'Choose file A', chooseB: 'Choose file B',
      artifactA: 'Artifact A', artifactB: 'Artifact B', missing: 'not selected',
      lens: 'Common lens', scope: 'Scope', tolerance: 'Probability tolerance',
      all: 'Prompt + generated answer', prompt: 'Prompt context', generated: 'Generated answer by ordinal rank',
      compare: 'Compare A and B', incompatible: 'The two artifacts share no measured lens.',
      invalid: 'The file does not contain a compatible Prismora artifact or Neuronpedia export.',
      needBoth: 'Select two compatible artifacts to start the comparison.',
      localBadge: 'Deterministic local comparison', why: 'Why this sentence?',
      evidence: 'Evidence', noCommonLayers: 'No common layer is measured for this lens.',
      sameSurface: 'The generated surface is identical for this pair.',
      differentSurface: 'The generated surface differs between A and B.',
      promptScope: 'Scope: prompt context; tokens are aligned only when position and token id are identical.',
      generatedScope: 'Scope: generated answer; tokens are aligned only by ordinal rank, without semantic alignment.',
      noTop1: 'No top‑1 divergence is measured in the selected scope.',
      firstTop1: (layer, position) => `The first top‑1 divergence is measured at layer ${layer}, position ${position}.`,
      noStrict: 'No strict top‑k/probability divergence is measured in the selected scope.',
      firstStrict: (layer, position) => `The first strict top‑k/probability divergence is measured at layer ${layer}, position ${position}.`,
      intervention: (layers) => `Artifact B declares an intervention at ${layers}.`,
      causal: 'A measured divergence after a declared intervention does not, by itself, establish causal proof.',
      missingCells: (count) => `${count} measured cell(s) are missing from one of the observations.`,
      generatedLength: 'The answers have different generated-token counts; only shared ordinal ranks are compared.',
      promptAlignment: 'Some prompt tokens do not share the same identifier and are not aligned.',
      run: 'Run', model: 'Model', file: 'File', loaded: 'loaded artifact',
    },
  };

  const t = (key) => copy[language()][key] ?? key;
  const isArtifact = (value) => value?.schema === 'prismora.run/v2' && Array.isArray(value?.result?.tokens);

  function sessionArtifact() {
    try {
      const payload = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
      return isArtifact(payload?.artifact) ? payload.artifact : null;
    } catch {
      return null;
    }
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
        backend: 'neuronpedia_export', prompt: value.kind === 'completion' ? String(value.prompt || '') : last('user'),
        messages, model: { model_id: value.modelId || value.meta?.model || 'unknown-model' },
      },
      result: {
        tokens: value.tokens, meta: { ...value.meta, layers_by_type: layersByType },
        done: { completion: value.kind === 'chat' ? last('assistant') : value.tokens.filter((token) => token?.is_generated).map((token) => token?.token || '').join('') },
      },
      coverage: { captured_layers: layersByType.JACOBIAN_LENS || [], lens_types: Object.keys(layersByType) },
      provenance: { backend: 'neuronpedia_export', source: 'local-file', original_filename: filename },
    };
  }

  function unwrap(value, filename) {
    const candidate = isArtifact(value) ? value : value?.artifact || value?.run || value?.data || normalizeNative(value, filename);
    return isArtifact(candidate) ? candidate : null;
  }

  const layersByType = (artifact) => artifact?.result?.meta?.layers_by_type || {};
  const lenses = (artifact) => Object.keys(layersByType(artifact));
  const completion = (artifact) => artifact?.result?.done?.completion || artifact?.result?.completion || '';
  const resultFor = (token, lens) => (token?.results || []).find((row) => row?.type === lens) || null;

  function topAt(artifact, token, lens, layer) {
    const measured = layersByType(artifact)[lens] || [];
    const index = measured.indexOf(layer);
    const result = resultFor(token, lens);
    if (index < 0 || !result) return null;
    const names = result.top_tokens?.[index];
    const probabilities = result.top_probs?.[index];
    if (!Array.isArray(names) || !names.length || !Array.isArray(probabilities) || !probabilities.length) return null;
    const topTokens = names.map((name) => String(name));
    const topProbs = probabilities.map((probability) => Number(probability));
    if (topProbs.some((probability) => !Number.isFinite(probability))) return null;
    return { token: topTokens[0], probability: topProbs[0], top_tokens: topTokens, top_probs: topProbs };
  }

  function sameArray(left, right) {
    return left.length === right.length && left.every((value, index) => value === right[index]);
  }

  function sameNumericArrayWithinTolerance(left, right, tolerance) {
    return left.length === right.length
      && left.every((value, index) => Math.abs(value - right[index]) <= tolerance);
  }

  function strictCellChanged(left, right, tolerance) {
    return !sameArray(left.top_tokens, right.top_tokens)
      || !sameNumericArrayWithinTolerance(left.top_probs, right.top_probs, tolerance);
  }

  function promptPairs(a, b) {
    const left = (a?.result?.tokens || []).filter((token) => !token?.is_generated);
    const right = (b?.result?.tokens || []).filter((token) => !token?.is_generated);
    const rightByKey = new Map(right.map((token) => [`${token.position}:${token.id}`, token]));
    const pairs = left.map((token) => ({ a: token, b: rightByKey.get(`${token.position}:${token.id}`) })).filter((pair) => pair.b);
    return { pairs, unaligned: Math.max(left.length, right.length) - pairs.length };
  }

  function generatedPairs(a, b) {
    const left = (a?.result?.tokens || []).filter((token) => token?.is_generated);
    const right = (b?.result?.tokens || []).filter((token) => token?.is_generated);
    return {
      pairs: Array.from({ length: Math.min(left.length, right.length) }, (_, index) => ({ a: left[index], b: right[index], ordinal: index + 1 })),
      unequal: left.length !== right.length,
    };
  }

  function interventionLayers(artifact) {
    const request = artifact?.request || {};
    const intervention = request.intervention || {};
    const rows = [];
    if (Number.isInteger(intervention.layer)) rows.push(intervention.layer);
    if (Array.isArray(intervention.layers)) rows.push(...intervention.layers.filter(Number.isInteger));
    if (Array.isArray(request.steerLayers)) rows.push(...request.steerLayers.filter(Number.isInteger));
    return [...new Set(rows)].sort((a, b) => a - b);
  }

  function compareArtifacts(a, b, lens, scope, tolerance) {
    const commonLayers = (layersByType(a)[lens] || []).filter((layer) => (layersByType(b)[lens] || []).includes(layer)).sort((x, y) => x - y);
    const prompt = promptPairs(a, b);
    const generated = generatedPairs(a, b);
    const groups = [];
    if (scope === 'all' || scope === 'prompt_fixed') groups.push(...prompt.pairs.map((pair) => ({ ...pair, scope: 'prompt', position: pair.a.position })));
    if (scope === 'all' || scope === 'generated_ordinal') groups.push(...generated.pairs.map((pair) => ({ ...pair, scope: 'generated', position: pair.ordinal })));

    let firstTop1 = null;
    let firstStrict = null;
    let missing = 0;
    for (const layer of commonLayers) {
      for (const pair of groups) {
        const left = topAt(a, pair.a, lens, layer);
        const right = topAt(b, pair.b, lens, layer);
        if (!left || !right) { missing += 1; continue; }
        const evidence = { layer, scope: pair.scope, position: pair.position, a: left, b: right };
        if (!firstTop1 && left.token !== right.token) firstTop1 = evidence;
        if (!firstStrict && strictCellChanged(left, right, tolerance)) firstStrict = evidence;
      }
    }

    return {
      lens, scope, tolerance, commonLayers, firstTop1, firstStrict, missing,
      sameSurface: completion(a) === completion(b), promptUnaligned: prompt.unaligned,
      generatedUnequal: generated.unequal, interventionLayers: interventionLayers(b),
    };
  }

  function sentence(text, severity, evidence) {
    return { text, severity, evidence };
  }

  function narrative(result) {
    const rows = [sentence(result.sameSurface ? t('sameSurface') : t('differentSurface'), result.sameSurface ? 'info' : 'warning', { same: result.sameSurface })];
    if (result.scope === 'all' || result.scope === 'prompt_fixed') rows.push(sentence(t('promptScope'), 'info', { unaligned: result.promptUnaligned }));
    if (result.scope === 'all' || result.scope === 'generated_ordinal') rows.push(sentence(t('generatedScope'), 'warning', { unequal_length: result.generatedUnequal }));
    if (!result.commonLayers.length) rows.push(sentence(t('noCommonLayers'), 'warning', { lens: result.lens }));
    else {
      rows.push(sentence(result.firstTop1 ? t('firstTop1')(result.firstTop1.layer, result.firstTop1.position) : t('noTop1'), result.firstTop1 ? 'warning' : 'info', result.firstTop1 || { common_layers: result.commonLayers }));
      rows.push(sentence(result.firstStrict ? t('firstStrict')(result.firstStrict.layer, result.firstStrict.position) : t('noStrict'), result.firstStrict ? 'warning' : 'info', result.firstStrict || { tolerance: result.tolerance }));
    }
    if (result.interventionLayers.length) rows.push(sentence(t('intervention')(result.interventionLayers.join(', ')), 'warning', { layers: result.interventionLayers }));
    if (result.missing) rows.push(sentence(t('missingCells')(result.missing), 'warning', { missing_cells: result.missing }));
    if (result.generatedUnequal) rows.push(sentence(t('generatedLength'), 'warning', {}));
    if (result.promptUnaligned) rows.push(sentence(t('promptAlignment'), 'warning', { unaligned: result.promptUnaligned }));
    rows.push(sentence(t('causal'), 'warning', { causal_claim: false }));
    return rows;
  }

  function artifactLabel(artifact, filename) {
    if (!artifact) return t('missing');
    return `${artifact.run_id || 'local'} · ${artifact?.request?.model?.model_id || 'model'} · ${filename || artifact?.provenance?.original_filename || t('loaded')}`;
  }

  function renderResult(root) {
    const target = $('.user-comparison-result', root);
    target.replaceChildren();
    if (!state.result) return;
    const badge = document.createElement('span');
    badge.className = 'explorer-pair-badge';
    badge.textContent = t('localBadge');
    const list = document.createElement('div');
    list.className = 'explorer-sentence-list';
    narrative(state.result).forEach((row) => {
      const card = document.createElement('article');
      card.className = `explorer-sentence ${row.severity}`;
      const text = document.createElement('p');
      text.textContent = row.text;
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = t('why');
      const evidence = document.createElement('pre');
      evidence.textContent = `${t('evidence')}\n${JSON.stringify(row.evidence || {}, null, 2)}`;
      details.append(summary, evidence);
      card.append(text, details);
      list.append(card);
    });
    target.append(badge, list);
  }

  function updateControls(root) {
    $('.user-comparison-a-value', root).textContent = artifactLabel(state.a, state.aLabel);
    $('.user-comparison-b-value', root).textContent = artifactLabel(state.b, state.bLabel);
    const lensSelect = $('.user-comparison-lens', root);
    const common = state.a && state.b ? lenses(state.a).filter((lens) => lenses(state.b).includes(lens)) : [];
    const previous = lensSelect.value;
    lensSelect.replaceChildren(...common.map((lens) => {
      const option = document.createElement('option'); option.value = lens; option.textContent = lens; return option;
    }));
    if (common.includes(previous)) lensSelect.value = previous;
    $('.user-comparison-submit', root).disabled = !(state.a && state.b && common.length);
    $('.user-comparison-message', root).textContent = state.a && state.b && !common.length ? t('incompatible') : '';
    renderResult(root);
  }

  async function readSide(file, side, root) {
    try {
      const artifact = unwrap(JSON.parse(await file.text()), file.name);
      if (!artifact) throw new Error(t('invalid'));
      state[side] = artifact;
      state[`${side}Label`] = file.name;
      state.result = null;
      updateControls(root);
    } catch (error) {
      $('.user-comparison-message', root).textContent = error.message || t('invalid');
    }
  }

  function buildWorkbench(panel) {
    const section = document.createElement('section');
    section.className = 'user-comparison-workbench';
    section.innerHTML = `
      <div class="user-comparison-heading"><h3></h3><p></p></div>
      <div class="user-comparison-artifacts">
        <article><span>${t('artifactA')}</span><strong class="user-comparison-a-value"></strong><label>${t('chooseA')}<input class="user-comparison-a" type="file" accept="application/json,.json"></label><button class="secondary user-comparison-loaded" type="button">${t('useLoaded')}</button></article>
        <article><span>${t('artifactB')}</span><strong class="user-comparison-b-value"></strong><label>${t('chooseB')}<input class="user-comparison-b" type="file" accept="application/json,.json"></label></article>
      </div>
      <div class="user-comparison-controls">
        <label>${t('lens')}<select class="user-comparison-lens"></select></label>
        <label>${t('scope')}<select class="user-comparison-scope"><option value="all">${t('all')}</option><option value="prompt_fixed">${t('prompt')}</option><option value="generated_ordinal">${t('generated')}</option></select></label>
        <label>${t('tolerance')}<input class="user-comparison-tolerance" type="number" min="0" step="0.0001" value="0"></label>
        <button class="primary user-comparison-submit" type="button">${t('compare')}</button>
      </div>
      <p class="user-comparison-message" role="status"></p>
      <div class="user-comparison-result"></div>`;
    $('h3', section).textContent = t('title');
    $('.user-comparison-heading p', section).textContent = t('subtitle');

    $('.user-comparison-loaded', section).addEventListener('click', () => {
      state.a = sessionArtifact(); state.aLabel = t('loaded'); state.result = null; updateControls(section);
    });
    $('.user-comparison-a', section).addEventListener('change', (event) => event.target.files?.[0] && readSide(event.target.files[0], 'a', section));
    $('.user-comparison-b', section).addEventListener('change', (event) => event.target.files?.[0] && readSide(event.target.files[0], 'b', section));
    $('.user-comparison-submit', section).addEventListener('click', () => {
      if (!state.a || !state.b) { $('.user-comparison-message', section).textContent = t('needBoth'); return; }
      state.result = compareArtifacts(
        state.a, state.b, $('.user-comparison-lens', section).value,
        $('.user-comparison-scope', section).value,
        Math.max(0, Number($('.user-comparison-tolerance', section).value) || 0),
      );
      $('.user-comparison-message', section).textContent = '';
      renderResult(section);
    });
    panel.append(section);
    updateControls(section);
  }

  function ensureWorkbench() {
    const panel = $('#explorer-compare-view');
    if (!panel) return;
    const workbench = $('.user-comparison-workbench', panel);
    if (!workbench) buildWorkbench(panel);
    else updateControls(workbench);
  }

  function schedule() {
    if (state.scheduled) return;
    state.scheduled = true;
    requestAnimationFrame(() => {
      state.scheduled = false;
      if (!state.a) { state.a = sessionArtifact(); state.aLabel = t('loaded'); }
      ensureWorkbench();
    });
  }

  window.addEventListener('DOMContentLoaded', () => {
    state.a = sessionArtifact();
    state.aLabel = state.a ? t('loaded') : null;
    const explore = $('.screen[data-screen="explore"]') || document.body;
    new MutationObserver(() => {
      const panel = $('#explorer-compare-view');
      if (panel && !$('.user-comparison-workbench', panel)) schedule();
    }).observe(explore, { childList: true, subtree: true });
    new MutationObserver(() => {
      const panel = $('#explorer-compare-view');
      const old = panel && $('.user-comparison-workbench', panel);
      if (old) old.remove();
      schedule();
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    schedule();
  });
})();
