(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const $ = (selector, root = document) => root.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let scheduled = false;
  const comparison = { a: null, b: null };

  const copy = {
    fr: {
      layers: 'Couches capturées', operation: 'Opération', unavailable: 'non disponible',
      synthetic: 'synthétique', steer: 'steer', swap: 'swap', ablation: 'ablation',
      strictBadge: 'Paire A/B stricte',
      strictText: 'Même identité de modèle, même backend, mêmes paramètres de génération et de lecture, même couverture, même prompt et mêmes identifiants de tokens du prompt.',
      crossBadge: 'Comparaison exploratoire inter-modèles',
      crossText: 'Les couches portant le même numéro ne sont pas supposées équivalentes entre ces modèles. La première divergence ne doit pas être interprétée comme un effet causal comparable.',
      promptBadge: 'Comparaison exploratoire · contexte différent',
      promptText: 'Le modèle est identique, mais le prompt ou le contexte diffère. Les divergences mélangent l’effet du contexte et celui des autres paramètres.',
      tokenBadge: 'Compatibilité partielle · tokenisation différente',
      tokenText: 'Le modèle et le prompt textuel correspondent, mais les identifiants des tokens du prompt diffèrent. L’alignement strict n’est pas garanti.',
      configBadge: 'Compatibilité partielle · configuration différente',
      configText: 'Le modèle textuel et le prompt correspondent, mais les révisions, paramètres de génération, paramètres de lecture ou la couverture diffèrent.',
      modelA: 'Modèle A', modelB: 'Modèle B',
    },
    en: {
      layers: 'Captured layers', operation: 'Operation', unavailable: 'unavailable',
      synthetic: 'synthetic', steer: 'steer', swap: 'swap', ablation: 'ablation',
      strictBadge: 'Strict A/B pair',
      strictText: 'Same model identity, backend, generation and readout settings, coverage, prompt, and prompt-token identifiers.',
      crossBadge: 'Exploratory cross-model comparison',
      crossText: 'Layers sharing a number are not assumed to be equivalent across these models. The first divergence must not be interpreted as a comparable causal effect.',
      promptBadge: 'Exploratory comparison · different context',
      promptText: 'The model is identical, but the prompt or context differs. Divergences mix context effects with other parameter changes.',
      tokenBadge: 'Partial compatibility · different tokenization',
      tokenText: 'The model and prompt text match, but prompt-token identifiers differ. Strict alignment is not guaranteed.',
      configBadge: 'Partial compatibility · different configuration',
      configText: 'The model label and prompt match, but revisions, generation settings, readout settings, or coverage differ.',
      modelA: 'Model A', modelB: 'Model B',
    },
  };
  const t = (key) => copy[language()][key];
  const isArtifact = (value) => value?.schema === 'prismora.run/v2' && Array.isArray(value?.result?.tokens);

  function sessionPayload() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null'); }
    catch { return null; }
  }

  function artifact() {
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
        done: { completion: value.kind === 'chat' ? last('assistant') : '' },
      },
      coverage: { captured_layers: layersByType.JACOBIAN_LENS || [], lens_types: Object.keys(layersByType) },
      provenance: { backend: 'neuronpedia_export', source: 'local-file', original_filename: filename },
    };
  }

  function unwrap(value, filename) {
    const candidate = isArtifact(value) ? value : value?.artifact || value?.run || value?.data || normalizeNative(value, filename);
    return isArtifact(candidate) ? candidate : null;
  }

  function measuredLayers(value) {
    const layersByType = value?.result?.meta?.layers_by_type || {};
    return [...new Set(Object.values(layersByType).flat().filter(Number.isFinite))].sort((a, b) => a - b);
  }

  function compactRanges(layers) {
    if (!layers.length) return t('unavailable');
    const ranges = [];
    let start = layers[0];
    let previous = layers[0];
    for (const layer of layers.slice(1)) {
      if (layer === previous + 1) {
        previous = layer;
        continue;
      }
      ranges.push(start === previous ? `${start}` : `${start}–${previous}`);
      start = layer;
      previous = layer;
    }
    ranges.push(start === previous ? `${start}` : `${start}–${previous}`);
    return `${layers.length} · ${ranges.join(', ')}`;
  }

  function factValue(panel, label) {
    return [...panel.querySelectorAll('.explorer-fact')]
      .find((row) => row.querySelector('span')?.textContent.trim() === label)
      ?.querySelector('strong') || null;
  }

  function operationSummary(value) {
    const request = value?.request || {};
    const explicit = request.intervention || {};
    const operations = [];
    if (typeof explicit.type === 'string' && explicit.type.trim()) {
      operations.push(explicit.type === 'synthetic' ? t('synthetic') : explicit.type.trim());
    }
    const steerTokens = explicit.steerTokens || request.steerTokens || [];
    const swapToken = explicit.swapToken || request.swapToken || null;
    const ablation = explicit.steerAblate ?? request.steerAblate ?? false;
    if ((Array.isArray(steerTokens) && steerTokens.length) || (!Array.isArray(steerTokens) && steerTokens)) operations.push(t('steer'));
    if (swapToken) operations.push(t('swap'));
    if (ablation) operations.push(t('ablation'));
    return [...new Set(operations)].join(' + ') || t('unavailable');
  }

  const modelId = (value) => String(value?.request?.model?.model_id || 'unknown-model');

  function promptText(value) {
    if (typeof value?.request?.prompt === 'string') return value.request.prompt;
    const messages = Array.isArray(value?.request?.chat)
      ? value.request.chat
      : (Array.isArray(value?.request?.messages) ? value.request.messages : []);
    return JSON.stringify(messages.map((message) => ({ role: message?.role, content: message?.content })));
  }

  function promptTokenIds(value) {
    return (value?.result?.tokens || [])
      .filter((token) => !token?.is_generated)
      .map((token) => String(token?.id ?? 'missing'));
  }

  function sameArray(left, right) {
    return left.length === right.length && left.every((value, index) => value === right[index]);
  }

  function stableValue(value) {
    if (Array.isArray(value)) return value.map(stableValue);
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
    }
    return value;
  }

  function sameValue(left, right) {
    return JSON.stringify(stableValue(left)) === JSON.stringify(stableValue(right));
  }

  function comparabilityConfiguration(value) {
    const request = value?.request || {};
    const model = request.model || {};
    const provenance = value?.provenance || {};
    const meta = value?.result?.meta || {};
    const coverage = value?.coverage || {};
    return {
      backend: request.backend,
      model: {
        model_id: model.model_id,
        revision: model.revision ?? provenance.model_revision ?? meta.model_revision,
        tokenizer_revision: model.tokenizer_revision ?? provenance.tokenizer_revision ?? meta.tokenizer_revision,
        lens_id: model.lens_id ?? provenance.lens_id ?? meta.lens_name_or_path,
        lens_revision: model.lens_revision ?? provenance.lens_revision ?? meta.lens_revision,
        precision: model.precision ?? meta.precision,
        quantization: model.quantization ?? meta.quantization,
      },
      generation: request.generation || {},
      readout: request.readout || {},
      coverage: {
        status: coverage.status,
        source_tokens_total: coverage.source_tokens_total,
        transmitted_tokens: coverage.transmitted_tokens,
        instrumented_tokens: coverage.instrumented_tokens,
        instrumented_generated_tokens: coverage.instrumented_generated_tokens,
        truncated_tokens: coverage.truncated_tokens,
        requested_layers: coverage.requested_layers || [],
        captured_layers: coverage.captured_layers || [],
      },
    };
  }

  function compatibility() {
    if (!comparison.a || !comparison.b) return null;
    const sameModel = modelId(comparison.a) === modelId(comparison.b);
    const samePrompt = promptText(comparison.a) === promptText(comparison.b);
    const leftIds = promptTokenIds(comparison.a);
    const rightIds = promptTokenIds(comparison.b);
    const sameTokens = leftIds.length > 0 && sameArray(leftIds, rightIds);
    const sameConfiguration = sameValue(
      comparabilityConfiguration(comparison.a),
      comparabilityConfiguration(comparison.b),
    );
    if (sameModel && samePrompt && sameTokens && sameConfiguration) return { kind: 'strict', badge: t('strictBadge'), text: t('strictText') };
    if (!sameModel) return { kind: 'exploratory', badge: t('crossBadge'), text: t('crossText') };
    if (!samePrompt) return { kind: 'exploratory', badge: t('promptBadge'), text: t('promptText') };
    if (!sameConfiguration) return { kind: 'partial', badge: t('configBadge'), text: t('configText') };
    return { kind: 'partial', badge: t('tokenBadge'), text: t('tokenText') };
  }

  function renderCompatibility() {
    const workbench = $('.user-comparison-workbench');
    if (!workbench) return;
    let panel = $('.user-comparison-compatibility', workbench);
    if (!panel) {
      panel = document.createElement('section');
      panel.className = 'user-comparison-compatibility';
      workbench.insertBefore(panel, $('.user-comparison-controls', workbench) || null);
    }
    const result = compatibility();
    panel.hidden = !result;
    if (!result) return;
    panel.className = `user-comparison-compatibility ${result.kind}`;
    panel.replaceChildren();
    const badge = document.createElement('strong');
    badge.textContent = result.badge;
    const text = document.createElement('p');
    text.textContent = result.text;
    const meta = document.createElement('small');
    meta.textContent = `${t('modelA')} : ${modelId(comparison.a)} · ${t('modelB')} : ${modelId(comparison.b)}`;
    panel.append(badge, text, meta);
  }

  async function readComparisonFile(input, side) {
    const file = input.files?.[0];
    if (!file) return;
    try {
      comparison[side] = unwrap(JSON.parse(await file.text()), file.name);
    } catch {
      comparison[side] = null;
    }
    renderCompatibility();
  }

  function applyPolish() {
    const value = artifact();
    if (value) {
      const references = $('#explorer-references-view');
      if (references) {
        const target = factValue(references, t('layers'));
        const summary = compactRanges(measuredLayers(value));
        if (target && target.textContent !== summary) target.textContent = summary;
      }

      const interventions = $('#explorer-interventions-view');
      if (interventions) {
        const operation = factValue(interventions, t('operation'));
        const summary = operationSummary(value);
        if (operation && operation.textContent !== summary) operation.textContent = summary;
        interventions.querySelectorAll('.explorer-fact strong').forEach((node) => {
          if (!node.textContent.trim()) node.textContent = t('unavailable');
        });
      }
    }
    if (!comparison.a) comparison.a = value;
    renderCompatibility();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      applyPolish();
    });
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('.user-comparison-loaded')) {
      comparison.a = artifact();
      renderCompatibility();
    }
    if (event.target.closest('[data-nav], [data-explorer-view], [data-level]')) schedule();
  });

  document.addEventListener('change', (event) => {
    if (event.target.matches?.('.user-comparison-a')) readComparisonFile(event.target, 'a');
    if (event.target.matches?.('.user-comparison-b')) readComparisonFile(event.target, 'b');
    if (event.target.closest?.('#language, #lens-select')) schedule();
  });

  window.addEventListener('DOMContentLoaded', () => {
    comparison.a = artifact();
    const screen = $('.screen[data-screen="explore"]');
    if (screen) new MutationObserver(schedule).observe(screen, { childList: true, subtree: true });
    new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    schedule();
  });
})();
