(() => {
  'use strict';

  const SESSION_KEY = 'prismora.v4.session';
  const MODEL_KEY = 'prismora.v4.liveModel';
  const $ = (selector, root = document) => root.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let models = [];
  let busy = false;
  let scheduled = false;

  const copy = {
    fr: {
      local: 'Démo et imports locaux', livePrefix: 'Neuronpedia · ', choose: 'Sélectionnez un modèle Neuronpedia dans « Source » pour envoyer un vrai message.',
      notConnected: 'Testez d’abord la connexion Neuronpedia dans Réglages et compte.', pending: 'Run Neuronpedia en cours · aucune mesure n’est inventée.',
      failed: 'Le run Neuronpedia a échoué', live: 'Neuronpedia live · raw archivé', unavailable: 'Les modèles live sont indisponibles.',
    },
    en: {
      local: 'Demo and local imports', livePrefix: 'Neuronpedia · ', choose: 'Select a Neuronpedia model in “Source” to send a real message.',
      notConnected: 'Test the Neuronpedia connection first in Settings and account.', pending: 'Neuronpedia run in progress · no measurement is invented.',
      failed: 'Neuronpedia run failed', live: 'Live Neuronpedia · raw archived', unavailable: 'Live models are unavailable.',
    },
  };
  const t = (key) => copy[language()][key] || key;

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { 'content-type': 'application/json', ...(options.headers || {}) },
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

  function liveSession() {
    try {
      const payload = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
      return payload?.sourceType === 'live' ? payload : null;
    } catch {
      return null;
    }
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
    select.disabled = false;
    const session = liveSession();
    const sessionModel = session?.artifact?.request?.model?.model_id;
    const wanted = sessionModel ? `live:${sessionModel}` : current;
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
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({
        version: 1,
        artifact,
        sourceType: 'live',
        selectedToken: 0,
        selectedLayer: null,
        level: 'read',
      }));
      localStorage.setItem('prismora.level', 'read');
      localStorage.setItem(MODEL_KEY, `live:${modelId}`);
      location.assign(`/v4.html?live=${encodeURIComponent(artifact.run_id)}`);
    } catch (error) {
      setBusy(false);
      setStatus(`${t('failed')} : ${error.message}`, true);
    }
  }

  function polishLiveArtifact() {
    const session = liveSession();
    if (!session?.artifact) return;
    const modelId = session.artifact?.request?.model?.model_id || 'model';
    const who = $('#model-who');
    if (who && !who.textContent.includes('Neuronpedia live')) who.textContent = `${modelId} · Neuronpedia live`;
    const status = $('#reader-status');
    const expected = `${t('live')} · ${session.artifact.run_id}`;
    if (status && status.textContent !== expected) status.textContent = expected;
  }

  function schedulePolish() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      polishLiveArtifact();
    });
  }

  async function init() {
    document.addEventListener('submit', submitLive, true);
    try {
      const payload = await api('/api/live/models');
      models = Array.isArray(payload.models) ? payload.models : [];
      renderSources();
    } catch {
      models = [];
      renderSources();
      setStatus(t('unavailable'), true);
    }
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
