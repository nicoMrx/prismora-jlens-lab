(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const language = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  let scheduled = false;

  function ensureCampaignNav(active) {
    const nav = $('#sidebar-nav');
    const controlActive = $('#lvl-control')?.classList.contains('active');
    if (!nav || !controlActive) return;
    let button = nav.querySelector('[data-nav="campaigns"]');
    if (!button) {
      button = document.createElement('button');
      button.type = 'button';
      button.className = 'nav-button';
      button.dataset.nav = 'campaigns';
      const before = nav.querySelector('[data-nav="runs"], [data-nav="claims"], [data-nav="demos"]');
      nav.insertBefore(button, before || null);
    }
    const label = language() === 'fr' ? 'Campagnes' : 'Campaigns';
    if (button.textContent !== label) button.textContent = label;
    button.classList.toggle('active', Boolean(active));
  }

  function applyCampaignFocus() {
    const screen = $('.screen[data-screen="control"]');
    const panel = $('#campaign-center-panel');
    if (!screen) return;
    const active = Boolean(panel && !panel.hidden && $('#lvl-control')?.classList.contains('active'));
    screen.classList.toggle('campaign-focus', active);
    ensureCampaignNav(active);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      applyCampaignFocus();
    });
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-nav], [data-control-view], [data-level]')) {
      setTimeout(schedule, 0);
    }
  });

  window.addEventListener('DOMContentLoaded', () => {
    const nav = $('#sidebar-nav');
    const screen = $('.screen[data-screen="control"]');
    if (nav) new MutationObserver(schedule).observe(nav, { childList: true, subtree: true });
    if (screen) new MutationObserver(schedule).observe(screen, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['hidden', 'class'],
    });
    new MutationObserver(schedule).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['lang'],
    });
    schedule();
  });
})();