(() => {
  'use strict';

  let lastLayer = null;
  let scheduledLayer = null;
  let frame = 0;

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  function railEntries() {
    const buttons = $$('#layer-rail .layer-button');
    const numbers = $$('#layer-rail .layer-number');
    return buttons.map((button, index) => ({
      button,
      layer: Number(numbers[index]?.textContent),
    })).filter((entry) => Number.isFinite(entry.layer));
  }

  function activateLayer(layer) {
    if (!Number.isFinite(layer) || layer === lastLayer) return;
    scheduledLayer = layer;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const entry = railEntries().find((row) => row.layer === scheduledLayer);
      if (!entry || entry.button.classList.contains('active')) {
        lastLayer = scheduledLayer;
        return;
      }
      lastLayer = scheduledLayer;
      entry.button.click();
    });
  }

  function nearestLayerFromRail(clientX, rail) {
    const entries = railEntries();
    if (!entries.length) return null;
    const rect = rail.getBoundingClientRect();
    const x = Math.max(rect.left, Math.min(rect.right, clientX));
    let nearest = entries[0];
    let distance = Infinity;
    entries.forEach((entry) => {
      const buttonRect = entry.button.getBoundingClientRect();
      const center = buttonRect.left + buttonRect.width / 2;
      const current = Math.abs(center - x);
      if (current < distance) {
        distance = current;
        nearest = entry;
      }
    });
    return nearest.layer;
  }

  function nearestLayerFromOverlay(clientX, chart) {
    const entries = railEntries();
    if (!entries.length) return null;
    const rect = chart.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / Math.max(1, rect.width)));
    const targetIndex = Math.round(ratio * (entries.length - 1));
    return entries[targetIndex]?.layer ?? null;
  }

  function suppressNativeOverlayTooltips(chart) {
    chart.querySelectorAll('title').forEach((title) => title.remove());
  }

  function ensureHoverBadge() {
    let badge = $('#layer-hover-badge');
    if (!badge) {
      badge = document.createElement('div');
      badge.id = 'layer-hover-badge';
      badge.className = 'layer-hover-badge';
      badge.setAttribute('aria-hidden', 'true');
      document.body.append(badge);
    }
    return badge;
  }

  function showBadge(event, layer) {
    const badge = ensureHoverBadge();
    badge.textContent = `${document.documentElement.lang === 'fr' ? 'Couche' : 'Layer'} ${layer}`;
    badge.classList.add('visible');
    const width = badge.offsetWidth || 90;
    const margin = 12;
    let left = event.clientX + 14;
    let top = event.clientY + 14;
    if (left + width + margin > innerWidth) left = event.clientX - width - 14;
    if (top + 40 > innerHeight) top = event.clientY - 40;
    badge.style.left = `${Math.max(margin, left)}px`;
    badge.style.top = `${Math.max(margin, top)}px`;
  }

  function hideBadge() {
    $('#layer-hover-badge')?.classList.remove('visible');
  }

  function resetHover() {
    hideBadge();
    lastLayer = null;
  }

  document.addEventListener('pointermove', (event) => {
    const rail = event.target.closest?.('#layer-rail');
    if (rail) {
      const layer = nearestLayerFromRail(event.clientX, rail);
      if (layer !== null) {
        activateLayer(layer);
        showBadge(event, layer);
      }
      return;
    }

    const overlay = event.target.closest?.('.lens-overlay-chart');
    if (overlay) {
      suppressNativeOverlayTooltips(overlay);
      const layer = nearestLayerFromOverlay(event.clientX, overlay);
      if (layer !== null) {
        activateLayer(layer);
        showBadge(event, layer);
      }
      return;
    }

    resetHover();
  });

  document.addEventListener('pointerout', (event) => {
    const fromRail = event.target.closest?.('#layer-rail');
    const fromOverlay = event.target.closest?.('.lens-overlay-chart');
    if (!fromRail && !fromOverlay) return;
    const relatedRail = event.relatedTarget?.closest?.('#layer-rail');
    const relatedOverlay = event.relatedTarget?.closest?.('.lens-overlay-chart');
    if (relatedRail || relatedOverlay) return;
    resetHover();
  });

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-level], [data-nav], [data-explorer-view]')) resetHover();
  });
  window.addEventListener('blur', resetHover);
  window.addEventListener('scroll', resetHover, true);
})();