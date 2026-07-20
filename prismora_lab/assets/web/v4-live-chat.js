(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const LIVE_REF_KEY = 'prismora.v4.liveRef';
  const MODEL_KEY = 'prismora.v4.liveModel';
  const STOP_MARKERS = ['<|im_end|>', '<|end|>', '<|return|>', '<end_of_turn>', '<eos>'];
  const $ = (selector, root = document) => root.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let models = [];
  let busy = false;
  let scheduled = false;
  let currentArtifact = null;
  let progressTimer = null;
  let progressStartedAt = 0;

  const copy = {
    fr: {
      local: 'Démo et imports locaux', livePrefix: 'Neuronpedia · ', choose: 'Sélectionnez un modèle Neuronpedia dans « Source » pour envoyer un vrai message.',
      notConnected: 'Testez d’abord la connexion Neuronpedia dans Réglages et compte.', pending: 'Run Neuronpedia en cours · aucune mesure n’est inventée.',
      failed: 'Le run Neuronpedia a échoué', live: 'Neuronpedia live · raw archivé', unavailable: 'Les modèles live sont indisponibles.',
      workTitle: 'Neuronpedia travaille sur votre message', sent: 'Requête envoyée au modèle.',
      measuring: 'Le modèle génère sa réponse et calcule les readouts J-Lens.',
      waiting: 'Prismora attend les mesures de toutes les couches.', long: 'Toujours en cours — un grand modèle peut prendre plusieurs minutes.',
      dontClose: 'Gardez cette page ouverte. Le temps affiché est réel ; la progression est volontairement indéterminée.',
      received: 'Artifact reçu · raw archivé · affichage des mesures…', restored: 'Artifact live restauré depuis le serveur local.',
    },
    en: {
      local: 'Demo and local imports', livePrefix: 'Neuronpedia · ', choose: 'Select a Neuronpedia model in “Source” to send a real message.',
      notConnected: 'Test the Neuronpedia connection first in Settings and account.', pending: 'Neuronpedia run in progress · no measurement is invented.',
      failed: 'Neuronpedia run failed', live: 'Live Neuronpedia · raw archived', unavailable: 'Live models are unavailable.',
      workTitle: 'Neuronpedia is working on your message', sent: 'Request sent to the model.',
      measuring: 'The model is generating its answer and computing J-Lens readouts.',
      waiting: 'Prismora is waiting for measurements from all layers.', long: 'Still running — a large model can take several minutes.',
      dontClose: 'Keep this page open. Elapsed time is real; progress is intentionally indeterminate.',
      received: 'Artifact received · raw archived · rendering measurements…', restored: 'Live artifact restored from the local server.',
    },
  };
  const t = (key) => copy[language()][key] || key;

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { 'content-type': 'application/json', ...(options.headers || {}) },
      cache: 'no-store',
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

  function setStatus(message, error = false) {
    const node = $('#reader-status');
    if (!node) return;
    node.textContent = message;
    node.style.color = error ? 'var(--danger)' : '';
  }

  function sourceSelect() {
    return $('.model-select select');
  }

  function selectedModelId() {
    const value = sourceSelect()?.value || '';
    return value.startsWith('live:') ? value.slice(5) : null;
  }

  function sessionArtifact() {
    try {
      const payload = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
      return payload?.sourceType === 'live' ? payload.artifact || null : null;
    } catch {
      return null;
    }
  }

  function activeArtifact() {
    return currentArtifact || sessionArtifact();
  }

  function livePrompt(artifact) {
    const derived = artifact?.derived?.live_chat?.user_message;
    if (derived) return String(derived);
    const chat = Array.isArray(artifact?.request?.chat) ? artifact.request.chat : [];
    return String([...chat].reverse().find((message) => message?.role === 'user')?.content || artifact?.request?.prompt || '');
  }

  function cleanCompletion(artifact) {
    let text = String(artifact?.result?.done?.completion || artifact?.result?.completion || '');
    const finalMarker = text.match(/<\|channel\|>\s*final\s*<\|message\|>/i);
    if (finalMarker) text = text.slice((finalMarker.index || 0) + finalMarker[0].length);
    let stop = text.length;
    STOP_MARKERS.forEach((marker) => {
      const index = text.toLowerCase().indexOf(marker.toLowerCase());
      if (index >= 0) stop = Math.min(stop, index);
    });
    return text
      .slice(0, stop)
      .replace(/<\|(?:im_start|start|start_header_id|message|channel)[^>]*\|>/gi, '')
      .trim();
  }

  function compact(value) {
    return String(value || '').replace(/\s+/g, '').toLowerCase();
  }

  function trimTechnicalTokenButtons() {
    const buttons = [...document.querySelectorAll('#tokens .token')];
    if (!buttons.length) return;
    const targets = STOP_MARKERS.map((marker) => compact(marker));
    for (let index = 0; index < buttons.length; index += 1) {
      let combined = '';
      for (let end = index; end < Math.min(buttons.length, index + 10); end += 1) {
        combined += buttons[end].textContent || '';
        const value = compact(combined);
        if (targets.includes(value)) {
          buttons.slice(index).forEach((button) => button.remove());
          return;
        }
        if (value && !targets.some((target) => target.startsWith(value))) break;
      }
    }
  }

  function modelLabel(modelId) {
    return models.find((model) => model.model_id === modelId)?.label || modelId || 'Neuronpedia';
  }

  function renderSources() {
    const select = sourceSelect();
    if (!select) return;
    const current = select.value || localStorage.getItem(MODEL_KEY) || 'local';
    const options = [{ value: 'local', label: t('local') }];
    models.forEach((model) => options.push({ value: `live:${model.model_id}`, label: `${t('livePrefix')}${model.label}` }));
    select.replaceChildren(...options.map((item) => {
      const option = document.createElement('option');
      option.value = item.value;
      option.textContent = item.label;
      return option;
    }));
    select.disabled = busy;
    const artifactModel = activeArtifact()?.request?.model?.model_id;
    const wanted = artifactModel ? `live:${artifactModel}` : current;
    select.value = options.some((item) => item.value === wanted) ? wanted : 'local';
    select.onchange = () => {
      localStorage.setItem(MODEL_KEY, select.value);
      if (selectedModelId()) setStatus(t('live'));
    };
  }

  function setBusy(value) {
    busy = value;
    const input = $('#message-input');
    const button = $('#send-button');
    const select = sourceSelect();
    if (input) input.disabled = value;
    if (button) button.disabled = value;
    if (select) select.disabled = value;
  }

  function ensureProgress() {
    let panel = $('#live-progress');
    if (panel) return panel;
    panel = document.createElement('section');
    panel.id = 'live-progress';
    panel.className = 'live-progress';
    panel.hidden = true;
    panel.setAttribute('role', 'status');
    panel.setAttribute('aria-live', 'polite');
    panel.innerHTML = '<span class="live-progress-spinner" aria-hidden="true"></span><div class="live-progress-copy"><strong></strong><p></p></div><span class="live-progress-time">00:00</span><p class="live-progress-note"></p>';
    const composer = $('#composer');
    composer?.insertAdjacentElement('afterend', panel);
    return panel;
  }

  function elapsedLabel(seconds) {
    const minutes = Math.floor(seconds / 60);
    return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  }

  function progressStage(seconds) {
    if (seconds >= 45) return t('long');
    if (seconds >= 15) return t('waiting');
    if (seconds >= 4) return t('measuring');
    return t('sent');
  }

  function updateProgress() {
    const panel = ensureProgress();
    if (!progressStartedAt || panel.hidden) return;
    const seconds = Math.max(0, Math.floor((Date.now() - progressStartedAt) / 1000));
    $('.live-progress-copy p', panel).textContent = progressStage(seconds);
    $('.live-progress-time', panel).textContent = elapsedLabel(seconds);
  }

  function startProgress(modelId) {
    const panel = ensureProgress();
    panel.hidden = false;
    panel.classList.remove('done', 'error');
    $('.live-progress-copy strong', panel).textContent = `${t('workTitle')} · ${modelLabel(modelId)}`;
    $('.live-progress-note', panel).textContent = t('dontClose');
    progressStartedAt = Date.now();
    updateProgress();
    clearInterval(progressTimer);
    progressTimer = setInterval(updateProgress, 1000);
  }

  function finishProgress({ error = false, message = '' } = {}) {
    const panel = ensureProgress();
    clearInterval(progressTimer);
    progressTimer = null;
    panel.classList.toggle('done', !error);
    panel.classList.toggle('error', error);
    $('.live-progress-copy p', panel).textContent = message || (error ? t('failed') : t('received'));
    updateProgress();
    if (!error) setTimeout(() => { panel.hidden = true; }, 1800);
  }

  function showPending(message) {
    const messages = $('#messages');
    const jlens = $('#jlens');
    if (messages) messages.hidden = false;
    if (jlens) jlens.hidden = true;
    const user = $('#user-message');
    const output = $('#model-output');
    const tokens = $('#tokens');
    if (user) user.textContent = message;
    if (output) output.textContent = t('pending');
    if (tokens) tokens.replaceChildren();
    setStatus(t('pending'));
  }

  function saveLiveReference(artifact) {
    const reference = {
      run_id: artifact.run_id,
      experiment_id: artifact.experiment_id,
      model_id: artifact?.request?.model?.model_id || null,
      user_message: livePrompt(artifact),
    };
    sessionStorage.setItem(LIVE_REF_KEY, JSON.stringify(reference));
    const params = new URLSearchParams();
    params.set('live', artifact.run_id);
    if (artifact.experiment_id) params.set('experiment', artifact.experiment_id);
    history.replaceState(null, '', `/v4.html?${params.toString()}`);
  }

  async function waitForReader(timeout = 10000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      if ($('#messages') && !$('#messages').hidden && $('#jlens') && !$('#jlens').hidden) return true;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    return false;
  }

  async function loadArtifactIntoReader(artifact, { updateUrl = true } = {}) {
    currentArtifact = artifact;
    if (updateUrl) saveLiveReference(artifact);
    const input = $('#import-files');
    const form = $('#import-form');
    const submit = $('#load-import');
    if (!input || !form || !submit || typeof DataTransfer === 'undefined') {
      throw new Error('Le lecteur local ne peut pas recevoir l’artifact live.');
    }
    const transfer = new DataTransfer();
    transfer.items.add(new File([JSON.stringify(artifact)], `${artifact.run_id}.json`, { type: 'application/json' }));
    input.files = transfer.files;
    form.requestSubmit(submit);
    await waitForReader();
    renderSources();
    schedulePolish();
  }

  async function submitLive(event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.id !== 'composer') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (busy) return;

    const message = $('#message-input')?.value.trim() || '';
    if (!message) return;
    const modelId = selectedModelId();
    if (!modelId) {
      setStatus(t('choose'), true);
      return;
    }

    try {
      const settings = await api('/api/session/settings');
      if (!settings.neuronpedia_connected) {
        setStatus(t('notConnected'), true);
        $('#settings-dialog')?.showModal();
        return;
      }
      setBusy(true);
      showPending(message);
      startProgress(modelId);
      const artifact = await api('/api/live/chat', {
        method: 'POST',
        body: JSON.stringify({
          message,
          model_id: modelId,
          temperature: 0,
          max_new_tokens: 128,
          top_k: 8,
          lens_types: ['JACOBIAN_LENS', 'LOGIT_LENS'],
          filter_nonword_tokens: true,
          enable_thinking: false,
        }),
      });
      $('.live-progress-copy p', ensureProgress()).textContent = t('received');
      await loadArtifactIntoReader(artifact);
      $('#message-input').value = '';
      setBusy(false);
      finishProgress();
    } catch (error) {
      setBusy(false);
      finishProgress({ error: true, message: `${t('failed')} : ${error.message}` });
      setStatus(`${t('failed')} : ${error.message}`, true);
    }
  }

  function polishLiveArtifact() {
    const artifact = activeArtifact();
    if (!artifact) return;
    const modelId = artifact?.request?.model?.model_id || 'model';
    const who = $('#model-who');
    if (who && !who.textContent.includes('Neuronpedia live')) who.textContent = `${modelId} · Neuronpedia live`;
    const user = $('#user-message');
    const prompt = livePrompt(artifact);
    if (user && prompt && user.textContent !== prompt) user.textContent = prompt;
    const output = $('#model-output');
    const completion = cleanCompletion(artifact);
    if (output && completion && output.textContent !== completion) output.textContent = completion;
    trimTechnicalTokenButtons();
    const status = $('#reader-status');
    const expected = `${t('live')} · ${artifact.run_id}`;
    if (!busy && status && status.textContent !== expected) status.textContent = expected;
  }

  function schedulePolish() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      polishLiveArtifact();
    });
  }

  async function restoreLiveFromServer() {
    const params = new URLSearchParams(location.search);
    let runId = params.get('live');
    let experimentId = params.get('experiment');
    if (!runId) {
      try {
        const reference = JSON.parse(sessionStorage.getItem(LIVE_REF_KEY) || 'null');
        runId = reference?.run_id || null;
        experimentId = reference?.experiment_id || null;
      } catch {
        runId = null;
      }
    }
    if (!runId) {
      currentArtifact = sessionArtifact();
      return;
    }
    const existing = sessionArtifact();
    if (existing?.run_id === runId) {
      currentArtifact = existing;
      return;
    }
    try {
      const suffix = experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : '';
      const artifact = await api(`/api/runs/${encodeURIComponent(runId)}${suffix}`);
      currentArtifact = artifact;
      await loadArtifactIntoReader(artifact, { updateUrl: false });
      setStatus(`${t('restored')} · ${runId}`);
    } catch (error) {
      setStatus(`${t('failed')} : ${error.message}`, true);
    }
  }

  async function init() {
    ensureProgress();
    document.addEventListener('submit', submitLive, true);
    try {
      const payload = await api('/api/live/models');
      models = Array.isArray(payload.models) ? payload.models : [];
    } catch {
      models = [];
      setStatus(t('unavailable'), true);
    }
    await restoreLiveFromServer();
    renderSources();
    const root = $('.screen[data-screen="read"]') || document.body;
    new MutationObserver(schedulePolish).observe(root, { childList: true, subtree: true, characterData: true });
    new MutationObserver(() => { renderSources(); schedulePolish(); }).observe(document.documentElement, {
      attributes: true, attributeFilter: ['lang'],
    });
    schedulePolish();
  }

  if (document.readyState === 'loading') window.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
