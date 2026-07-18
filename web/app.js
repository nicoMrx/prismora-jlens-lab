(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const state = {
    experiments: [],
    runs: [],
    claims: [],
    backends: [],
    plan: null,
    artifact: null,
    selectedTokenPosition: null,
    visualA: null,
    visualB: null,
    visualComparison: null,
    understand: null,
    demoArtifacts: [],
    visualSelectedColumn: 0,
    visualSelectedLayer: null,
    visualLocalSources: new Map(),
  };

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { 'content-type': 'application/json', ...(options.headers || {}) },
    });
    const text = await response.text();
    let value = null;
    try { value = text ? JSON.parse(text) : null; } catch { value = text; }
    if (!response.ok) {
      const detail = value && value.detail ? value.detail : value;
      const message = typeof detail === 'string' ? detail : JSON.stringify(detail, null, 2);
      throw new Error(message || `${response.status} ${response.statusText}`);
    }
    return value;
  }

  function toast(message, error = false) {
    const node = $('toast');
    node.textContent = message;
    node.classList.toggle('error', error);
    node.classList.add('show');
    clearTimeout(node._timer);
    node._timer = setTimeout(() => node.classList.remove('show'), 4200);
  }

  function setStatus(id, message, kind = '') {
    const node = $(id);
    node.textContent = message;
    node.className = `status-line ${kind}`.trim();
  }

  function pretty(value) { return JSON.stringify(value, null, 2); }
  function parseEditor(id) {
    try { return JSON.parse($(id).value); }
    catch (error) { throw new Error(`Invalid JSON: ${error.message}`); }
  }
  function fmt(value, digits = 3) {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    if (typeof value === 'number') return value.toFixed(digits);
    return String(value);
  }
  function shortHash(value) { return value ? `${value.slice(0, 10)}…${value.slice(-6)}` : '—'; }
  function escapeText(value) { return String(value ?? ''); }

  function navigate(panel) {
    document.querySelectorAll('.panel-page').forEach((node) => node.classList.toggle('active', node.id === `panel-${panel}`));
    document.querySelectorAll('.nav-item').forEach((node) => node.classList.toggle('active', node.dataset.panel === panel));
    if (window.location.hash !== `#${panel}`) history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${panel}`);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  document.querySelectorAll('.nav-item').forEach((button) => button.addEventListener('click', () => navigate(button.dataset.panel)));
  document.querySelectorAll('[data-jump]').forEach((button) => button.addEventListener('click', () => navigate(button.dataset.jump)));

  function fillSelect(select, rows, valueKey, labelFn, includeBlank = false) {
    const previous = select.value;
    select.replaceChildren();
    if (includeBlank) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'All';
      select.append(option);
    }
    rows.forEach((row) => {
      const option = document.createElement('option');
      option.value = row[valueKey];
      option.textContent = labelFn(row);
      select.append(option);
    });
    if ([...select.options].some((opt) => opt.value === previous)) select.value = previous;
  }

  async function refreshHealth() {
    try {
      const health = await api('/api/health');
      $('healthBadge').textContent = `control plane ${health.version}`;
      $('healthBadge').className = 'badge ok';
    } catch (error) {
      $('healthBadge').textContent = 'offline';
      $('healthBadge').className = 'badge warn';
    }
  }

  async function refreshExamples() {
    const value = await api('/api/examples');
    const select = $('exampleSelect');
    select.replaceChildren();
    value.examples.filter((name) => name !== 'model-registry.json').forEach((name) => {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      select.append(option);
    });
  }

  async function refreshExperiments() {
    const value = await api('/api/experiments');
    state.experiments = value.experiments;
    $('statExperiments').textContent = state.experiments.length;
    const targets = ['campaignExperimentSelect', 'claimExperiment', 'baselineBuildExperiment'];
    targets.forEach((id) => fillSelect($(id), state.experiments, 'experiment_id', (row) => `${row.experiment_id} · ${row.status}`));
    fillSelect($('runsExperimentFilter'), state.experiments, 'experiment_id', (row) => row.experiment_id, true);
  }

  async function refreshRuns() {
    const filter = $('runsExperimentFilter')?.value || '';
    const value = await api(`/api/runs${filter ? `?experiment_id=${encodeURIComponent(filter)}` : ''}`);
    state.runs = value.runs;
    $('statRuns').textContent = state.runs.length;
    $('statIndependent').textContent = state.runs.filter((run) => run.independent_observation).length;
    const runSelects = ['inspectRunSelect', 'baselineSourceRun', 'filterRunA', 'filterRunB', 'causalSourceRun', 'compareRunA', 'compareRunB', 'visualRunA', 'visualRunB'];
    runSelects.forEach((id) => fillSelect($(id), state.runs, 'run_id', (row) => `${row.run_id} · ${row.model_alias || row.model_id}`));
    renderRunsTable();
  }

  async function refreshClaims() {
    const value = await api('/api/claims');
    state.claims = value.claims;
    $('statClaims').textContent = state.claims.length;
    renderClaims();
  }

  async function refreshBackends() {
    const value = await api('/api/backends');
    state.backends = value.backends;
    renderFleet();
    $('backendMini').replaceChildren(...state.backends.map((backend) => {
      const badge = document.createElement('span');
      badge.className = `badge ${backend.available ? 'ok' : 'warn'}`;
      badge.textContent = `${backend.backend_id}: ${backend.available ? 'available' : 'unavailable'}${backend.mock ? ' · mock' : ''}`;
      return badge;
    }));
  }

  async function refreshAll() {
    await Promise.allSettled([refreshHealth(), refreshExamples(), refreshExperiments(), refreshBackends(), refreshClaims()]);
    await refreshRuns().catch((error) => toast(error.message, true));
  }

  $('refreshAllBtn').addEventListener('click', refreshAll);

  $('loadExampleBtn').addEventListener('click', async () => {
    try {
      const value = await api(`/api/examples/${encodeURIComponent($('exampleSelect').value)}`);
      $('specEditor').value = pretty(value);
      setStatus('specStatus', `Loaded ${$('exampleSelect').value}.`, 'ok');
    } catch (error) { setStatus('specStatus', error.message, 'error'); }
  });

  $('validateSpecBtn').addEventListener('click', async () => {
    try {
      const spec = parseEditor('specEditor');
      const report = await api('/api/validate/experiment', { method: 'POST', body: JSON.stringify(spec) });
      if (!report.ok) throw new Error(report.errors.join('\n'));
      setStatus('specStatus', 'ExperimentSpec v2: valid.', 'ok');
    } catch (error) { setStatus('specStatus', error.message, 'error'); }
  });

  $('saveSpecBtn').addEventListener('click', async () => {
    try {
      const spec = parseEditor('specEditor');
      const result = await api('/api/experiments', { method: 'POST', body: JSON.stringify(spec) });
      setStatus('specStatus', `Saved ${result.experiment_id}. Locked hash valid: ${result.locked}.`, 'ok');
      await refreshExperiments();
    } catch (error) { setStatus('specStatus', error.message, 'error'); }
  });

  $('lockSpecBtn').addEventListener('click', async () => {
    try {
      const spec = parseEditor('specEditor');
      await api('/api/experiments', { method: 'POST', body: JSON.stringify(spec) });
      const result = await api(`/api/experiments/${encodeURIComponent(spec.experiment_id)}/lock`, { method: 'POST', body: '{}' });
      const locked = await api(`/api/experiments/${encodeURIComponent(spec.experiment_id)}`);
      $('specEditor').value = pretty(locked);
      setStatus('specStatus', `LOCKED ${result.locked_at}\nSHA-256 ${result.spec_sha256}`, 'ok');
      await refreshExperiments();
    } catch (error) { setStatus('specStatus', error.message, 'error'); }
  });

  $('planSpecBtn').addEventListener('click', async () => {
    try {
      const spec = parseEditor('specEditor');
      await api('/api/experiments', { method: 'POST', body: JSON.stringify(spec) });
      $('campaignExperimentSelect').value = spec.experiment_id;
      await buildPlan(spec.experiment_id);
      navigate('campaign');
    } catch (error) { setStatus('specStatus', error.message, 'error'); }
  });

  $('bundleBtn').addEventListener('click', () => {
    try {
      const spec = parseEditor('specEditor');
      window.location.href = `/api/experiments/${encodeURIComponent(spec.experiment_id)}/bundle`;
    } catch (error) { setStatus('specStatus', error.message, 'error'); }
  });

  async function loadRegistry() {
    const value = await api('/api/models');
    $('registryEditor').value = pretty(value);
    setStatus('registryStatus', 'Stored registry loaded.', 'ok');
  }
  $('refreshRegistryBtn').addEventListener('click', () => loadRegistry().catch((error) => setStatus('registryStatus', error.message, 'error')));
  $('loadRegistryExampleBtn').addEventListener('click', async () => {
    try {
      $('registryEditor').value = pretty(await api('/api/examples/model-registry.json'));
      setStatus('registryStatus', 'Example loaded. Replace placeholders before scientific use.', 'warn');
    } catch (error) { setStatus('registryStatus', error.message, 'error'); }
  });
  $('saveRegistryBtn').addEventListener('click', async () => {
    try {
      const registry = parseEditor('registryEditor');
      const result = await api('/api/models', { method: 'POST', body: JSON.stringify(registry) });
      setStatus('registryStatus', `Saved ${result.count} model records.`, 'ok');
    } catch (error) { setStatus('registryStatus', error.message, 'error'); }
  });

  async function buildPlan(experimentId) {
    const value = await api(`/api/experiments/${encodeURIComponent(experimentId)}/plan`, { method: 'POST', body: '{}' });
    state.plan = value;
    const summary = value.summary;
    $('planSummary').textContent = [
      `${summary.run_count} planned runs`,
      `Backends: ${JSON.stringify(summary.by_backend)}`,
      `Models: ${JSON.stringify(summary.by_model)}`,
      ...(summary.warnings || []).map((warning) => `WARNING: ${warning}`),
    ].join('\n');
    renderPlanTable();
    return value;
  }

  $('refreshPlanBtn').addEventListener('click', async () => {
    try {
      const id = $('campaignExperimentSelect').value;
      if (!id) throw new Error('Select an experiment.');
      await buildPlan(id);
      setStatus('campaignStatus', 'Plan expanded deterministically.', 'ok');
    } catch (error) { setStatus('campaignStatus', error.message, 'error'); }
  });

  function renderPlanTable() {
    const body = $('planTable').querySelector('tbody');
    body.replaceChildren();
    if (!state.plan) return;
    state.plan.runs.forEach((run) => {
      const tr = document.createElement('tr');
      const selectCell = document.createElement('td');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox'; checkbox.dataset.runId = run.run_id;
      selectCell.append(checkbox); tr.append(selectCell);
      [run.run_id, run.request.backend, run.request.model.alias, run.request.prompt_id, JSON.stringify(run.request.factors), run.request.repeat].forEach((value, index) => {
        const td = document.createElement('td');
        td.textContent = escapeText(value);
        if (index === 0) td.className = 'mono';
        tr.append(td);
      });
      body.append(tr);
    });
  }

  $('executePlanBtn').addEventListener('click', async () => {
    try {
      const experimentId = $('campaignExperimentSelect').value;
      if (!experimentId) throw new Error('Select an experiment.');
      const checked = [...$('planTable').querySelectorAll('input[type=checkbox]:checked')].map((node) => node.dataset.runId);
      const payload = {
        experiment_id: experimentId,
        run_ids: checked,
        limit: Number($('runLimitInput').value || 1),
        force: false,
      };
      setStatus('campaignStatus', 'Executing synchronously…');
      const result = await api('/api/runs/execute', { method: 'POST', body: JSON.stringify(payload) });
      setStatus('campaignStatus', pretty(result), result.errors.length ? 'warn' : 'ok');
      await refreshRuns();
    } catch (error) { setStatus('campaignStatus', error.message, 'error'); }
  });

  function renderFleet() {
    const grid = $('fleetGrid');
    grid.replaceChildren();
    state.backends.forEach((backend) => {
      const card = document.createElement('article');
      card.className = 'card backend-card';
      const header = document.createElement('header');
      const title = document.createElement('h3'); title.textContent = backend.backend_id;
      const badge = document.createElement('span'); badge.className = `badge ${backend.available ? 'ok' : 'warn'}`; badge.textContent = backend.available ? 'available' : 'unavailable';
      header.append(title, badge); card.append(header);
      const p = document.createElement('p'); p.textContent = backend.mock ? 'Synthetic backend' : 'External execution backend'; p.style.color = 'var(--muted)'; card.append(p);
      const ul = document.createElement('ul');
      [
        `Readouts: ${(backend.readouts || []).join(', ') || 'none'}`,
        `Interventions: ${(backend.interventions || []).join(', ') || 'none'}`,
        `Forced tokens: ${Boolean(backend.forced_tokens)}`,
        `Fit lens: ${Boolean(backend.fit_lens)}`,
        `Limits: ${JSON.stringify(backend.limits || {})}`,
        ...(backend.notes || []),
      ].forEach((text) => { const li = document.createElement('li'); li.textContent = text; ul.append(li); });
      card.append(ul); grid.append(card);
    });
  }
  $('refreshFleetBtn').addEventListener('click', () => refreshBackends().catch((error) => toast(error.message, true)));

  function renderRunsTable() {
    const body = $('runsTable').querySelector('tbody');
    body.replaceChildren();
    state.runs.forEach((run) => {
      const tr = document.createElement('tr');
      const values = [
        run.run_id, run.experiment_id, run.backend, run.model_alias || run.model_id,
        run.prompt_id, run.independent_observation ? 'yes' : `no → ${run.duplicate_of || 'duplicate'}`,
        `${run.generated_token_count}/${run.token_count}`, run.created_at || '—',
      ];
      values.forEach((value, index) => {
        const td = document.createElement('td'); td.textContent = escapeText(value); if (index === 0) td.className = 'mono'; tr.append(td);
      });
      const action = document.createElement('td');
      const button = document.createElement('button'); button.textContent = 'Inspect';
      button.addEventListener('click', async () => { $('inspectRunSelect').value = run.run_id; navigate('inspector'); await loadArtifact(run.run_id); });
      action.append(button); tr.append(action); body.append(tr);
    });
  }
  $('refreshRunsBtn').addEventListener('click', () => refreshRuns().catch((error) => toast(error.message, true)));
  $('runsExperimentFilter').addEventListener('change', () => refreshRuns().catch((error) => toast(error.message, true)));

  async function loadArtifact(runId) {
    if (!runId) throw new Error('Select a run.');
    state.artifact = await api(`/api/runs/${encodeURIComponent(runId)}`);
    const lenses = state.artifact.result.meta.types || Object.keys(state.artifact.result.meta.layers_by_type || {});
    fillSelect($('inspectLensSelect'), lenses.map((lens) => ({ lens })), 'lens', (row) => row.lens);
    const firstLayers = state.artifact.result.meta.layers_by_type?.[lenses[0]] || [0];
    $('inspectLayerInput').value = firstLayers[0] ?? 0;
    const tokens = visibleTokens();
    state.selectedTokenPosition = tokens[0]?.position ?? state.artifact.result.tokens[0]?.position ?? null;
    renderInspector();
  }

  $('loadRunBtn').addEventListener('click', () => loadArtifact($('inspectRunSelect').value).catch((error) => toast(error.message, true)));
  $('inspectLensSelect').addEventListener('change', renderInspector);
  $('inspectLayerInput').addEventListener('change', renderInspector);
  $('generatedOnlyCheckbox').addEventListener('change', () => {
    const tokens = visibleTokens(); state.selectedTokenPosition = tokens[0]?.position ?? null; renderInspector();
  });

  function visibleTokens() {
    if (!state.artifact) return [];
    return state.artifact.result.tokens.filter((token) => !$('generatedOnlyCheckbox').checked || token.is_generated);
  }
  function tokenResult(token, lens) { return (token.results || []).find((result) => result.type === lens); }
  function top1Probability(token, lens, layer) {
    const layers = state.artifact.result.meta.layers_by_type?.[lens] || [];
    const index = layers.indexOf(layer);
    const result = tokenResult(token, lens);
    return index >= 0 && result?.top_probs?.[index]?.length ? Number(result.top_probs[index][0]) : null;
  }
  function heatColor(value) {
    if (value === null || Number.isNaN(value)) return '#111722';
    const x = Math.max(0, Math.min(1, value));
    const r = Math.round(24 + 115 * x); const g = Math.round(35 + 130 * x); const b = Math.round(52 + 180 * x);
    return `rgb(${r},${g},${b})`;
  }

  function renderInspector() {
    if (!state.artifact) return;
    renderRunMeta(); renderHeatmap(); renderTimeline(); renderCursor();
  }

  function renderRunMeta() {
    const artifact = state.artifact; const model = artifact.request.model;
    const entries = [
      ['run', artifact.run_id], ['experiment', artifact.experiment_id], ['backend', artifact.request.backend], ['model', model.model_id],
      ['prompt', artifact.request.prompt_id], ['request SHA-256', shortHash(artifact.provenance.request_sha256)],
      ['execution SHA-256', shortHash(artifact.provenance.execution_request_sha256)], ['raw SHA-256', shortHash(artifact.provenance.raw_sha256)], ['result SHA-256', shortHash(artifact.provenance.canonical_result_sha256)],
    ];
    const grid = $('runMeta'); grid.replaceChildren();
    entries.forEach(([label, value]) => { const div = document.createElement('div'); const span = document.createElement('span'); span.textContent = label; const b = document.createElement('b'); b.textContent = value; div.append(span, b); grid.append(div); });
    $('qualityDetails').textContent = pretty({ quality: artifact.quality, provenance: artifact.provenance, raw: artifact.raw, request: artifact.request });
  }

  function renderHeatmap() {
    const canvas = $('heatmapCanvas'); const ctx = canvas.getContext('2d');
    const tokens = visibleTokens(); const lens = $('inspectLensSelect').value;
    const layers = state.artifact.result.meta.layers_by_type?.[lens] || [];
    const cellW = 10, cellH = 9, left = 58, top = 24;
    canvas.width = Math.max(900, left + tokens.length * cellW + 20);
    canvas.height = Math.max(280, top + layers.length * cellH + 35);
    ctx.fillStyle = '#070b11'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = '10px ui-monospace, monospace'; ctx.textBaseline = 'middle';
    layers.forEach((layer, y) => {
      if (y % Math.max(1, Math.floor(layers.length / 12)) === 0) { ctx.fillStyle = '#8fa0b8'; ctx.fillText(String(layer), 7, top + y * cellH + cellH / 2); }
      tokens.forEach((token, x) => {
        const p = top1Probability(token, lens, layer);
        ctx.fillStyle = heatColor(p); ctx.fillRect(left + x * cellW, top + y * cellH, cellW - 1, cellH - 1);
        if (token.position === state.selectedTokenPosition && layer === Number($('inspectLayerInput').value)) {
          ctx.strokeStyle = '#ffffff'; ctx.strokeRect(left + x * cellW + .5, top + y * cellH + .5, cellW - 2, cellH - 2);
        }
      });
    });
    ctx.fillStyle = '#8fa0b8'; ctx.fillText('layer', 7, 10); ctx.fillText('token position →', left, canvas.height - 10);
    canvas.onclick = (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = Math.floor((event.clientX - rect.left + canvas.parentElement.scrollLeft - left) / cellW);
      const y = Math.floor((event.clientY - rect.top + canvas.parentElement.scrollTop - top) / cellH);
      if (tokens[x] && layers[y] !== undefined) { state.selectedTokenPosition = tokens[x].position; $('inspectLayerInput').value = layers[y]; renderInspector(); }
    };
    $('heatmapLegend').textContent = `Top-1 probability · ${lens} · ${layers.length} actual layers · ${tokens.length} visible tokens`;
  }

  function renderTimeline() {
    const timeline = $('tokenTimeline'); timeline.replaceChildren();
    visibleTokens().forEach((token) => {
      const chip = document.createElement('button'); chip.className = `token-chip ${token.position === state.selectedTokenPosition ? 'active' : ''} ${token.is_generated ? '' : 'context'}`;
      chip.textContent = token.token; chip.title = `position ${token.position} · id ${token.id}`;
      chip.addEventListener('click', () => { state.selectedTokenPosition = token.position; renderInspector(); }); timeline.append(chip);
    });
  }

  function renderCursor() {
    const token = state.artifact.result.tokens.find((item) => item.position === state.selectedTokenPosition);
    if (!token) { $('cursorDetails').textContent = 'No token selected.'; return; }
    const layer = Number($('inspectLayerInput').value); const layersByType = state.artifact.result.meta.layers_by_type || {};
    $('cursorDetails').textContent = `position ${token.position} · token ${JSON.stringify(token.token)} · id ${token.id} · ${token.is_generated ? 'generated' : 'context'} · layer ${layer}`;
    const container = $('topKTables'); container.replaceChildren();
    Object.keys(layersByType).forEach((lens) => {
      const layerIndex = layersByType[lens].indexOf(layer); const result = tokenResult(token, lens);
      const section = document.createElement('div'); section.className = 'topk-table';
      const heading = document.createElement('h3'); heading.textContent = lens; section.append(heading);
      if (layerIndex < 0 || !result) { const p = document.createElement('p'); p.textContent = 'Layer unavailable for this lens.'; section.append(p); container.append(section); return; }
      const table = document.createElement('table'); const head = document.createElement('thead'); head.innerHTML = '<tr><th>Rank</th><th>Token</th><th>Probability</th></tr>'; table.append(head);
      const body = document.createElement('tbody');
      const candidates = result.top_tokens[layerIndex] || []; const probs = result.top_probs[layerIndex] || [];
      candidates.forEach((candidate, index) => { const tr = document.createElement('tr'); [index + 1, JSON.stringify(candidate), fmt(Number(probs[index]), 4)].forEach((value) => { const td = document.createElement('td'); td.textContent = value; tr.append(td); }); body.append(tr); });
      table.append(body); section.append(table); container.append(section);
    });
  }

  $('downloadRawBtn').addEventListener('click', () => {
    if (!state.artifact) return toast('Load a run first.', true);
    const query = new URLSearchParams({ experiment_id: state.artifact.experiment_id });
    const a = document.createElement('a');
    a.href = `/api/runs/${encodeURIComponent(state.artifact.run_id)}/raw?${query}`;
    a.download = `${state.artifact.run_id}.raw.json`;
    a.click();
  });

  $('downloadCockpitBtn').addEventListener('click', async () => {
    try {
      if (!state.artifact) throw new Error('Load a run first.');
      const value = await api(`/api/runs/${encodeURIComponent(state.artifact.run_id)}/cockpit`);
      const blob = new Blob([pretty(value)], { type: 'application/json' }); const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `${state.artifact.run_id}.cockpit.json`; a.click(); URL.revokeObjectURL(url);
    } catch (error) { toast(error.message, true); }
  });

  $('createReplayBtn').addEventListener('click', async () => {
    try {
      const runId = $('baselineSourceRun').value; if (!runId) throw new Error('Select a source run.');
      const payload = { experiment_id: $('baselineExperimentId').value.trim(), save: true };
      const spec = await api(`/api/runs/${encodeURIComponent(runId)}/make-filter-replay`, { method: 'POST', body: JSON.stringify(payload) });
      $('specEditor').value = pretty(spec); setStatus('baselineStatus', `Saved ${spec.experiment_id}. Review and lock it before execution.`, 'ok');
      await refreshExperiments();
    } catch (error) { setStatus('baselineStatus', error.message, 'error'); }
  });

  $('compareFilterBtn').addEventListener('click', async () => {
    try {
      const value = await api('/api/compare', { method: 'POST', body: JSON.stringify({ run_a: $('filterRunA').value, run_b: $('filterRunB').value, lens: $('filterLens').value, mode: 'filter_effect' }) });
      $('filterComparisonOutput').textContent = pretty(value);
    } catch (error) { $('filterComparisonOutput').textContent = error.message; }
  });

  $('buildBaselineBtn').addEventListener('click', async () => {
    try {
      const payload = { experiment_id: $('baselineBuildExperiment').value, lens: $('baselineBuildLens').value, position_scope: $('baselineScope').value, max_tokens_per_layer: 20 };
      const value = await api('/api/baselines/build', { method: 'POST', body: JSON.stringify(payload) });
      $('baselineOutput').textContent = pretty({ baseline_id: value.baseline_id, runs: value.run_ids.length, mixed_filter_warning: value.mixed_filter_warning, stored_relative_path: value.stored_relative_path, first_layers: value.per_layer.slice(0, 4) });
    } catch (error) { $('baselineOutput').textContent = error.message; }
  });

  $('executeInterventionBtn').addEventListener('click', async () => {
    try {
      const runId = $('causalSourceRun').value; if (!runId) throw new Error('Select a source run.');
      const mode = $('causalMode').value; const layers = $('causalLayers').value.split(',').map((value) => value.trim()).filter(Boolean).map(Number);
      if (layers.some(Number.isNaN)) throw new Error('Layers must be comma-separated integers.');
      const intervention = {
        mode,
        source_tokens: [{ token: $('causalSourceToken').value, type: $('causalSourceLens').value }],
        target_token: mode === 'swap' ? { token: $('causalTargetToken').value, type: $('causalTargetLens').value } : null,
        layers,
        strength: mode === 'ablate' ? null : Number($('causalStrength').value),
        apply_to_generated_tokens: $('causalGenerated').checked,
        controls: ['no_intervention', 'random_direction_same_norm'],
      };
      setStatus('causalStatus', 'Executing intervention…');
      const artifact = await api(`/api/runs/${encodeURIComponent(runId)}/intervene`, { method: 'POST', body: JSON.stringify({ label: $('causalLabel').value, intervention }) });
      setStatus('causalStatus', `Stored ${artifact.run_id}. This is an intervention observation, not an automatic causality claim.`, 'ok');
      await refreshRuns(); $('inspectRunSelect').value = artifact.run_id;
    } catch (error) { setStatus('causalStatus', error.message, 'error'); }
  });

  $('compareRunsBtn').addEventListener('click', async () => {
    try {
      const mode = $('compareMode').value;
      const value = await api('/api/compare', { method: 'POST', body: JSON.stringify({
        run_a: $('compareRunA').value,
        run_b: $('compareRunB').value,
        lens: $('compareLens').value,
        mode,
        probability_abs_tolerance: Number($('compareTolerance').value),
      }) });
      if (mode === 'bridge') renderBridgeComparison(value); else renderComparison(value);
    } catch (error) { $('compareSummary').textContent = error.message; }
  });

  function renderComparison(value) {
    $('compareSummary').textContent = `Mean top-1 agreement: ${fmt(value.mean_top1_agreement)}\nAligned generated positions: ${value.aligned_positions}\n${(value.warnings || []).join('\n')}`;
    const body = $('compareTable').querySelector('tbody'); body.replaceChildren();
    value.layers.forEach((row) => { const tr = document.createElement('tr'); [row.layer, fmt(row.relative_depth_a), fmt(row.relative_depth_b), row.positions_compared, fmt(row.top1_agreement), fmt(row.mean_topk_jaccard)].forEach((cell) => { const td = document.createElement('td'); td.textContent = cell; tr.append(td); }); body.append(tr); });
    const canvas = $('compareCanvas'); const ctx = canvas.getContext('2d'); const rows = value.layers.filter((row) => row.top1_agreement !== null);
    canvas.width = Math.max(900, rows.length * 18 + 80); canvas.height = 300; ctx.fillStyle = '#070b11'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    const left = 50, top = 20, width = canvas.width - 75, height = 230;
    ctx.strokeStyle = '#31405a'; ctx.strokeRect(left, top, width, height); ctx.font = '11px ui-monospace, monospace'; ctx.fillStyle = '#93a3ba';
    [0, .25, .5, .75, 1].forEach((valueY) => { const y = top + height * (1 - valueY); ctx.fillText(valueY.toFixed(2), 8, y + 4); ctx.strokeStyle = '#1e293b'; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + width, y); ctx.stroke(); });
    if (rows.length) {
      ctx.strokeStyle = '#8db4ff'; ctx.lineWidth = 2; ctx.beginPath();
      rows.forEach((row, index) => { const x = left + (rows.length === 1 ? 0 : index / (rows.length - 1)) * width; const y = top + (1 - row.top1_agreement) * height; if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }); ctx.stroke();
    }
  }


  function renderBridgeComparison(value) {
    $('compareSummary').textContent = [
      `Equivalent under declared tolerance: ${value.equivalent_under_declared_tolerance}`,
      `Surface token IDs identical: ${value.surface_token_ids_identical}`,
      `Actual layer lists identical: ${value.actual_layer_lists_identical}`,
      `Top-1 agreement: ${fmt(value.top1_agreement)}`,
      `Exact top-k rate: ${fmt(value.exact_topk_rate)}`,
      `Probability within tolerance: ${fmt(value.probability_within_tolerance_rate)}`,
      `Maximum |Δp|: ${fmt(value.max_probability_abs_delta)}`,
      ...(value.warnings || []),
    ].join('\n');
    const body = $('compareTable').querySelector('tbody'); body.replaceChildren();
    value.layers.forEach((row) => {
      const tr = document.createElement('tr');
      [row.layer, '', '', row.cells, fmt(row.top1_agreement), fmt(row.exact_topk_rate)].forEach((cell) => {
        const td = document.createElement('td'); td.textContent = cell; tr.append(td);
      });
      tr.title = `p within tol=${fmt(row.probability_within_tolerance_rate)} · max |Δp|=${fmt(row.max_probability_abs_delta)}`;
      body.append(tr);
    });
    const canvas = $('compareCanvas'); const ctx = canvas.getContext('2d'); const rows = value.layers.filter((row) => row.exact_topk_rate !== null);
    canvas.width = Math.max(900, rows.length * 18 + 80); canvas.height = 300; ctx.fillStyle = '#070b11'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    const left = 50, top = 20, width = canvas.width - 75, height = 230;
    ctx.strokeStyle = '#31405a'; ctx.strokeRect(left, top, width, height); ctx.font = '11px ui-monospace, monospace'; ctx.fillStyle = '#93a3ba';
    [0, .25, .5, .75, 1].forEach((valueY) => { const y = top + height * (1 - valueY); ctx.fillText(valueY.toFixed(2), 8, y + 4); ctx.strokeStyle = '#1e293b'; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + width, y); ctx.stroke(); });
    if (rows.length) {
      ctx.strokeStyle = '#8db4ff'; ctx.lineWidth = 2; ctx.beginPath();
      rows.forEach((row, index) => { const x = left + (rows.length === 1 ? 0 : index / (rows.length - 1)) * width; const y = top + (1 - row.exact_topk_rate) * height; if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }); ctx.stroke();
    }
  }

  $('saveClaimBtn').addEventListener('click', async () => {
    try {
      const claim = {
        schema: 'prismora.claim/v1', claim_id: $('claimId').value.trim(), experiment_id: $('claimExperiment').value,
        statement: $('claimStatement').value.trim(), level: $('claimLevel').value, status: $('claimStatus').value,
        evidence_run_ids: $('claimRuns').value.split(',').map((value) => value.trim()).filter(Boolean),
        limitations: $('claimLimitations').value.split('\n').map((value) => value.trim()).filter(Boolean), metadata: {},
      };
      const result = await api('/api/claims', { method: 'POST', body: JSON.stringify(claim) });
      setStatus('claimStatusLine', `Saved ${result.claim_id}.`, 'ok'); await refreshClaims();
    } catch (error) { setStatus('claimStatusLine', error.message, 'error'); }
  });
  $('refreshClaimsBtn').addEventListener('click', () => refreshClaims().catch((error) => toast(error.message, true)));

  function renderClaims() {
    const list = $('claimsList'); list.replaceChildren();
    state.claims.forEach((claim) => {
      const item = document.createElement('article'); item.className = 'claim-item';
      const header = document.createElement('header'); const strong = document.createElement('strong'); strong.textContent = claim.claim_id; const badge = document.createElement('span'); badge.className = `badge ${claim.status === 'supported' ? 'ok' : claim.status === 'refuted' ? 'warn' : 'muted'}`; badge.textContent = `${claim.level} · ${claim.status}`; header.append(strong, badge);
      const p = document.createElement('p'); p.textContent = claim.statement; const small = document.createElement('small'); small.textContent = `Experiment: ${claim.experiment_id} · Evidence: ${(claim.evidence_run_ids || []).length} runs · Limitations: ${(claim.limitations || []).length}`;
      item.append(header, p, small); list.append(item);
    });
    if (!state.claims.length) list.textContent = 'No claims stored.';
  }


  // ---------------------------------------------------------------------------
  // Visualiseur humain — comparison without reading JSON.
  // All calculations are derived from the two archived artifacts loaded here.
  // ---------------------------------------------------------------------------

  function visualArtifactLabel(artifact) {
    if (!artifact) return '—';
    const request = artifact.request || {};
    const condition = request.factors?.condition || request.factors?.probe_condition || request.prompt_id || '';
    return `${artifact.run_id || 'local'}${condition ? ` · ${condition}` : ''}`;
  }

  function visualInterventionText(artifact) {
    const intervention = artifact?.request?.intervention;
    if (!intervention || ((!intervention.layers || !intervention.layers.length) && intervention.layer === undefined) || intervention.mode === 'none') return 'Sans intervention déclarée';
    const layersList = intervention.layers || (intervention.layer === undefined ? [] : [intervention.layer]);
    if (intervention.type === 'synthetic' || artifact?.request?.factors?.demo) return `Intervention synthétique de démonstration · couche(s) ${layersList.join(', ') || '—'}`;
    const sources = (intervention.source_tokens || []).map((item) => JSON.stringify(item.token)).join(', ') || '—';
    const target = intervention.target_token?.token ? ` → ${JSON.stringify(intervention.target_token.token)}` : '';
    const layers = layersList.join(', ') || '—';
    const strength = intervention.strength === null || intervention.strength === undefined ? '' : ` · force ${intervention.strength}`;
    return `${(intervention.mode || intervention.type || 'intervention').toUpperCase()} · ${sources}${target} · couche(s) ${layers}${strength}`;
  }

  function visualCompletion(artifact) {
    if (!artifact) return '';
    const done = artifact.result?.done || {};
    if (typeof done.completion === 'string') return done.completion;
    return (artifact.result?.tokens || []).filter((token) => token.is_generated).map((token) => token.token).join('');
  }

  function visualLensResult(token, lens) {
    return (token?.results || []).find((result) => result.type === lens) || null;
  }

  function visualLayerCell(token, lens, layer, artifact) {
    const layers = artifact?.result?.meta?.layers_by_type?.[lens] || [];
    const layerIndex = layers.indexOf(layer);
    const result = visualLensResult(token, lens);
    if (layerIndex < 0 || !result) return null;
    const candidates = result.top_tokens?.[layerIndex] || [];
    const probabilities = (result.top_probs?.[layerIndex] || []).map(Number);
    if (!candidates.length) return null;
    return { candidates, probabilities, top1: candidates[0], p1: probabilities[0] ?? null };
  }

  function arrayExactlyEqual(a, b) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((value, index) => value === b[index]);
  }

  function topKJaccard(a, b) {
    const setA = new Set(a || []); const setB = new Set(b || []);
    const union = new Set([...setA, ...setB]);
    if (!union.size) return 1;
    let intersection = 0;
    setA.forEach((value) => { if (setB.has(value)) intersection += 1; });
    return intersection / union.size;
  }

  function visualProbeRequestToInternal(payload, label) {
    const steerTokens = Array.isArray(payload?.steerTokens) ? payload.steerTokens : [];
    let intervention = null;
    if (payload?.steerAblate) {
      intervention = { mode: 'ablate', source_tokens: steerTokens, target_token: null, layers: payload.steerLayers || [], strength: null, apply_to_generated_tokens: Boolean(payload.steerGeneratedTokens) };
    } else if (payload?.swapToken) {
      intervention = { mode: 'swap', source_tokens: steerTokens, target_token: payload.swapToken, layers: payload.steerLayers || [], strength: payload.steerStrength ?? null, apply_to_generated_tokens: Boolean(payload.steerGeneratedTokens) };
    } else if (steerTokens.length) {
      intervention = { mode: 'steer', source_tokens: steerTokens, target_token: null, layers: payload.steerLayers || [], strength: payload.steerStrength ?? null, apply_to_generated_tokens: Boolean(payload.steerGeneratedTokens) };
    }
    return {
      backend: 'neuronpedia',
      model: { alias: 'Q36', model_id: payload?.modelId || 'unknown' },
      prompt_id: label,
      prompt: payload?.prompt || '',
      factors: { source: 'local-probe', condition: label },
      repeat: 1,
      generation: { temperature: payload?.temperature ?? 0, max_new_tokens: payload?.numCompletionTokens ?? 0, prepend_bos: payload?.prependBos, enable_thinking: payload?.enableThinking },
      readout: { types: payload?.type || [], top_k: payload?.topN, filter_nonword_tokens: payload?.filterNonWordTokens },
      intervention,
    };
  }

  function wrapLocalVisualArtifact(raw, label, requestPayload = null) {
    const result = raw?.result?.meta && raw?.result?.tokens ? raw.result : raw;
    if (!result?.meta || !Array.isArray(result?.tokens) || !result?.done) throw new Error(`${label}: le JSON ne contient pas meta + tokens + done.`);
    if (raw?.schema === 'prismora.run/v2') return raw;
    return {
      schema: 'prismora.run/v2-local-view',
      run_id: label,
      experiment_id: 'local-probe',
      request: visualProbeRequestToInternal(requestPayload || {}, label),
      result,
      provenance: {},
      quality: { warnings: ['Fichier local affiché sans import dans l’archive Prismora.'] },
    };
  }

  function visualAlignedTokens(a, b, scope) {
    const tokensA = a.result?.tokens || []; const tokensB = b.result?.tokens || [];
    const promptA = tokensA.filter((token) => !token.is_generated);
    const promptB = tokensB.filter((token) => !token.is_generated);
    const generatedA = tokensA.filter((token) => token.is_generated);
    const generatedB = tokensB.filter((token) => token.is_generated);
    const aligned = [];
    if (scope === 'prompt' || scope === 'all') {
      const byPositionB = new Map(promptB.map((token) => [Number(token.position), token]));
      promptA.forEach((tokenA) => {
        const tokenB = byPositionB.get(Number(tokenA.position));
        if (tokenB) aligned.push({ kind: 'prompt', key: `p${tokenA.position}`, label: `p${tokenA.position}`, tokenA, tokenB });
      });
    }
    if (scope === 'generated' || scope === 'all') {
      const count = Math.min(generatedA.length, generatedB.length);
      for (let index = 0; index < count; index += 1) {
        aligned.push({ kind: 'generated', key: `g${index}`, label: `g${index + 1}`, tokenA: generatedA[index], tokenB: generatedB[index] });
      }
    }
    return aligned;
  }

  function buildVisualComparison(a, b, lens, scope) {
    const layersA = a.result?.meta?.layers_by_type?.[lens] || [];
    const layersB = b.result?.meta?.layers_by_type?.[lens] || [];
    const layers = layersA.filter((layer) => layersB.includes(layer));
    const aligned = visualAlignedTokens(a, b, scope);
    const rows = layers.map((layer) => {
      let compared = 0; let top1Different = 0; let strictDifferent = 0; let jaccardSum = 0;
      const cells = aligned.map((pair) => {
        const cellA = visualLayerCell(pair.tokenA, lens, layer, a);
        const cellB = visualLayerCell(pair.tokenB, lens, layer, b);
        if (!cellA || !cellB) return { pair, cellA, cellB, missing: true, top1Different: null, strictDifferent: null, jaccard: null };
        compared += 1;
        const top1Diff = cellA.top1 !== cellB.top1;
        const strictDiff = !arrayExactlyEqual(cellA.candidates, cellB.candidates) || !arrayExactlyEqual(cellA.probabilities, cellB.probabilities);
        const jaccard = topKJaccard(cellA.candidates, cellB.candidates);
        top1Different += Number(top1Diff); strictDifferent += Number(strictDiff); jaccardSum += jaccard;
        return { pair, cellA, cellB, missing: false, top1Different: top1Diff, strictDifferent: strictDiff, jaccard };
      });
      return {
        layer, cells, compared,
        top1DifferenceRate: compared ? top1Different / compared : null,
        strictDifferenceRate: compared ? strictDifferent / compared : null,
        meanTopKJaccard: compared ? jaccardSum / compared : null,
      };
    });
    const firstStrict = rows.find((row) => row.strictDifferenceRate > 0)?.layer ?? null;
    const firstTop1 = rows.find((row) => row.top1DifferenceRate > 0)?.layer ?? null;
    const maxRow = rows.filter((row) => row.strictDifferenceRate !== null).sort((x, y) => y.strictDifferenceRate - x.strictDifferenceRate)[0] || null;
    const layersFor = (run) => { const i = run.request?.intervention || {}; return [...(i.layers || []), ...(i.layer === undefined ? [] : [i.layer])]; };
    const declared = [...new Set([...layersFor(a), ...layersFor(b)])].sort((x, y) => x - y);
    return {
      a, b, lens, scope, layers, aligned, rows, firstStrict, firstTop1, maxRow,
      declaredLayers: declared,
      completionsEqual: visualCompletion(a) === visualCompletion(b),
      idsEqual: (a.result?.tokens || []).map((token) => token.id).join(',') === (b.result?.tokens || []).map((token) => token.id).join(','),
    };
  }

  function visualMetricValue(cell, metric) {
    if (!cell || cell.missing) return null;
    if (metric === 'top1') return cell.top1Different ? 1 : 0;
    if (metric === 'jaccard') return 1 - cell.jaccard;
    return cell.strictDifferent ? 1 : 0;
  }

  function visualDifferenceColor(value, missing = false) {
    if (missing || value === null || Number.isNaN(value)) return '#202836';
    const x = Math.max(0, Math.min(1, Number(value)));
    if (x === 0) return '#173b42';
    const r = Math.round(110 + 140 * x); const g = Math.round(105 - 55 * x); const b = Math.round(55 + 35 * (1 - x));
    return `rgb(${r},${g},${b})`;
  }

  function visualDeclaredLayer() {
    return state.visualComparison?.declaredLayers?.[0] ?? null;
  }

  function renderVisualSummary() {
    const comparison = state.visualComparison; const grid = $('visualSummaryGrid'); grid.replaceChildren();
    if (!comparison) return;
    const declared = comparison.declaredLayers.length ? comparison.declaredLayers.join(', ') : 'aucune';
    const entries = [
      ['Première divergence stricte', comparison.firstStrict ?? 'aucune'],
      ['Première divergence top-1', comparison.firstTop1 ?? 'aucune'],
      ['Couche(s) déclarée(s)', declared],
      ['Sorties générées', comparison.completionsEqual ? 'identiques' : 'différentes'],
      ['Tokens alignés', comparison.aligned.length],
      ['Couches communes', comparison.layers.length],
    ];
    entries.forEach(([label, value]) => {
      const card = document.createElement('article'); card.className = 'human-stat-card';
      const span = document.createElement('span'); span.textContent = label;
      const strong = document.createElement('strong'); strong.textContent = value;
      card.append(span, strong); grid.append(card);
    });
  }

  function renderVisualOutputs() {
    const comparison = state.visualComparison; if (!comparison) return;
    $('visualLabelA').textContent = visualArtifactLabel(comparison.a);
    $('visualLabelB').textContent = visualArtifactLabel(comparison.b);
    $('visualInterventionA').textContent = visualInterventionText(comparison.a);
    $('visualInterventionB').textContent = visualInterventionText(comparison.b);
    $('visualCompletionA').textContent = visualCompletion(comparison.a) || 'Aucun texte généré.';
    $('visualCompletionB').textContent = visualCompletion(comparison.b) || 'Aucun texte généré.';
  }

  function renderVisualProfile() {
    const comparison = state.visualComparison; if (!comparison) return;
    const canvas = $('visualProfileCanvas'); const ctx = canvas.getContext('2d');
    const rows = comparison.rows; const declared = visualDeclaredLayer();
    const left = 54, top = 22, right = 20, bottom = 38;
    canvas.width = Math.max(900, rows.length * 16 + left + right);
    canvas.height = 280;
    const width = canvas.width - left - right; const height = canvas.height - top - bottom;
    ctx.fillStyle = '#070b11'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = '11px ui-monospace, monospace'; ctx.fillStyle = '#9aa9bf';
    [0, .25, .5, .75, 1].forEach((tick) => {
      const y = top + height * (1 - tick); ctx.fillText(tick.toFixed(2), 8, y + 4);
      ctx.strokeStyle = '#1f2a3b'; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + width, y); ctx.stroke();
    });
    const drawLine = (selector, stroke) => {
      const points = [];
      rows.forEach((row, index) => {
        const value = selector(row); if (value === null) return;
        points.push({ layer: row.layer, x: left + (rows.length <= 1 ? 0 : index / (rows.length - 1)) * width, y: top + (1 - value) * height });
      });
      ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.beginPath();
      let previousLayer = null; let hasActivePoint = false;
      points.forEach((point) => {
        const gap = previousLayer !== null && point.layer - previousLayer > 1;
        if (!hasActivePoint || gap) ctx.moveTo(point.x, point.y); else ctx.lineTo(point.x, point.y);
        previousLayer = point.layer; hasActivePoint = true;
      });
      ctx.stroke();
      ctx.fillStyle = stroke;
      points.forEach((point) => { ctx.beginPath(); ctx.arc(point.x, point.y, 3, 0, Math.PI * 2); ctx.fill(); });
    };
    drawLine((row) => row.strictDifferenceRate, '#f0b55a');
    drawLine((row) => row.top1DifferenceRate, '#86b8ff');
    if (declared !== null && comparison.layers.includes(declared)) {
      const index = comparison.layers.indexOf(declared); const x = left + (rows.length <= 1 ? 0 : index / (rows.length - 1)) * width;
      ctx.strokeStyle = '#ffffff'; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#ffffff'; ctx.fillText(`couche déclarée ${declared}`, Math.min(x + 5, canvas.width - 170), 13);
    }
    ctx.fillStyle = '#9aa9bf'; ctx.fillText('taux de cellules différentes', left, canvas.height - 8);
    ctx.fillStyle = '#f0b55a'; ctx.fillText('— strict', canvas.width - 185, 16);
    ctx.fillStyle = '#86b8ff'; ctx.fillText('— top-1', canvas.width - 95, 16);
  }

  function renderVisualHeatmap() {
    const comparison = state.visualComparison; if (!comparison) return;
    const canvas = $('visualHeatmapCanvas'); const ctx = canvas.getContext('2d');
    const metric = $('visualMetricSelect').value; const rows = comparison.rows; const aligned = comparison.aligned;
    const cellW = 13, cellH = 10, left = 68, top = 28;
    canvas.width = Math.max(940, left + aligned.length * cellW + 30);
    canvas.height = Math.max(360, top + rows.length * cellH + 42);
    ctx.fillStyle = '#070b11'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = '10px ui-monospace, monospace'; ctx.textBaseline = 'middle';
    rows.forEach((row, y) => {
      if (y % Math.max(1, Math.floor(rows.length / 12)) === 0) { ctx.fillStyle = '#98a7bd'; ctx.fillText(String(row.layer), 10, top + y * cellH + cellH / 2); }
      row.cells.forEach((cell, x) => {
        const value = visualMetricValue(cell, metric);
        ctx.fillStyle = visualDifferenceColor(value, cell.missing);
        ctx.fillRect(left + x * cellW, top + y * cellH, cellW - 1, cellH - 1);
        if (x === state.visualSelectedColumn && row.layer === state.visualSelectedLayer) {
          ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5; ctx.strokeRect(left + x * cellW + .5, top + y * cellH + .5, cellW - 2, cellH - 2);
        }
      });
    });
    comparison.declaredLayers.forEach((layer) => {
      const y = rows.findIndex((row) => row.layer === layer);
      if (y >= 0) { ctx.strokeStyle = '#ffffff'; ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.moveTo(left, top + y * cellH); ctx.lineTo(left + aligned.length * cellW, top + y * cellH); ctx.stroke(); ctx.setLineDash([]); }
    });
    ctx.fillStyle = '#98a7bd'; ctx.fillText('couche', 8, 12); ctx.fillText('tokens alignés →', left, canvas.height - 12);
    canvas.onclick = (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = Math.floor((event.clientX - rect.left + canvas.parentElement.scrollLeft - left) / cellW);
      const y = Math.floor((event.clientY - rect.top + canvas.parentElement.scrollTop - top) / cellH);
      if (aligned[x] && rows[y]) { state.visualSelectedColumn = x; state.visualSelectedLayer = rows[y].layer; renderVisualComparison(); }
    };
    const metricLabel = metric === 'top1' ? 'Top-1' : metric === 'jaccard' ? 'Écart top-k' : 'Différence stricte';
    $('visualHeatLegend').textContent = `${metricLabel} · bleu-vert = identique · orange/rouge = différent · pointillés = couche déclarée`;
  }

  function renderVisualTimeline() {
    const comparison = state.visualComparison; if (!comparison) return;
    const node = $('visualTokenTimeline'); node.replaceChildren();
    comparison.aligned.forEach((pair, index) => {
      const button = document.createElement('button');
      const same = pair.tokenA.token === pair.tokenB.token;
      button.className = `visual-token-pair ${index === state.visualSelectedColumn ? 'active' : ''} ${same ? '' : 'surface-diff'}`;
      const label = document.createElement('span'); label.className = 'pair-index'; label.textContent = pair.label;
      const tokenA = document.createElement('span'); tokenA.className = 'pair-a'; tokenA.textContent = `A ${JSON.stringify(pair.tokenA.token)}`;
      const tokenB = document.createElement('span'); tokenB.className = 'pair-b'; tokenB.textContent = `B ${JSON.stringify(pair.tokenB.token)}`;
      button.append(label, tokenA, tokenB);
      button.title = `${pair.kind} · A position ${pair.tokenA.position} id ${pair.tokenA.id} · B position ${pair.tokenB.position} id ${pair.tokenB.id}`;
      button.addEventListener('click', () => { state.visualSelectedColumn = index; renderVisualComparison(); });
      node.append(button);
    });
  }

  function renderVisualCell() {
    const comparison = state.visualComparison; if (!comparison || !comparison.aligned.length) return;
    const column = Math.min(state.visualSelectedColumn, comparison.aligned.length - 1);
    const row = comparison.rows.find((item) => item.layer === state.visualSelectedLayer) || comparison.rows[0];
    if (!row) return;
    const cell = row.cells[column]; const pair = comparison.aligned[column];
    state.visualSelectedColumn = column; state.visualSelectedLayer = row.layer;
    if (!cell || cell.missing) { $('visualCellSummary').textContent = `${pair.label} · couche ${row.layer} · cellule absente`; $('visualTopKSideBySide').replaceChildren(); return; }
    $('visualCellSummary').textContent = [
      `${pair.kind === 'prompt' ? 'Prompt' : 'Généré'} ${pair.label} · couche ${row.layer}`,
      `Token A ${JSON.stringify(pair.tokenA.token)} (id ${pair.tokenA.id})`,
      `Token B ${JSON.stringify(pair.tokenB.token)} (id ${pair.tokenB.id})`,
      `Top-1 ${cell.top1Different ? 'DIFFÉRENT' : 'identique'} · Jaccard top-k ${fmt(cell.jaccard, 3)}`,
    ].join('\n');
    const container = $('visualTopKSideBySide'); container.replaceChildren();
    const table = document.createElement('table'); table.className = 'visual-paired-topk';
    const head = document.createElement('thead'); head.innerHTML = '<tr><th>Rang</th><th>Token A</th><th>p A</th><th>Token B</th><th>p B</th><th></th></tr>'; table.append(head);
    const body = document.createElement('tbody');
    const count = Math.max(cell.cellA.candidates.length, cell.cellB.candidates.length);
    for (let index = 0; index < count; index += 1) {
      const candidateA = cell.cellA.candidates[index] ?? '—'; const candidateB = cell.cellB.candidates[index] ?? '—';
      const tr = document.createElement('tr'); if (candidateA !== candidateB) tr.className = 'different-row';
      [index + 1, JSON.stringify(candidateA), fmt(cell.cellA.probabilities[index], 5), JSON.stringify(candidateB), fmt(cell.cellB.probabilities[index], 5), candidateA === candidateB ? 'même' : 'différent'].forEach((value) => { const td = document.createElement('td'); td.textContent = value; tr.append(td); });
      body.append(tr);
    }
    table.append(body); container.append(table);

    const trajectoryBody = $('visualTrajectoryTable').querySelector('tbody'); trajectoryBody.replaceChildren();
    comparison.rows.forEach((layerRow) => {
      const layerCell = layerRow.cells[column]; const tr = document.createElement('tr');
      if (layerCell && !layerCell.missing && layerCell.top1Different) tr.className = 'different-row';
      if (layerRow.layer === state.visualSelectedLayer) tr.classList.add('selected-row');
      const values = layerCell && !layerCell.missing
        ? [layerRow.layer, JSON.stringify(layerCell.cellA.top1), fmt(layerCell.cellA.p1, 5), JSON.stringify(layerCell.cellB.top1), fmt(layerCell.cellB.p1, 5), layerCell.top1Different ? 'différent' : 'même']
        : [layerRow.layer, '—', '—', '—', '—', 'absent'];
      values.forEach((value) => { const td = document.createElement('td'); td.textContent = value; tr.append(td); });
      tr.addEventListener('click', () => { state.visualSelectedLayer = layerRow.layer; renderVisualComparison(); });
      trajectoryBody.append(tr);
    });
    const selectedRow = trajectoryBody.querySelector('.selected-row');
    if (selectedRow) {
      const wrap = $('visualTrajectoryTable').parentElement;
      wrap.scrollTop = Math.max(0, selectedRow.offsetTop - wrap.clientHeight / 2);
    }
  }

  function renderVisualHumanReading() {
    const c = state.visualComparison; if (!c) return;
    const lines = [];
    const declared = c.declaredLayers;
    if (c.firstStrict === null) {
      lines.push('Aucune différence stricte n’est mesurée dans la lentille et la zone sélectionnées.');
    } else {
      lines.push(`La première différence stricte apparaît à la couche ${c.firstStrict}. La première différence du top-1 apparaît à la couche ${c.firstTop1 ?? 'aucune'}.`);
    }
    if (declared.length) {
      const firstDeclared = declared[0];
      if (c.firstStrict === firstDeclared) lines.push(`La frontière mesurée coïncide exactement avec la première couche d’intervention déclarée (${firstDeclared}). C’est compatible avec une intervention appliquée à cet endroit.`);
      else if (c.firstStrict !== null && c.firstStrict < firstDeclared) lines.push(`ALERTE : une divergence apparaît avant la couche déclarée (${firstDeclared}). Il faut vérifier l’alignement, la baseline et la requête.`);
      else if (c.firstStrict !== null) lines.push(`La divergence apparaît après la couche déclarée (${firstDeclared}), avec un décalage de ${c.firstStrict - firstDeclared} couche(s).`);
      else lines.push(`Une intervention est déclarée à la couche ${firstDeclared}, mais aucune divergence n’est visible dans cette vue.`);
    } else {
      lines.push('Aucune couche d’intervention n’est déclarée dans les métadonnées des deux observations.');
    }
    lines.push(c.completionsEqual ? 'Les textes générés sont identiques dans ces deux runs.' : 'Les textes générés sont différents dans ces deux runs.');
    if (c.maxRow) lines.push(`La plus forte proportion de cellules strictement différentes est observée à la couche ${c.maxRow.layer} (${fmt(c.maxRow.strictDifferenceRate * 100, 1)} % des tokens alignés).`);
    lines.push('Cette vue établit des différences mesurées et leur localisation. La causalité sémantique exige encore une baseline répétée et les contrôles préenregistrés.');
    const node = $('visualHumanReading'); node.replaceChildren();
    lines.forEach((line, index) => { const p = document.createElement('p'); if (index === 1 && declared.length && c.firstStrict === declared[0]) p.className = 'highlight-reading'; p.textContent = line; node.append(p); });
  }

  function renderVisualComparison() {
    if (!state.visualComparison) return;
    renderVisualSummary(); renderVisualOutputs(); renderVisualProfile(); renderVisualHeatmap(); renderVisualTimeline(); renderVisualCell(); renderVisualHumanReading(); renderUnderstand();
  }

  function recomputeVisualComparison() {
    if (!state.visualA || !state.visualB) return;
    const lensesA = state.visualA.result?.meta?.types || Object.keys(state.visualA.result?.meta?.layers_by_type || {});
    const lensesB = state.visualB.result?.meta?.types || Object.keys(state.visualB.result?.meta?.layers_by_type || {});
    const shared = lensesA.filter((lens) => lensesB.includes(lens));
    const select = $('visualLensSelect'); const previous = select.value; fillSelect(select, shared.map((lens) => ({ lens })), 'lens', (row) => row.lens);
    if (shared.includes(previous)) select.value = previous;
    const lens = select.value || shared[0];
    if (!lens) throw new Error('Aucune lentille commune entre A et B.');
    state.visualComparison = buildVisualComparison(state.visualA, state.visualB, lens, $('visualScopeSelect').value);
    state.visualSelectedColumn = Math.min(state.visualSelectedColumn, Math.max(0, state.visualComparison.aligned.length - 1));
    const suggestedLayer = state.visualComparison.firstStrict ?? state.visualComparison.declaredLayers[0] ?? state.visualComparison.layers[0] ?? null;
    if (!state.visualComparison.layers.includes(state.visualSelectedLayer)) state.visualSelectedLayer = suggestedLayer;
    renderVisualComparison();
    loadUnderstand().catch((error) => { state.understand = null; renderUnderstand(); renderUnderstandError(error.message); });
    setStatus('visualStatus', `Comparaison chargée : ${visualArtifactLabel(state.visualA)} ↔ ${visualArtifactLabel(state.visualB)}.`, 'ok');
  }


  async function loadUnderstand() {
    if (!state.visualA || !state.visualB) return;
    const locale = $('understandLocale')?.value || 'en';
    const selectedScope = $('visualScopeSelect')?.value || 'prompt';
    const scope = selectedScope === 'generated' ? 'generated_ordinal' : (selectedScope === 'all' ? 'all' : 'prompt_fixed');
    clearUnderstandError();
    const endpoint = (state.demoArtifacts || []).some((run) => run.run_id === state.visualA.run_id) ? '/api/demo/build-week/understand/compare' : '/api/understand/compare';
    state.understand = await api(endpoint, { method: 'POST', body: JSON.stringify({ run_a: state.visualA.run_id, run_b: state.visualB.run_id, lens: $('visualLensSelect').value || 'JACOBIAN_LENS', scope, locale, probability_abs_tolerance: 0 }) });
    renderUnderstand();
  }


  function updateUnderstandStaticLabels() {
    const locale = $('understandLocale')?.value || 'en';
    const copy = locale === 'fr'
      ? { demo: 'Charger la démo Build Week', language: 'Langue', badge: 'Résumé par règles, sans LLM' }
      : { demo: 'Load Build Week demo', language: 'Language', badge: 'Rule-based, no LLM summary' };
    if ($('loadBuildWeekDemoBtn')) $('loadBuildWeekDemoBtn').textContent = copy.demo;
    if ($('understandLanguageLabel')) $('understandLanguageLabel').textContent = copy.language;
    if ($('understandRuleBadge')) $('understandRuleBadge').textContent = copy.badge;
  }

  function renderUnderstand() {
    const cov = $('coverageCards'); const box = $('understandSentences'); if (!cov || !box) return;
    const locale = $('understandLocale')?.value || 'en'; updateUnderstandStaticLabels(); const why = locale === 'fr' ? 'Pourquoi ?' : 'Why?';
    const labels = locale === 'fr' ? { source: 'source', transmitted: 'transmis', instrumented: 'instrumentés', generated: 'générés instrumentés', layers: 'couches', unknown: 'inconnu', complete: 'complète', partial: 'partielle' } : { source: 'source', transmitted: 'transmitted', instrumented: 'instrumented', generated: 'instrumented generated', layers: 'layers', unknown: 'unknown', complete: 'complete', partial: 'partial' };
    const statusLabel = (status) => labels[status] || labels.unknown;
    const cards = [state.visualA, state.visualB].filter(Boolean).map((run, idx) => {
      const c = run.coverage || {}; const status = c.status || 'unknown'; const unknown = labels.unknown;
      return `<article class="coverage-card ${status !== 'complete' ? 'warn' : ''}"><strong>${idx === 0 ? 'A' : 'B'} · ${statusLabel(status)}</strong><span>${labels.source} ${c.source_tokens_total ?? unknown}</span><span>${labels.transmitted} ${c.transmitted_tokens ?? unknown}</span><span>${labels.instrumented} ${c.instrumented_tokens ?? unknown}</span><span>${labels.generated} ${c.instrumented_generated_tokens ?? unknown}</span><span>${labels.layers} ${(c.captured_layers || []).join(', ') || unknown}</span></article>`;
    }).join('');
    cov.innerHTML = cards || `<p class="muted-copy">${locale === 'fr' ? 'Aucune couverture chargée.' : 'No coverage loaded.'}</p>`;
    const sentences = state.understand?.sentences || [];
    box.replaceChildren();
    sentences.forEach((sentence) => { const details = document.createElement('details'); details.className = `understand-trace ${sentence.severity || 'info'}`; const summary = document.createElement('summary'); summary.textContent = sentence.text; details.append(summary); const pre = document.createElement('pre'); pre.textContent = JSON.stringify({ rule_id: sentence.rule_id, template_id: sentence.template_id, evidence: sentence.evidence }, null, 2); const whyLabel = document.createElement('strong'); whyLabel.textContent = why; details.append(whyLabel, pre); box.append(details); });
  }

  function clearUnderstandError() { const node = $('understandError'); if (node) { node.hidden = true; node.replaceChildren(); } }

  function renderUnderstandError(message) {
    const node = $('understandError'); if (!node) return;
    const locale = $('understandLocale')?.value || 'en';
    node.hidden = false; node.replaceChildren();
    const title = document.createElement('strong'); title.textContent = locale === 'fr' ? 'Erreur Understand' : 'Understand error';
    const detail = document.createElement('pre'); detail.textContent = String(message || 'Unknown error');
    const retry = document.createElement('p'); retry.textContent = locale === 'fr' ? 'Réessaie ou recharge la démo vérifiée.' : 'Retry or reload the verified demo.';
    node.append(title, detail, retry);
  }

  async function loadStoredVisualComparison() {
    const runA = $('visualRunA').value; const runB = $('visualRunB').value;
    if (!runA || !runB) throw new Error('Choisis deux runs archivés.');
    if (runA === runB) throw new Error('A et B doivent être deux runs différents.');
    state.understand = null; renderUnderstand(); clearUnderstandError();
    setStatus('visualStatus', 'Chargement des deux artifacts…');
    [state.visualA, state.visualB] = await Promise.all([
      api(`/api/runs/${encodeURIComponent(runA)}`),
      api(`/api/runs/${encodeURIComponent(runB)}`),
    ]);
    state.visualSelectedColumn = 0; state.visualSelectedLayer = null; recomputeVisualComparison();
  }

  async function readProbeDirectory(files) {
    const records = new Map();
    const selected = [...files];
    for (const file of selected) {
      const name = file.name;
      let base = null; let kind = null;
      if (name.endsWith('_request_exact.json')) { base = name.replace('_request_exact.json', ''); kind = 'request'; }
      else if (name.endsWith('_response_pretty.json')) { base = name.replace('_response_pretty.json', ''); kind = 'response'; }
      else if (name.endsWith('_response_exact.raw')) { base = name.replace('_response_exact.raw', ''); kind = 'raw'; }
      if (!base || !kind) continue;
      const record = records.get(base) || { label: base, request: null, response: null, rawText: null };
      try {
        const text = await file.text();
        if (kind === 'request') record.request = JSON.parse(text);
        else if (kind === 'response') record.response = JSON.parse(text);
        else record.rawText = text;
      } catch (error) {
        record.error = `${name}: ${error.message}`;
      }
      records.set(base, record);
    }
    state.visualLocalSources.clear();
    records.forEach((record, label) => {
      if (!record.response && record.rawText) { try { record.response = JSON.parse(record.rawText); } catch { /* shown below */ } }
      if (record.response?.meta && Array.isArray(record.response?.tokens) && record.response?.done) {
        state.visualLocalSources.set(label, wrapLocalVisualArtifact(record.response, label, record.request));
      }
    });
    const rows = [...state.visualLocalSources.keys()].sort().map((label) => ({ label }));
    fillSelect($('visualLocalA'), rows, 'label', (row) => row.label);
    fillSelect($('visualLocalB'), rows, 'label', (row) => row.label);
    if (rows.length > 1) $('visualLocalB').value = rows[1].label;
    setStatus('visualProbeStatus', `${rows.length} résultat(s) J-Lens lisible(s) trouvé(s) dans ${selected.length} fichier(s).`, rows.length >= 2 ? 'ok' : 'warn');
  }


  async function loadBuildWeekDemo() {
    state.understand = null; renderUnderstand(); clearUnderstandError();
    const payload = await api('/api/demo/build-week');
    state.demoArtifacts = payload.artifacts || [];
    if (state.demoArtifacts.length < 2) throw new Error('Build Week demo artifacts are unavailable.');
    state.visualA = state.demoArtifacts.find((run) => run.run_id === 'demo-pair-a-control') || state.demoArtifacts[0];
    state.visualB = state.demoArtifacts.find((run) => run.run_id === 'demo-pair-a-shift') || state.demoArtifacts[1];
    state.visualSelectedColumn = 0; state.visualSelectedLayer = null;
    $('visualScopeSelect').value = 'all';
    recomputeVisualComparison();
    setStatus('visualStatus', 'Build Week demo loaded: Pair A selected.', 'ok');
  }

  $('visualCompareStoredBtn').addEventListener('click', () => loadStoredVisualComparison().catch((error) => setStatus('visualStatus', error.message, 'error')));
  $('loadBuildWeekDemoBtn')?.addEventListener('click', () => loadBuildWeekDemo().catch((error) => setStatus('visualStatus', error.message, 'error')));
  $('understandLocale')?.addEventListener('change', () => { updateUnderstandStaticLabels(); renderUnderstand(); if (!state.understand) renderUnderstandError($('understandError')?.textContent || ''); loadUnderstand().catch((error) => { state.understand = null; renderUnderstand(); renderUnderstandError(error.message); }); });
  $('visualSwapRunsBtn').addEventListener('click', () => { const a = $('visualRunA').value; $('visualRunA').value = $('visualRunB').value; $('visualRunB').value = a; });
  $('visualRedrawBtn').addEventListener('click', () => { try { recomputeVisualComparison(); } catch (error) { setStatus('visualStatus', error.message, 'error'); } });
  $('visualLensSelect').addEventListener('change', () => { if (state.visualA && state.visualB) { state.visualSelectedLayer = null; recomputeVisualComparison(); } });
  $('visualScopeSelect').addEventListener('change', () => { if (state.visualA && state.visualB) { state.visualSelectedColumn = 0; state.visualSelectedLayer = null; recomputeVisualComparison(); } });
  $('visualMetricSelect').addEventListener('change', () => { if (state.visualComparison) renderVisualHeatmap(); });
  $('visualLoadProbeBtn').addEventListener('click', () => readProbeDirectory($('visualProbeFiles').files).catch((error) => setStatus('visualProbeStatus', error.message, 'error')));
  $('visualCompareLocalBtn').addEventListener('click', () => {
    try {
      const a = state.visualLocalSources.get($('visualLocalA').value); const b = state.visualLocalSources.get($('visualLocalB').value);
      if (!a || !b) throw new Error('Charge un dossier puis choisis deux résultats locaux.');
      if (a.run_id === b.run_id) throw new Error('A et B doivent être différents.');
      state.visualA = a; state.visualB = b; state.visualSelectedColumn = 0; state.visualSelectedLayer = null; recomputeVisualComparison();
    } catch (error) { setStatus('visualStatus', error.message, 'error'); }
  });

  $('quickStartBtn').addEventListener('click', async () => {
    navigate('experiments');
    $('exampleSelect').value = 'strategy_quadratic_mock.json';
    $('loadExampleBtn').click();
  });

  refreshAll().then(async () => {
    await loadRegistry();
    if (state.runs.length > 1 && $('visualRunA').value === $('visualRunB').value) $('visualRunB').value = state.runs[1].run_id;
    const requestedPanel = window.location.hash ? window.location.hash.slice(1) : '';
    if (requestedPanel && document.getElementById(`panel-${requestedPanel}`)) {
      navigate(requestedPanel);
      if (requestedPanel === 'visualizer' && state.runs.length > 1) loadStoredVisualComparison().catch((error) => setStatus('visualStatus', error.message, 'error'));
    }
  }).catch((error) => toast(error.message, true));
})();
