(() => {
  'use strict';

  const CAMPAIGN_DEMO_KEY = 'prismora.v4.loadCampaignDemo';
  const $ = (selector, root = document) => root.querySelector(selector);

  function leadingCount(node) {
    const match = String(node?.textContent || '').match(/^\s*(\d+)\b/);
    return match ? Number(match[1]) : null;
  }

  function enforceCampaignGuards() {
    const card = $('.campaign-progress-card');
    if (!card) return;
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
      lock.disabled = locked || completedCount === 0;
      lock.title = completedCount === 0
        ? 'Un préflight réussi est requis avant verrouillage.'
        : '';
    }

    const run = [...card.querySelectorAll('button')]
      .find((button) => /prochain lot|next batch/i.test(button.textContent));
    if (run) {
      run.disabled = !locked || remainingCount === 0;
      run.title = !locked
        ? 'Verrouillez le protocole après le préflight avant une exécution par lots.'
        : '';
    }
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
    enforceCampaignGuards();
  });
})();
