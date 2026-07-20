(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const lang = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  const copy = {
    fr: { title:'Interventions', subtitle:'Déclarations présentes dans la requête, sans déduire un effet causal.', noArtifact:'Chargez une démo ou un export local.', none:'Aucune intervention n’est déclarée dans cet artifact.', operation:'Opération', layers:'Couches déclarées', strength:'Force', tokens:'Tokens dirigés', swap:'Token de remplacement', ablation:'Ablation', yes:'oui', no:'non', unavailable:'non disponible', guard:'Une intervention déclarée et une divergence mesurée ne constituent pas, à elles seules, une preuve causale.', open:'Ouvrir le laboratoire causal' },
    en: { title:'Interventions', subtitle:'Declarations present in the request, without inferring a causal effect.', noArtifact:'Load a demo or local export.', none:'No intervention is declared in this artifact.', operation:'Operation', layers:'Declared layers', strength:'Strength', tokens:'Steered tokens', swap:'Swap token', ablation:'Ablation', yes:'yes', no:'no', unavailable:'unavailable', guard:'A declared intervention and a measured divergence do not, by themselves, establish causal proof.', open:'Open Causal Lab' },
  };
  const t = (key) => copy[lang()][key];

  function panel() {
    const host = $('#explorer-subview-host');
    if (!host) return null;
    let node = $('#explorer-interventions-view');
    if (!node) {
      node = document.createElement('section'); node.id = 'explorer-interventions-view'; node.className = 'explorer-subview card'; node.dataset.explorerPanel = 'interventions'; host.append(node);
    }
    return node;
  }
  function valueLabel(value) {
    if (!value) return t('unavailable');
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map(valueLabel).join(', ');
    return value.token || value.name || JSON.stringify(value);
  }
  function dataFor(artifact) {
    const request = artifact?.request || {}; const explicit = request.intervention || {}; const layers = [];
    if (Number.isInteger(explicit.layer)) layers.push(explicit.layer);
    if (Array.isArray(explicit.layers)) layers.push(...explicit.layers.filter(Number.isInteger));
    if (Array.isArray(request.steerLayers)) layers.push(...request.steerLayers.filter(Number.isInteger));
    const tokens = explicit.steerTokens || request.steerTokens || []; const swap = explicit.swapToken || request.swapToken || null;
    const ablation = explicit.steerAblate ?? request.steerAblate ?? false; const strength = explicit.steerStrength ?? request.steerStrength ?? explicit.strength ?? null;
    return { declared:Boolean(Object.keys(explicit).length || layers.length || tokens.length || swap || ablation || strength !== null), layers:[...new Set(layers)], tokens, swap, ablation, strength };
  }
  function fact(label, value) { const row=document.createElement('div'); row.className='explorer-fact'; row.innerHTML='<span></span><strong></strong>'; row.children[0].textContent=label; row.children[1].textContent=value; return row; }
  function render(detail) {
    const node=panel(); if(!node)return; node.replaceChildren();
    const title=document.createElement('h2'); title.textContent=t('title'); const subtitle=document.createElement('p'); subtitle.className='explorer-subview-subtitle'; subtitle.textContent=t('subtitle'); node.append(title,subtitle);
    const artifact=detail?.session?.artifact; if(artifact?.schema!=='prismora.run/v2'){const empty=document.createElement('p');empty.className='explorer-subview-empty';empty.textContent=t('noArtifact');node.append(empty);return;}
    const data=dataFor(artifact);
    if(!data.declared){const empty=document.createElement('p');empty.className='explorer-subview-empty';empty.textContent=t('none');node.append(empty);}else{
      const operations=[];if(data.tokens.length)operations.push('steer');if(data.swap)operations.push('swap');if(data.ablation)operations.push('ablation');
      const grid=document.createElement('div');grid.className='explorer-fact-grid';grid.append(fact(t('operation'),operations.join(' + ')||t('unavailable')),fact(t('layers'),data.layers.join(', ')||t('unavailable')),fact(t('strength'),data.strength===null?t('unavailable'):String(data.strength)),fact(t('tokens'),valueLabel(data.tokens)),fact(t('swap'),valueLabel(data.swap)),fact(t('ablation'),data.ablation?t('yes'):t('no')));node.append(grid);
    }
    const guard=document.createElement('p');guard.className='explorer-causal-guard';guard.textContent=t('guard');node.append(guard);const actions=document.createElement('div');actions.className='explorer-subview-actions';actions.innerHTML=`<a href="/#causal">${t('open')}</a>`;node.append(actions);
  }
  document.addEventListener('prismora:explorer-view',(event)=>{panel();if(event.detail?.view==='interventions')render(event.detail);});
})();
