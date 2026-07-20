(() => {
  'use strict';

  const CAMPAIGN_DEMO_KEY = 'prismora.v4.loadCampaignDemo';
  const $ = (selector, root = document) => root.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';

  const warningTranslations = new Map([
    [
      'Campaign is still draft; lock the compiled experiments before describing results as preregistered.',
      'La campagne est encore en brouillon ; verrouillez les expériences compilées avant de présenter les résultats comme préenregistrés.',
    ],
    [
      'Run a single preflight and a repeated noise-floor check before scaling the complete campaign.',
      'Lancez un préflight unique puis une mesure répétée du plancher de bruit avant de déployer la campagne complète.',
    ],
    [
      'Raw responses are immutable evidence and must never be edited in place.',
      'Les réponses brutes sont des preuves immuables et ne doivent jamais être modifiées sur place.',
    ],
  ]);

  function setDisabled(node, value) {
    if (node && node.disabled !== value) node.disabled = value;
  }

  function leadingCount(node) {
    const match = String(node?.textContent || '').match(/^\s*(\d+)\b/);
    return match ? Number(match[1]) : null;
  }

  function localizeCampaignWarnings() {
    if (language() !== 'fr') return;
    document.querySelectorAll('.campaign-warnings li').forEach((item) => {
      const translated = warningTranslations.get(item.textContent.trim());
      if (translated) item.textContent = translated;
    });
  }

  function enforceCampaignGuards() {
    const card = $('.campaign-progress-card');
    if (!card) {
      localizeCampaignWarnings();
      return;
    }
    const title = $('h3', card)?.textContent || '';
    const locked = /verrouillée|locked/i.test(title);
    const meta = [...card.querySelectorAll('.campaign-progress-meta span')];
    const completed = meta.find((node) => /terminés|completed/i.test(node.textContent));
    const remaining = meta.find((node) => /restants|remaining/i.test(node.textContent));
    const completedCount = leadingCount(completed);
    const remainingCount = leadingCount(remaining);

    const lock = [...card.querySelectorAll('button')]
      .find((button) => /verrouiller|lock protocol/i.test(button.textContent));
    if (lock) {
      setDisabled(lock, locked || completedCount === 0);
      lock.title = completedCount === 0
        ? (language() === 'fr'
          ? 'Un préflight réussi est requis avant verrouillage.'
          : 'A successful preflight is required before locking.')
        : '';
    }

    const run = [...card.querySelectorAll('button')]
      .find((button) => /prochain lot|next batch/i.test(button.textContent));
    if (run) {
      setDisabled(run, !locked || remainingCount === 0);
      run.title = !locked
        ? (language() === 'fr'
          ? 'Verrouillez le protocole après le préflight avant une exécution par lots.'
          : 'Lock the protocol after preflight before batch execution.')
        : '';
    }
    localizeCampaignWarnings();
  }

  function restoreCampaignDemo() {
    if (sessionStorage.getItem(CAMPAIGN_DEMO_KEY) !== '1') return;
    let attempts = 0;
    const step = () => {
      attempts += 1;
      const control = $('#lvl-control');
      if (control && !control.classList.contains('active')) control.click();
      const target = $('[data-nav="campaigns"]') || $('[data-control-view="campaigns"]');
      if (target) target.click();
      const demo = $('.campaign-demo');
      if (demo) {
        sessionStorage.removeItem(CAMPAIGN_DEMO_KEY);
        demo.click();
        return;
      }
      if (attempts < 120) requestAnimationFrame(step);
    };
    step();
  }

  window.addEventListener('DOMContentLoaded', () => {
    restoreCampaignDemo();
    const root = $('.screen[data-screen="control"]') || document.body;
    new MutationObserver(enforceCampaignGuards).observe(root, {
      childList: true, subtree: true, attributes: true, attributeFilter: ['disabled'],
    });
    new MutationObserver(enforceCampaignGuards).observe(document.documentElement, {
      attributes: true, attributeFilter: ['lang'],
    });
    enforceCampaignGuards();
  });
})();
