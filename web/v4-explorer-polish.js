(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const $ = (selector) => document.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let scheduled = false;

  const copy = {
    fr: {
      layers: 'Couches capturées', operation: 'Opération', unavailable: 'non disponible',
      synthetic: 'synthétique', steer: 'steer', swap: 'swap', ablation: 'ablation',
    },
    en: {
      layers: 'Captured layers', operation: 'Operation', unavailable: 'unavailable',
      synthetic: 'synthetic', steer: 'steer', swap: 'swap', ablation: 'ablation',
    },
  };
  const t = (key) => copy[language()][key];

  function artifact() {
    try {
      const value = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null')?.artifact;
      return value?.schema === 'prismora.run/v2' ? value : null;
    } catch {
      return null;
    }
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

  function applyPolish() {
    const value = artifact();
    if (!value) return;

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

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      applyPolish();
    });
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-nav], [data-explorer-view], [data-level]')) schedule();
  });
  document.addEventListener('change', (event) => {
    if (event.target.closest('#language, #lens-select')) schedule();
  });

  window.addEventListener('DOMContentLoaded', () => {
    const screen = $('.screen[data-screen="explore"]');
    if (screen) new MutationObserver(schedule).observe(screen, { childList: true, subtree: true });
    new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    schedule();
  });
})();