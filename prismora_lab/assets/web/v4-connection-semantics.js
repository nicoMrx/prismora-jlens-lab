(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let scheduled = false;
  let latestSettings = null;

  const copy = {
    fr: {
      off: 'Neuronpedia non connecté', configured: 'Clé Neuronpedia enregistrée · test requis', connected: 'Neuronpedia connecté', rejected: 'Clé Neuronpedia refusée',
      note: 'La clé reste uniquement dans la mémoire du serveur et est effacée à chaque redémarrage de Prismora. Pour ne la saisir qu’une fois : collez-la puis cliquez directement sur « Enregistrer et tester ». Les démos et imports fonctionnent sans clé.',
      enterAndTest: 'Enregistrer et tester', testSaved: 'Tester la connexion enregistrée', test: 'Tester la connexion',
      saveSettings: 'Enregistrer les réglages', saveWithoutTest: 'Enregistrer sans tester',
      stateOff: 'État de la session : aucune clé en mémoire', stateConfigured: 'État de la session : clé présente, test requis', stateConnected: 'État de la session : connexion validée', stateRejected: 'État de la session : clé refusée',
    },
    en: {
      off: 'Neuronpedia not connected', configured: 'Neuronpedia key saved · test required', connected: 'Neuronpedia connected', rejected: 'Neuronpedia key rejected',
      note: 'The key stays only in server memory and is cleared whenever Prismora restarts. To enter it once: paste it, then click “Save and test”. Demo and imports work without a key.',
      enterAndTest: 'Save and test', testSaved: 'Test saved connection', test: 'Test connection',
      saveSettings: 'Save settings', saveWithoutTest: 'Save without testing',
      stateOff: 'Session state: no key in memory', stateConfigured: 'Session state: key present, test required', stateConnected: 'Session state: connection validated', stateRejected: 'Session state: key rejected',
    },
  };

  function statusLooksRejected() {
    const text = String($('#reader-status')?.textContent || '');
    return /HTTP\s*(401|403)|refus[ée]|rejected/i.test(text);
  }

  function ensureSessionState() {
    let node = $('#connection-session-state');
    if (node) return node;
    const note = $('#secret-note');
    if (!note) return null;
    node = document.createElement('div');
    node.id = 'connection-session-state';
    node.className = 'connection-session-state';
    note.insertAdjacentElement('afterend', node);
    return node;
  }

  function updateDialogControls(settings) {
    const lang = language();
    const key = $('#neuronpedia-key');
    const typed = Boolean(key?.value.trim());
    const configured = Boolean(settings?.neuronpedia_key_configured);
    const connected = Boolean(settings?.neuronpedia_connected);
    const rejected = configured && !connected && statusLooksRejected();
    const test = $('#test-key');
    const save = $('#save-settings');
    if (test) test.textContent = typed ? copy[lang].enterAndTest : configured ? copy[lang].testSaved : copy[lang].test;
    if (save) save.textContent = typed ? copy[lang].saveWithoutTest : copy[lang].saveSettings;
    const state = ensureSessionState();
    if (state) {
      state.textContent = connected
        ? copy[lang].stateConnected
        : rejected
          ? copy[lang].stateRejected
          : configured
            ? copy[lang].stateConfigured
            : copy[lang].stateOff;
    }
  }

  async function refreshConnectionState() {
    try {
      const response = await fetch('/api/session/settings', { cache: 'no-store' });
      if (!response.ok) return;
      const settings = await response.json();
      latestSettings = settings;
      const lang = language();
      const chip = $('#connection-chip');
      const connected = Boolean(settings.neuronpedia_connected);
      const configured = Boolean(settings.neuronpedia_key_configured);
      const rejected = configured && !connected && statusLooksRejected();
      const label = connected ? copy[lang].connected : rejected ? copy[lang].rejected : configured ? copy[lang].configured : copy[lang].off;

      if (chip && chip.textContent !== label) chip.textContent = label;
      chip?.classList.toggle('connected', connected);
      chip?.classList.toggle('configured', configured && !connected);
      chip?.classList.toggle('rejected', rejected);

      const note = $('#secret-note');
      if (note && note.textContent !== copy[lang].note) note.textContent = copy[lang].note;
      updateDialogControls(settings);
      if (connected) {
        const key = $('#neuronpedia-key');
        if (key?.value) key.value = '';
      }
    } catch {
      // The local Reader remains usable when the session service is unavailable.
    }
  }

  function schedule(delay = 0) {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => {
      requestAnimationFrame(() => {
        scheduled = false;
        refreshConnectionState();
      });
    }, delay);
  }

  function init() {
    const status = $('#reader-status');
    if (status) new MutationObserver(() => schedule()).observe(status, { childList: true, characterData: true, subtree: true });
    new MutationObserver(() => schedule()).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    $('#neuronpedia-key')?.addEventListener('input', () => updateDialogControls(latestSettings));
    $('#open-settings')?.addEventListener('click', () => schedule());
    document.addEventListener('submit', (event) => {
      if (event.target?.id === 'settings-form') schedule(150);
    });
    document.addEventListener('click', (event) => {
      if (event.target.closest?.('#test-key')) {
        schedule(250);
        setTimeout(() => refreshConnectionState(), 1200);
      }
      if (event.target.closest?.('#continue-no-key, #save-settings')) schedule(150);
    });
    schedule();
  }

  if (document.readyState === 'loading') window.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
