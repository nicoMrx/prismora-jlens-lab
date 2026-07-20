(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let scheduled = false;

  const copy = {
    fr: {
      off: 'Neuronpedia non connecté',
      configured: 'Clé Neuronpedia enregistrée · test requis',
      connected: 'Neuronpedia connecté',
      rejected: 'Clé Neuronpedia refusée',
      note: 'La clé reste en mémoire serveur pour cette session. Enregistrer ne connecte pas automatiquement : utilisez « Tester la connexion ». Les démos et imports fonctionnent sans clé.',
    },
    en: {
      off: 'Neuronpedia not connected',
      configured: 'Neuronpedia key saved · test required',
      connected: 'Neuronpedia connected',
      rejected: 'Neuronpedia key rejected',
      note: 'The key remains in server memory for this session. Saving does not connect automatically: use “Test connection”. Demo and imports work without a key.',
    },
  };

  function statusLooksRejected() {
    const text = String($('#reader-status')?.textContent || '');
    return /HTTP\s*(401|403)|refus[ée]|rejected/i.test(text);
  }

  async function refreshConnectionState() {
    try {
      const response = await fetch('/api/session/settings', { cache: 'no-store' });
      if (!response.ok) return;
      const settings = await response.json();
      const lang = language();
      const chip = $('#connection-chip');
      const connected = Boolean(settings.neuronpedia_connected);
      const configured = Boolean(settings.neuronpedia_key_configured);
      const rejected = configured && !connected && statusLooksRejected();
      const label = connected
        ? copy[lang].connected
        : rejected
          ? copy[lang].rejected
          : configured
            ? copy[lang].configured
            : copy[lang].off;

      if (chip && chip.textContent !== label) chip.textContent = label;
      chip?.classList.toggle('connected', connected);
      chip?.classList.toggle('configured', configured && !connected);
      chip?.classList.toggle('rejected', rejected);

      const note = $('#secret-note');
      if (note && note.textContent !== copy[lang].note) note.textContent = copy[lang].note;
    } catch {
      // The local Reader remains usable when the session service is unavailable.
    }
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      refreshConnectionState();
    });
  }

  function init() {
    const status = $('#reader-status');
    if (status) new MutationObserver(schedule).observe(status, { childList: true, characterData: true, subtree: true });
    new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    document.addEventListener('submit', (event) => {
      if (event.target?.id === 'settings-form') setTimeout(schedule, 0);
    });
    document.addEventListener('click', (event) => {
      if (event.target.closest?.('#test-key, #continue-no-key, #save-settings')) setTimeout(schedule, 0);
    });
    schedule();
  }

  if (document.readyState === 'loading') window.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
