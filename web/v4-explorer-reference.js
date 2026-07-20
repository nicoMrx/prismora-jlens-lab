(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const lang = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  const copy = {
    fr: { title:'Références', subtitle:'Provenance, couverture et limites de l’artifact chargé.', no:'Chargez une démo ou un export local.', run:'Exécution', model:'Modèle', source:'Source', file:'Fichier source', lenses:'Lentilles', layers:'Couches capturées', coverage:'Couverture', status:'Statut', synthetic:'Démonstration synthétique', measured:'Artifact mesuré', unavailable:'non disponible', baseline:'Ouvrir le laboratoire de référence', raw:'Ouvrir les exécutions et données brutes' },
    en: { title:'References', subtitle:'Provenance, coverage and limitations of the loaded artifact.', no:'Load a demo or local export.', run:'Run', model:'Model', source:'Source', file:'Source file', lenses:'Lenses', layers:'Captured layers', coverage:'Coverage', status:'Status', synthetic:'Synthetic demonstration', measured:'Measured artifact', unavailable:'unavailable', baseline:'Open Baseline Lab', raw:'Open runs and exact raw data' },
  };
  const t = (key) => copy[lang()][key];

  function panel() {
    const host = $('#explorer-subview-host');
    if (!host) return null;
    let node = $('#explorer-references-view');
    if (!node) {
      node = document.createElement('section');
      node.id = 'explorer-references-view';
      node.className = 'explorer-subview card';
      node.dataset.explorerPanel = 'baselines';
      node.hidden = true;
      host.append(node);
    }
    return node;
  }

  function fact(label, value) {
    const row = document.createElement('div');
    row.className = 'explorer-fact';
    row.innerHTML = '<span></span><strong></strong>';
    row.children[0].textContent = label;
    row.children[1].textContent = value ?? t('unavailable');
    return row;
  }

  function render(detail) {
    const node = panel();
    if (!node) return;
    node.replaceChildren();
    const title = document.createElement('h2'); title.textContent = t('title');
    const subtitle = document.createElement('p'); subtitle.className = 'explorer-subview-subtitle'; subtitle.textContent = t('subtitle');
    node.append(title, subtitle);
    const artifact = detail?.session?.artifact;
    if (artifact?.schema !== 'prismora.run/v2') {
      const empty = document.createElement('p'); empty.className = 'explorer-subview-empty'; empty.textContent = t('no'); node.append(empty); return;
    }
    const layersByType = artifact?.result?.meta?.layers_by_type || {};
    const allLayers = [...new Set(Object.values(layersByType).flat().filter(Number.isFinite))].sort((a,b)=>a-b);
    const synthetic = Boolean(artifact?.result?.meta?.mock || artifact?.request?.factors?.demo || detail?.session?.sourceType === 'demo');
    const grid = document.createElement('div'); grid.className = 'explorer-fact-grid';
    grid.append(
      fact(t('run'), artifact.run_id || 'local'),
      fact(t('model'), artifact?.request?.model?.model_id || t('unavailable')),
      fact(t('source'), artifact?.provenance?.backend || artifact?.request?.backend || t('unavailable')),
      fact(t('file'), artifact?.provenance?.original_filename || artifact?.provenance?.source || t('unavailable')),
      fact(t('lenses'), Object.keys(layersByType).join(', ') || t('unavailable')),
      fact(t('layers'), allLayers.length ? `${allLayers.length} · ${allLayers[0]}–${allLayers.at(-1)}` : t('unavailable')),
      fact(t('coverage'), artifact?.coverage?.status || t('unavailable')),
      fact(t('status'), synthetic ? t('synthetic') : t('measured')),
    );
    node.append(grid);
    const actions = document.createElement('div'); actions.className = 'explorer-subview-actions';
    actions.innerHTML = `<a href="/#baseline">${t('baseline')}</a><a href="/#runs">${t('raw')}</a>`;
    node.append(actions);
  }

  document.addEventListener('prismora:explorer-view', (event) => {
    const node = panel();
    if (node) node.hidden = event.detail?.view !== 'baselines';
    if (event.detail?.view === 'baselines') render(event.detail);
  });
  document.dispatchEvent(new CustomEvent('prismora:explorer-refresh'));
})();
