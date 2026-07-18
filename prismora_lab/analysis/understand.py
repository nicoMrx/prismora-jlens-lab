from __future__ import annotations

from typing import Any
from .compare import strict_comparison_facts

TEXT = {
    "en": {
        "coverage.complete.v1": "Coverage is complete for {instrumented_tokens} transmitted context tokens.",
        "coverage.partial.v1": "{instrumented_tokens} transmitted context tokens were instrumented; source truncation is unknown or partial.",
        "coverage.unknown.v1": "Context coverage is unknown.",
        "coverage.instrumented.v1": "{instrumented_tokens} of {transmitted_tokens} transmitted context tokens were instrumented; {instrumented_generated_tokens} generated tokens were instrumented separately.",
        "coverage.truncated.v1": "Known truncation: {truncated_tokens} tokens; message indices {truncated_message_indices}.",
        "coverage.layers.v1": "Requested layers {requested_layers}; captured layers {captured_layers}.",
        "quality.independent.v1": "This run is recorded as an independent observation.",
        "quality.duplicate.v1": "This run duplicates {duplicate_of} and is not independent evidence.",
        "quality.synthetic.v1": "This is synthetic/mock demo data, not model-cognition evidence.",
        "compare.scope.v1": "Scope {scope_label}: {scope_warning}",
        "compare.surface.same.v1": "The generated surface is identical for this pair.",
        "compare.surface.different.v1": "The generated surface is different for this pair.",
        "compare.top1.v1": "The first top-1 divergence in {scope_label} is at layer {layer}, position {position}.",
        "compare.top1.none.v1": "No top-1 divergence was measurable in {scope_label}.",
        "compare.strict.v1": "The first strict top-k/probability divergence in {scope_label} is at layer {layer}, position {position}.",
        "compare.strict.none.v1": "No strict top-k/probability divergence was measurable in {scope_label}.",
        "compare.intervention.member.v1": "Measured first divergence layer {layer} belongs to the declared intervention layers {declared_layers}.",
        "compare.intervention.differs.v1": "Measured first divergence layer {layer} does not belong to the declared intervention layers {declared_layers}.",
        "compare.caution.v1": "A readout divergence alone is not semantic interpretation or causal proof.",
        "locale.fallback.v1": "Requested locale {requested_locale} is unsupported; English was used.",
    },
    "fr": {
        "coverage.complete.v1": "La couverture est complète pour {instrumented_tokens} jetons de contexte transmis.",
        "coverage.partial.v1": "{instrumented_tokens} jetons de contexte transmis ont été instrumentés ; la troncature source est inconnue ou partielle.",
        "coverage.unknown.v1": "La couverture du contexte est inconnue.",
        "coverage.instrumented.v1": "{instrumented_tokens} des {transmitted_tokens} jetons de contexte transmis ont été instrumentés ; {instrumented_generated_tokens} jetons générés ont été instrumentés séparément.",
        "coverage.truncated.v1": "Troncature connue : {truncated_tokens} jetons ; indices de messages {truncated_message_indices}.",
        "coverage.layers.v1": "Couches demandées {requested_layers} ; couches capturées {captured_layers}.",
        "quality.independent.v1": "Ce run est enregistré comme observation indépendante.",
        "quality.duplicate.v1": "Ce run duplique {duplicate_of} et ne constitue pas une preuve indépendante.",
        "quality.synthetic.v1": "Ce sont des données synthétiques/mock de démonstration, pas une preuve de cognition du modèle.",
        "compare.scope.v1": "Portée {scope_label} : {scope_warning}",
        "compare.surface.same.v1": "La surface générée est identique pour cette paire.",
        "compare.surface.different.v1": "La surface générée est différente pour cette paire.",
        "compare.top1.v1": "La première divergence top-1 dans {scope_label} est à la couche {layer}, position {position}.",
        "compare.top1.none.v1": "Aucune divergence top-1 n’est mesurable dans {scope_label}.",
        "compare.strict.v1": "La première divergence stricte top-k/probabilité dans {scope_label} est à la couche {layer}, position {position}.",
        "compare.strict.none.v1": "Aucune divergence stricte top-k/probabilité n’est mesurable dans {scope_label}.",
        "compare.intervention.member.v1": "La première couche de divergence mesurée {layer} appartient aux couches d’intervention déclarées {declared_layers}.",
        "compare.intervention.differs.v1": "La première couche de divergence mesurée {layer} n’appartient pas aux couches d’intervention déclarées {declared_layers}.",
        "compare.caution.v1": "Une divergence de readout seule n’est pas une interprétation sémantique ni une preuve causale.",
        "locale.fallback.v1": "La langue demandée {requested_locale} n’est pas prise en charge ; l’anglais est utilisé.",
    },
}
SCOPE_LABEL = {"en": {"prompt_fixed":"prompt context","generated_ordinal":"generated response","all":"prompt context and generated response"}, "fr": {"prompt_fixed":"contexte du prompt","generated_ordinal":"réponse générée","all":"contexte du prompt et réponse générée"}}
SCOPE_WARNING = {"prompt_fixed":"prompt tokens are aligned by position and token ID", "generated_ordinal":"generated tokens are aligned by ordinal position only; no semantic alignment is attempted", "all":"prompt and generated positions are reported as separate scopes"}

def _pick(locale: str) -> str: return locale if locale in TEXT else "en"
def _ev(path: str, value: Any) -> dict[str, Any]: return {"path": path, "value": value}
def _sent(locale: str, rule: str, tid: str, sev: str, ev: list[dict[str, Any]]) -> dict[str, Any]:
    vals = {e["path"].split(".")[-1]: e["value"] for e in ev}
    return {"rule_id": rule, "template_id": tid, "text": TEXT[locale][tid].format(**vals), "severity": sev, "evidence": ev}

def _declared_layers(*arts: dict[str, Any]) -> list[int]:
    layers: list[int] = []
    for art in arts:
        intervention = art.get("request", {}).get("intervention") or {}
        if isinstance(intervention.get("layer"), int): layers.append(intervention["layer"])
        plural = intervention.get("layers")
        if isinstance(plural, list): layers.extend(x for x in plural if isinstance(x, int))
    return sorted(set(layers))

def understand_run(artifact: dict[str, Any], locale: str = "en") -> dict[str, Any]:
    loc = _pick(locale); sentences: list[dict[str, Any]] = []
    if loc != locale: sentences.append(_sent(loc, "locale.fallback", "locale.fallback.v1", "warning", [_ev("requested_locale", locale)]))
    cov = artifact.get("coverage") or {}; status = cov.get("status", "unknown")
    tid = {"complete":"coverage.complete.v1", "partial":"coverage.partial.v1"}.get(status, "coverage.unknown.v1")
    sentences.append(_sent(loc, f"coverage.{status}", tid, "warning" if status != "complete" else "info", [_ev("coverage.instrumented_tokens", cov.get("instrumented_tokens")), _ev("coverage.status", status)]))
    if cov.get("transmitted_tokens") is not None:
        sentences.append(_sent(loc, "coverage.instrumented", "coverage.instrumented.v1", "info", [_ev("coverage.instrumented_tokens", cov.get("instrumented_tokens")), _ev("coverage.transmitted_tokens", cov.get("transmitted_tokens")), _ev("coverage.instrumented_generated_tokens", cov.get("instrumented_generated_tokens"))]))
    if cov.get("truncated_tokens") not in (None, 0) or cov.get("truncated_message_indices"):
        sentences.append(_sent(loc, "coverage.truncated", "coverage.truncated.v1", "warning", [_ev("coverage.truncated_tokens", cov.get("truncated_tokens")), _ev("coverage.truncated_message_indices", cov.get("truncated_message_indices", []))]))
    sentences.append(_sent(loc, "coverage.layers", "coverage.layers.v1", "info", [_ev("coverage.requested_layers", cov.get("requested_layers", [])), _ev("coverage.captured_layers", cov.get("captured_layers", []))]))
    q = artifact.get("quality", {})
    if q.get("independent_observation"): sentences.append(_sent(loc, "quality.independent", "quality.independent.v1", "info", [_ev("quality.independent_observation", True)]))
    else: sentences.append(_sent(loc, "quality.duplicate", "quality.duplicate.v1", "warning", [_ev("quality.duplicate_of", q.get("duplicate_of"))]))
    if artifact.get("result", {}).get("meta", {}).get("mock") or artifact.get("request", {}).get("factors", {}).get("demo"):
        sentences.append(_sent(loc, "quality.synthetic", "quality.synthetic.v1", "warning", [_ev("result.meta.mock", artifact.get("result", {}).get("meta", {}).get("mock"))]))
    return {"schema":"prismora.understand/v1", "locale":loc, "subject":{"run_ids":[artifact["run_id"]]}, "sentences":sentences, "warnings":[] if loc == locale else [sentences[0]["text"]]}

def _scope_sentences(loc: str, facts: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    label = SCOPE_LABEL[loc][scope]
    out = [_sent(loc, f"compare.scope.{scope}", "compare.scope.v1", "warning" if scope == "generated_ordinal" else "info", [_ev("scope_label", label), _ev("scope_warning", SCOPE_WARNING[scope])])]
    fs = facts["first_strict_divergence"]; ft = facts["first_top1_divergence"]
    out.append(_sent(loc, "compare.strict" if fs else "compare.strict.none", "compare.strict.v1" if fs else "compare.strict.none.v1", "warning" if fs else "info", [_ev("scope_label", label), _ev("layer", fs.get("layer") if fs else None), _ev("position", fs.get("position") if fs else None)]))
    out.append(_sent(loc, "compare.top1" if ft else "compare.top1.none", "compare.top1.v1" if ft else "compare.top1.none.v1", "warning" if ft else "info", [_ev("scope_label", label), _ev("layer", ft.get("layer") if ft else None), _ev("position", ft.get("position") if ft else None)]))
    return out

def understand_compare(a: dict[str, Any], b: dict[str, Any], *, lens="JACOBIAN_LENS", scope="prompt_fixed", locale="en", probability_abs_tolerance=0.0) -> dict[str, Any]:
    loc = _pick(locale); sentences: list[dict[str, Any]] = []
    if loc != locale: sentences.append(_sent(loc, "locale.fallback", "locale.fallback.v1", "warning", [_ev("requested_locale", locale)]))
    scopes = ["prompt_fixed", "generated_ordinal"] if scope == "all" else [scope]
    facts_by_scope = {s: strict_comparison_facts(a, b, lens, scope=s, probability_abs_tolerance=probability_abs_tolerance) for s in scopes}
    first_facts = facts_by_scope[scopes[0]]
    sentences.append(_sent(loc, "compare.surface.same" if first_facts["generated_token_ids_identical"] else "compare.surface.different", "compare.surface.same.v1" if first_facts["generated_token_ids_identical"] else "compare.surface.different.v1", "info", [_ev("compare.generated_token_ids_identical", first_facts["generated_token_ids_identical"])]))
    for s in scopes: sentences.extend(_scope_sentences(loc, facts_by_scope[s], s))
    declared = _declared_layers(a, b)
    first_strict = next((facts_by_scope[s]["first_strict_divergence"] for s in scopes if facts_by_scope[s]["first_strict_divergence"]), None)
    if declared and first_strict:
        member = first_strict["layer"] in declared
        sentences.append(_sent(loc, "compare.intervention.member" if member else "compare.intervention.differs", "compare.intervention.member.v1" if member else "compare.intervention.differs.v1", "info" if member else "warning", [_ev("layer", first_strict["layer"]), _ev("declared_layers", declared)]))
    sentences.append(_sent(loc, "compare.caution", "compare.caution.v1", "warning", [_ev("compare.first_strict_divergence", first_strict)]))
    warnings = [w for facts in facts_by_scope.values() for w in facts["warnings"]]
    return {"schema":"prismora.understand/v1", "locale":loc, "subject":{"run_ids":[a["run_id"], b["run_id"]]}, "sentences":sentences, "facts": facts_by_scope[scopes[0]] if len(scopes) == 1 else {"schema":"prismora.compare_facts.composite/v1", "scopes": facts_by_scope}, "warnings": warnings}
