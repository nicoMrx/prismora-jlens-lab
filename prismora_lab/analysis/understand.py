from __future__ import annotations

from typing import Any
from .compare import strict_comparison_facts

TEXT = {
 'en': {
  'coverage.complete.v1':'Coverage is complete for {instrumented_tokens} instrumented tokens.',
  'coverage.partial.v1':'{instrumented_tokens} tokens were instrumented; source truncation is unknown or partial.',
  'coverage.unknown.v1':'Context coverage is unknown.',
  'coverage.instrumented.v1':'{instrumented_tokens} of {transmitted_tokens} transmitted tokens were instrumented.',
  'coverage.truncated.v1':'Known truncation: {truncated_tokens} tokens; message indices {truncated_message_indices}.',
  'coverage.layers.v1':'Requested layers {requested_layers}; captured layers {captured_layers}.',
  'quality.independent.v1':'This run is recorded as an independent observation.',
  'quality.duplicate.v1':'This run duplicates {duplicate_of} and is not independent evidence.',
  'quality.synthetic.v1':'This is synthetic/mock demo data, not model-cognition evidence.',
  'compare.surface.same.v1':'The generated surface is identical for this pair.',
  'compare.surface.different.v1':'The generated surface is different for this pair.',
  'compare.top1.v1':'The first top-1 divergence is at layer {layer}, position {position}.',
  'compare.top1.none.v1':'No top-1 divergence was measurable in the compared cells.',
  'compare.strict.v1':'The first strict top-k/probability divergence is at layer {layer}, position {position}.',
  'compare.strict.none.v1':'No strict top-k/probability divergence was measurable in the compared cells.',
  'compare.intervention.coincides.v1':'The declared intervention layer coincides with the measured first divergence layer {layer}.',
  'compare.intervention.differs.v1':'The declared intervention layer {declared_layer} does not coincide with measured first divergence layer {layer}.',
  'compare.caution.v1':'A readout divergence alone is not semantic interpretation or causal proof.',
  'locale.fallback.v1':'Requested locale {requested_locale} is unsupported; English was used.'},
 'fr': {
  'coverage.complete.v1':'La couverture est complète pour {instrumented_tokens} jetons instrumentés.',
  'coverage.partial.v1':'{instrumented_tokens} jetons ont été instrumentés ; la troncature source est inconnue ou partielle.',
  'coverage.unknown.v1':'La couverture du contexte est inconnue.',
  'coverage.instrumented.v1':'{instrumented_tokens} des {transmitted_tokens} jetons transmis ont été instrumentés.',
  'coverage.truncated.v1':'Troncature connue : {truncated_tokens} jetons ; indices de messages {truncated_message_indices}.',
  'coverage.layers.v1':'Couches demandées {requested_layers} ; couches capturées {captured_layers}.',
  'quality.independent.v1':'Ce run est enregistré comme observation indépendante.',
  'quality.duplicate.v1':'Ce run duplique {duplicate_of} et ne constitue pas une preuve indépendante.',
  'quality.synthetic.v1':'Ce sont des données synthétiques/mock de démonstration, pas une preuve de cognition du modèle.',
  'compare.surface.same.v1':'La surface générée est identique pour cette paire.',
  'compare.surface.different.v1':'La surface générée est différente pour cette paire.',
  'compare.top1.v1':'La première divergence top-1 est à la couche {layer}, position {position}.',
  'compare.top1.none.v1':'Aucune divergence top-1 n’est mesurable dans les cellules comparées.',
  'compare.strict.v1':'La première divergence stricte top-k/probabilité est à la couche {layer}, position {position}.',
  'compare.strict.none.v1':'Aucune divergence stricte top-k/probabilité n’est mesurable dans les cellules comparées.',
  'compare.intervention.coincides.v1':'La couche d’intervention déclarée coïncide avec la première divergence mesurée {layer}.',
  'compare.intervention.differs.v1':'La couche d’intervention déclarée {declared_layer} ne coïncide pas avec la première divergence mesurée {layer}.',
  'compare.caution.v1':'Une divergence de readout seule n’est pas une interprétation sémantique ni une preuve causale.',
  'locale.fallback.v1':'La langue demandée {requested_locale} n’est pas prise en charge ; l’anglais est utilisé.'}}

def _pick(locale:str): return locale if locale in TEXT else 'en'
def _sent(locale, rule, tid, sev, ev):
    vals={e['path'].split('.')[-1]: e['value'] for e in ev}; return {'rule_id':rule,'template_id':tid,'text':TEXT[locale][tid].format(**vals),'severity':sev,'evidence':ev}
def _ev(path,v): return {'path':path,'value':v}

def understand_run(artifact:dict[str,Any], locale:str='en')->dict[str,Any]:
    loc=_pick(locale); sentences=[]
    if loc != locale: sentences.append(_sent(loc,'locale.fallback','locale.fallback.v1','warning',[_ev('requested_locale',locale)]))
    cov=artifact.get('coverage') or {}
    status=cov.get('status','unknown')
    tid={'complete':'coverage.complete.v1','partial':'coverage.partial.v1'}.get(status,'coverage.unknown.v1')
    sentences.append(_sent(loc,f'coverage.{status}',tid,'warning' if status!='complete' else 'info',[_ev('coverage.instrumented_tokens',cov.get('instrumented_tokens')),_ev('coverage.status',status)]))
    if cov.get('transmitted_tokens') is not None: sentences.append(_sent(loc,'coverage.instrumented','coverage.instrumented.v1','info',[_ev('coverage.instrumented_tokens',cov.get('instrumented_tokens')),_ev('coverage.transmitted_tokens',cov.get('transmitted_tokens'))]))
    if cov.get('truncated_tokens') not in (None,0) or cov.get('truncated_message_indices'): sentences.append(_sent(loc,'coverage.truncated','coverage.truncated.v1','warning',[_ev('coverage.truncated_tokens',cov.get('truncated_tokens')),_ev('coverage.truncated_message_indices',cov.get('truncated_message_indices',[]))]))
    sentences.append(_sent(loc,'coverage.layers','coverage.layers.v1','info',[_ev('coverage.requested_layers',cov.get('requested_layers',[])),_ev('coverage.captured_layers',cov.get('captured_layers',[]))]))
    q=artifact.get('quality',{})
    if q.get('independent_observation'): sentences.append(_sent(loc,'quality.independent','quality.independent.v1','info',[_ev('quality.independent_observation',True)]))
    else: sentences.append(_sent(loc,'quality.duplicate','quality.duplicate.v1','warning',[_ev('quality.duplicate_of',q.get('duplicate_of'))]))
    if artifact.get('result',{}).get('meta',{}).get('mock') or artifact.get('request',{}).get('factors',{}).get('demo'):
        sentences.append(_sent(loc,'quality.synthetic','quality.synthetic.v1','warning',[_ev('result.meta.mock',artifact.get('result',{}).get('meta',{}).get('mock'))]))
    return {'schema':'prismora.understand/v1','locale':loc,'subject':{'run_ids':[artifact['run_id']]},'sentences':sentences,'warnings':[] if loc==locale else [sentences[0]['text']]}

def understand_compare(a:dict[str,Any], b:dict[str,Any], *, lens='JACOBIAN_LENS', scope='prompt_fixed', locale='en', probability_abs_tolerance=0.0)->dict[str,Any]:
    loc=_pick(locale); facts=strict_comparison_facts(a,b,lens,scope=scope,probability_abs_tolerance=probability_abs_tolerance); sentences=[]
    if loc != locale: sentences.append(_sent(loc,'locale.fallback','locale.fallback.v1','warning',[_ev('requested_locale',locale)]))
    sentences.append(_sent(loc,'compare.surface.same' if facts['generated_token_ids_identical'] else 'compare.surface.different','compare.surface.same.v1' if facts['generated_token_ids_identical'] else 'compare.surface.different.v1','info',[_ev('compare.generated_token_ids_identical',facts['generated_token_ids_identical'])]))
    fs=facts['first_strict_divergence']; ft=facts['first_top1_divergence']
    sentences.append(_sent(loc,'compare.strict' if fs else 'compare.strict.none','compare.strict.v1' if fs else 'compare.strict.none.v1','warning' if fs else 'info',[_ev('layer',fs.get('layer') if fs else None),_ev('position',fs.get('position') if fs else None)]))
    sentences.append(_sent(loc,'compare.top1' if ft else 'compare.top1.none','compare.top1.v1' if ft else 'compare.top1.none.v1','warning' if ft else 'info',[_ev('layer',ft.get('layer') if ft else None),_ev('position',ft.get('position') if ft else None)]))
    declared=(b.get('request',{}).get('intervention') or {}).get('layer') or (a.get('request',{}).get('intervention') or {}).get('layer')
    if declared is not None and fs: sentences.append(_sent(loc,'compare.intervention.coincides' if declared==fs['layer'] else 'compare.intervention.differs','compare.intervention.coincides.v1' if declared==fs['layer'] else 'compare.intervention.differs.v1','info' if declared==fs['layer'] else 'warning',[_ev('declared_layer',declared),_ev('layer',fs['layer'])]))
    sentences.append(_sent(loc,'compare.caution','compare.caution.v1','warning',[_ev('compare.first_strict_divergence',fs)]))
    return {'schema':'prismora.understand/v1','locale':loc,'subject':{'run_ids':[a['run_id'],b['run_id']]},'sentences':sentences,'facts':facts,'warnings':facts['warnings']}
