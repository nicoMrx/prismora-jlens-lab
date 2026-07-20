(() => {
  'use strict';

  const CAMPAIGN_DEMO_KEY = 'prismora.v4.loadCampaignDemo';
  const $ = (selector, root = document) => root.querySelector(selector);

  function enforceCampaignGuards() {
    const card = $('.campaign-progress-card');
    if (!card) return;
    const title = $('h3', card)?.textContent || '';
    const lock = [...card.querySelectorAll('button')].find((button) => /verrouiller|lock protocol/i.test(button.textContent));
    if (lock && /verrouillée|locked/i.test(title)) lock.disabled = true;

    const remaining = [...card.querySelectorAll('.campaign-progress-meta span')]
      .find((node) => /restants|remaining/i.test(node.textContent));
    const run = [...card.querySelectorAll('button')].find((button) => /prochain lot|next batch/i.test(button.textContent));
    if (run && remaining && /^\s*0\b/.test(remaining.textContent)) run.disabled = true;
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
