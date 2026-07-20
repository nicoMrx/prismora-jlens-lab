(() => {
  'use strict';

  const key = 'prismora.v4.session';
  const nativeRemoveItem = Storage.prototype.removeItem;
  let protectFirstStartupRemoval = sessionStorage.getItem(key) !== null;

  Storage.prototype.removeItem = function removeItem(name) {
    if (this === sessionStorage && name === key && protectFirstStartupRemoval) {
      protectFirstStartupRemoval = false;
      return;
    }
    return nativeRemoveItem.call(this, name);
  };

  window.setTimeout(() => {
    Storage.prototype.removeItem = nativeRemoveItem;
  }, 10000);

  const isPrismoraArtifact = (value) => value?.schema === 'prismora.run/v2';
  const isNeuronpediaExport = (value) => (
    value?.version === 1
    && ['chat', 'completion'].includes(value?.kind)
    && Array.isArray(value?.tokens)
    && value?.meta
    && value?.meta?.layers_by_type
  );

  const lastMessage = (messages, role) => [...messages].reverse().find((message) => message?.role === role)?.content || '';
  const safeId = (value) => String(value || 'export').replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 120) || 'export';

  function normalizeNeuronpediaExport(value, filename) {
    const messages = Array.isArray(value.messages) ? value.messages : [];
    const generatedTokens = value.tokens.filter((token) => token?.is_generated);
    const prompt = value.kind === 'completion'
      ? String(value.prompt || '')
      : lastMessage(messages, 'user');
    const completion = value.kind === 'chat'
      ? lastMessage(messages, 'assistant')
      : generatedTokens.map((token) => token?.token || '').join('');
    const layersByType = value.meta?.layers_by_type || {};
    const lensTypes = Array.isArray(value.meta?.types) && value.meta.types.length
      ? value.meta.types
      : Object.keys(layersByType);
    const capturedLayers = layersByType.JACOBIAN_LENS || layersByType[lensTypes[0]] || [];
    const runId = `neuronpedia-${safeId(value.modelId || value.meta?.model)}-${safeId(value.exportedAt || filename)}`;

    return {
      schema: 'prismora.run/v2',
      run_id: runId,
      request: {
        backend: 'neuronpedia_export',
        prompt,
        messages,
        model: {
          model_id: value.modelId || value.meta?.model || 'unknown-model',
        },
        parameters: {
          temperature: value.meta?.temperature,
          num_completion_tokens: value.meta?.num_completion_tokens,
          top_n: value.meta?.top_n,
          prepend_bos: value.meta?.prepend_bos,
          reuse_len: value.meta?.reuse_len,
        },
      },
      result: {
        tokens: value.tokens,
        meta: {
          ...value.meta,
          types: lensTypes,
          layers_by_type: layersByType,
        },
        done: {
          completion,
        },
      },
      coverage: {
        captured_layers: capturedLayers,
        lens_types: lensTypes,
      },
      provenance: {
        backend: 'neuronpedia_export',
        source: 'local-file',
        original_filename: filename,
        exported_at: value.exportedAt || null,
        original_kind: value.kind,
        original_version: value.version,
      },
    };
  }

  function showImportError(message) {
    const status = document.querySelector('#reader-status');
    if (status) {
      status.textContent = message;
      status.style.color = 'var(--danger)';
    }
  }

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.id !== 'import-form') return;
    if (event.submitter?.value === 'cancel') return;

    if (form.dataset.prismoraNormalized === '1') {
      delete form.dataset.prismoraNormalized;
      return;
    }

    const input = document.querySelector('#import-files');
    const files = input ? [...input.files] : [];
    if (!files.length) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    try {
      let source = null;
      let sourceFile = null;

      for (const file of files) {
        if (!file.name.toLowerCase().endsWith('.json')) continue;
        let value;
        try {
          value = JSON.parse(await file.text());
        } catch {
          continue;
        }

        const existing = isPrismoraArtifact(value)
          ? value
          : value?.artifact || value?.run || value?.data;
        if (isPrismoraArtifact(existing)) {
          source = existing;
          sourceFile = file;
          break;
        }
        if (isNeuronpediaExport(value)) {
          source = normalizeNeuronpediaExport(value, file.name);
          sourceFile = file;
          break;
        }
      }

      if (!source) throw new Error('No compatible Prismora or native Neuronpedia export was found.');

      const transfer = new DataTransfer();
      const normalizedName = `${(sourceFile?.name || 'neuronpedia-export').replace(/\.json$/i, '')}.prismora.json`;
      transfer.items.add(new File([JSON.stringify(source)], normalizedName, { type: 'application/json' }));
      input.files = transfer.files;

      const list = document.querySelector('#import-list');
      if (list) list.textContent = `${sourceFile?.name || normalizedName}\n→ ${normalizedName}`;

      form.dataset.prismoraNormalized = '1';
      queueMicrotask(() => form.requestSubmit(document.querySelector('#load-import')));
    } catch (error) {
      showImportError(error instanceof Error ? error.message : String(error));
    }
  }, true);

  function shouldShowDenseLabel(layer, index, count, selectedLayer) {
    return index === 0
      || index === count - 1
      || layer === selectedLayer
      || layer % 8 === 0;
  }

  function normalizeDenseMeasurements() {
    const rail = document.querySelector('#layer-rail');
    if (!rail) return;

    const buttons = [...rail.querySelectorAll('.layer-button')];
    const numbers = [...rail.querySelectorAll('.layer-number')];
    const count = Math.min(buttons.length, numbers.length);
    const dense = count > 24;
    rail.classList.toggle('dense', dense);

    if (!dense || count < 2) return;

    const selectedIndex = buttons.findIndex((button) => button.classList.contains('active'));
    const selectedLayer = selectedIndex >= 0 ? Number(numbers[selectedIndex]?.textContent) : null;
    const positionForIndex = (index) => 4 + (index / (count - 1)) * 92;

    buttons.slice(0, count).forEach((button, index) => {
      button.style.left = `${positionForIndex(index)}%`;
    });

    numbers.slice(0, count).forEach((number, index) => {
      const layer = Number(number.textContent);
      number.style.left = `${positionForIndex(index)}%`;
      number.hidden = !shouldShowDenseLabel(layer, index, count, selectedLayer);
    });

    const layerByIndex = numbers.slice(0, count).map((number) => Number(number.textContent));
    const gaps = [...rail.querySelectorAll('.layer-gap')];
    const gapLabels = [...rail.querySelectorAll('.layer-gap-label')];
    let gapIndex = 0;
    for (let index = 1; index < count; index += 1) {
      if (layerByIndex[index] - layerByIndex[index - 1] <= 1) continue;
      const left = positionForIndex(index - 1) + 1;
      const right = positionForIndex(index) - 1;
      if (gaps[gapIndex]) {
        gaps[gapIndex].style.left = `${left}%`;
        gaps[gapIndex].style.width = `${Math.max(0, right - left)}%`;
      }
      if (gapLabels[gapIndex]) gapLabels[gapIndex].style.left = `${(left + right) / 2}%`;
      gapIndex += 1;
    }

    const chart = document.querySelector('#trajectory');
    if (!chart) return;
    chart.classList.add('dense');

    const chartLabels = [...chart.querySelectorAll('.trajectory-label')];
    const positionByLayer = new Map();
    chartLabels.forEach((label, index) => {
      const layer = Number(label.textContent);
      const position = positionForIndex(index);
      positionByLayer.set(layer, position);
      label.style.left = `${position}%`;
      label.hidden = !shouldShowDenseLabel(layer, index, chartLabels.length, selectedLayer);
    });

    chart.querySelectorAll('.point').forEach((point) => {
      const match = String(point.title || '').match(/^L(-?\d+)/);
      if (!match) return;
      const position = positionByLayer.get(Number(match[1]));
      if (position !== undefined) point.style.left = `${position}%`;
    });

    const trajectoryGaps = [...chart.querySelectorAll('.trajectory-gap')];
    let trajectoryGapIndex = 0;
    for (let index = 1; index < layerByIndex.length; index += 1) {
      if (layerByIndex[index] - layerByIndex[index - 1] <= 1) continue;
      const left = positionForIndex(index - 1) + 1;
      const right = positionForIndex(index) - 1;
      const gap = trajectoryGaps[trajectoryGapIndex];
      if (gap) {
        gap.style.left = `${left}%`;
        gap.style.width = `${Math.max(0, right - left)}%`;
      }
      trajectoryGapIndex += 1;
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    const rail = document.querySelector('#layer-rail');
    const chart = document.querySelector('#trajectory');
    if (!rail || !chart) return;

    let scheduled = false;
    const schedule = () => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        normalizeDenseMeasurements();
      });
    };

    const observer = new MutationObserver(schedule);
    observer.observe(rail, { childList: true });
    observer.observe(chart, { childList: true });
    schedule();
  });
})();
