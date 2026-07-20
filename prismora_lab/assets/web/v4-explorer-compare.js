(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const lang = () => document.documentElement.lang === 'fr' ? 'fr' : 'en';
  const copy = {
    fr: { title:'Comparaison A/B', subtitle:'Comparer deux artifacts vérifiés sans modifier les données chargées.', no:'Un second artifact compatible est nécessaire. Le run chargé reste intact.', loading:'Chargement de la paire A vérifiée…', error:'La comparaison vérifiée n’a pas pu être produite.', pair:'Paire A vérifiée · contrôle ↔ variation', why:'Pourquoi cette phrase ?', rule:'Règle', evidence:'Preuves', open:'Ouvrir la comparaison A/B complète' },
    en: { title:'A/B comparison', subtitle:'Compare two verified artifacts without modifying the loaded data.', no:'A second compatible artifact is required. The loaded run remains unchanged.', loading:'Loading verified Pair A…', error:'The verified comparison could not be produced.', pair:'Verified Pair A · control ↔ shift', why:'Why this sentence?', rule:'Rule', evidence:'Evidence', open:'Open the complete A/B comparison' },
  };
  const t = (key) => copy[lang()][key];
  let requestSequence = 0;

  function panel() {
    const host = $('#explorer-subview-host');
    if (!host) return null;
    let node = $('#explorer-compare-view');
    if (!node) { node=document.createElement('section');node.id='explorer-compare-view';node.className='explorer-subview card';node.dataset.explorerPanel='compare';host.append(node); }
    return node;
  }
  function heading(node){node.replaceChildren();const title=document.createElement('h2');title.textContent=t('title');const subtitle=document.createElement('p');subtitle.className='explorer-subview-subtitle';subtitle.textContent=t('subtitle');node.append(title,subtitle);}
  async function api(payload){const response=await fetch('/api/demo/build-week/understand/compare',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});const text=await response.text();let value;try{value=text?JSON.parse(text):null;}catch{value=text;}if(!response.ok)throw new Error(value?.detail?.message||value?.detail||value?.message||text||String(response.status));return value;}
  function sentenceCard(sentence){const article=document.createElement('article');article.className=`explorer-sentence ${sentence.severity||'info'}`;const text=document.createElement('p');text.textContent=sentence.text||'';const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent=t('why');const rule=document.createElement('div');rule.className='explorer-rule';rule.textContent=`${t('rule')} · ${sentence.rule_id||'—'} · ${sentence.template_id||'—'}`;const evidence=document.createElement('pre');evidence.textContent=`${t('evidence')}\n${JSON.stringify(sentence.evidence||[],null,2)}`;details.append(summary,rule,evidence);article.append(text,details);return article;}
  async function render(detail){
    const node=panel();if(!node)return;heading(node);const artifact=detail?.session?.artifact;const isDemo=artifact?.run_id?.startsWith('demo-pair-a-')||detail?.session?.sourceType==='demo';
    if(!isDemo){const empty=document.createElement('p');empty.className='explorer-subview-empty';empty.textContent=t('no');node.append(empty);const actions=document.createElement('div');actions.className='explorer-subview-actions';actions.innerHTML=`<a href="/#visualizer">${t('open')}</a>`;node.append(actions);return;}
    const loading=document.createElement('p');loading.className='explorer-subview-empty';loading.textContent=t('loading');node.append(loading);const sequence=++requestSequence;const locale=lang();const lenses=Object.keys(artifact?.result?.meta?.layers_by_type||{});const lens=$('#lens-select')?.value||(lenses.includes('JACOBIAN_LENS')?'JACOBIAN_LENS':lenses[0]||'JACOBIAN_LENS');
    try{const payload=await api({run_a:'demo-pair-a-control',run_b:'demo-pair-a-shift',lens,scope:'all',locale,probability_abs_tolerance:0});if(sequence!==requestSequence||locale!==lang())return;heading(node);const badge=document.createElement('div');badge.className='explorer-pair-badge';badge.textContent=t('pair');const list=document.createElement('div');list.className='explorer-sentence-list';(payload.sentences||[]).forEach(sentence=>list.append(sentenceCard(sentence)));const actions=document.createElement('div');actions.className='explorer-subview-actions';actions.innerHTML=`<a href="/#visualizer">${t('open')}</a>`;node.append(badge,list,actions);}catch(error){if(sequence!==requestSequence)return;heading(node);const failure=document.createElement('p');failure.className='explorer-subview-error';failure.textContent=`${t('error')} ${error.message}`;node.append(failure);}
  }
  document.addEventListener('prismora:explorer-view',(event)=>{panel();if(event.detail?.view==='compare')render(event.detail);else requestSequence+=1;});
})();
