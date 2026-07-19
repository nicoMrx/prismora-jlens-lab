import copy, hashlib, json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prismora_lab.analysis.compare import strict_comparison_facts
from prismora_lab.analysis.understand import understand_compare, understand_run
from prismora_lab.api.app import create_app
from prismora_lab.config import Settings
from prismora_lab.coverage import validate_coverage
from prismora_lab.demo import verify_demo_manifest
from prismora_lab.schema import validate
from prismora_lab.store import LabStore

ROOT = Path(__file__).resolve().parents[1]


def demo(name):
    return json.loads((ROOT / 'demo' / 'build_week_2026' / f'{name}.json').read_text())


def test_run_schema_backward_compatible_and_coverage_validates():
    old = demo('demo-pair-a-control')
    old.pop('coverage')
    validate('run', old)
    new = demo('demo-pair-a-control')
    validate('run', new)
    cov = validate_coverage(new['coverage'])
    assert cov['source_tokens_total'] == 2
    assert cov['transmitted_tokens'] == 2
    assert cov['instrumented_tokens'] == 2
    assert cov['instrumented_generated_tokens'] == 1
    bad = copy.deepcopy(new['coverage']); bad['transmitted_tokens'] = -1
    with pytest.raises(ValueError):
        validate_coverage(bad)
    bad = copy.deepcopy(new['coverage']); bad['instrumented_tokens'] = bad['transmitted_tokens'] + 1
    with pytest.raises(ValueError):
        validate_coverage(bad)
    bad = copy.deepcopy(new['coverage']); bad['source_tokens_total'] = None
    with pytest.raises(ValueError):
        validate_coverage(bad)


def test_understand_deterministic_bilingual_and_evidence():
    art = demo('demo-pair-a-control')
    a = understand_run(art, locale='en')
    b = understand_run(art, locale='en')
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)
    fr = understand_run(art, locale='fr')
    assert fr['locale'] == 'fr'
    fb = understand_run(art, locale='de')
    assert fb['locale'] == 'en' and fb['warnings']
    for sentence in a['sentences']:
        assert sentence['rule_id'] and sentence['template_id'] and sentence['evidence'] is not None


def test_compare_first_divergence_at_intervention_layer_and_no_before():
    a = demo('demo-pair-a-control'); b = demo('demo-pair-a-shift')
    facts = strict_comparison_facts(a, b, 'JACOBIAN_LENS', scope='prompt_fixed', probability_abs_tolerance=0)
    assert facts['generated_token_ids_identical'] is True
    assert facts['first_strict_divergence'] is None
    assert all(r['strict_divergence_rate'] == 0 for r in facts['per_layer'] if r['strict_divergence_rate'] is not None)
    generated_facts = strict_comparison_facts(a, b, 'JACOBIAN_LENS', scope='generated_ordinal', probability_abs_tolerance=0)
    assert generated_facts['first_strict_divergence']['layer'] == 40
    assert b['request']['intervention']['layers'] == [40]
    narrative = understand_compare(a, b, lens='JACOBIAN_LENS', scope='generated_ordinal')
    assert any(s['rule_id'] == 'compare.intervention.member' for s in narrative['sentences'])
    assert any(s['rule_id'] == 'compare.caution' for s in narrative['sentences'])


def test_missing_malformed_cells_warn():
    a = demo('demo-pair-a-control'); b = demo('demo-pair-a-shift')
    b['result']['tokens'][0]['results'][0]['top_tokens'].pop()
    facts = strict_comparison_facts(a, b, 'JACOBIAN_LENS')
    assert facts['missing_cells']
    assert facts['warnings']


def test_understand_api_endpoints(tmp_path):
    store = LabStore(tmp_path)
    for art in [demo('demo-pair-a-control'), demo('demo-pair-a-shift')]:
        store.save_run(art)
    client = TestClient(create_app(Settings(data_dir=tmp_path, neuronpedia_api_key=None, worker_url=None), store=store))
    assert client.get('/api/runs/demo-pair-a-control/understand?locale=fr').status_code == 200
    response = client.post('/api/understand/compare', json={'run_a':'demo-pair-a-control','run_b':'demo-pair-a-shift','lens':'JACOBIAN_LENS','scope':'prompt_fixed','locale':'en','probability_abs_tolerance':0})
    assert response.status_code == 200
    assert response.json()['facts']['first_strict_divergence'] is None
    composite = client.post('/api/understand/compare', json={'run_a':'demo-pair-a-control','run_b':'demo-pair-a-shift','lens':'JACOBIAN_LENS','scope':'all','locale':'en','probability_abs_tolerance':0})
    assert composite.status_code == 200
    assert set(composite.json()['facts']['scopes']) == {'prompt_fixed', 'generated_ordinal'}
    demo_response = client.get('/api/demo/build-week')
    assert demo_response.status_code == 200 and len(demo_response.json()['artifacts']) == 4
    demo_understand = client.post('/api/demo/build-week/understand/compare', json={'run_a':'demo-pair-a-control','run_b':'demo-pair-a-shift','lens':'JACOBIAN_LENS','scope':'all','locale':'fr','probability_abs_tolerance':0})
    assert demo_understand.status_code == 200
    demo_rules = {s['rule_id'] for s in demo_understand.json()['sentences']}
    assert 'compare.scope.generated_ordinal' in demo_rules and 'compare.intervention.member' in demo_rules
    assert client.post('/api/understand/compare', json={'run_a':'demo-pair-a-control'}).status_code == 400


def test_web_assets_synchronized():
    for name in ['index.html','app.js','styles.css']:
        assert (ROOT/'web'/name).read_bytes() == (ROOT/'prismora_lab/assets/web'/name).read_bytes()


def test_demo_manifest_hashes_and_no_secrets():
    manifest = json.loads((ROOT/'demo/build_week_2026/MANIFEST_SHA256.json').read_text())
    forbidden = ['api_key', 'secret', 'Julie', 'Grok', 'OPENAI_API_KEY', 'BEGIN PRIVATE KEY']
    for item in manifest['items']:
        data = (ROOT/'demo/build_week_2026'/item['path']).read_bytes()
        assert len(data) == item['bytes']
        assert hashlib.sha256(data).hexdigest() == item['sha256']
        text = data.decode()
        assert not any(term in text for term in forbidden)


def test_all_scope_reports_generated_divergence_and_ordinal_warning():
    a = demo('demo-pair-a-control'); b = demo('demo-pair-a-shift')
    # Prompt positions are identical in the fixture, while generated positions diverge at layer 40.
    result = understand_compare(a, b, lens='JACOBIAN_LENS', scope='all', locale='en', probability_abs_tolerance=0)
    prompt = result['facts']['scopes']['prompt_fixed']
    generated = result['facts']['scopes']['generated_ordinal']
    assert prompt['first_strict_divergence'] is None
    assert generated['first_strict_divergence']['layer'] == 40
    assert any('ordinal position only' in warning for warning in result['warnings'])
    assert any(sentence['rule_id'] == 'compare.scope.generated_ordinal' for sentence in result['sentences'])
    fr = understand_compare(a, b, lens='JACOBIAN_LENS', scope='all', locale='fr', probability_abs_tolerance=0)
    visible = ' '.join(sentence['text'] for sentence in fr['sentences'])
    assert 'prompt tokens are aligned' not in visible
    assert 'generated tokens are aligned' not in visible
    assert 'semantic interpretation or causal proof' not in visible
    assert 'top-1 dans' in visible
    assert 'dans le contexte du prompt' in visible
    assert 'les jetons générés sont alignés uniquement par rang ordinal' in visible


def test_demo_manifest_verification_rejects_modified_file(tmp_path):
    source = ROOT / 'demo' / 'build_week_2026'
    target = tmp_path / 'demo'
    target.mkdir()
    for path in source.iterdir():
        target.joinpath(path.name).write_bytes(path.read_bytes())
    assert len(verify_demo_manifest(target)['artifacts']) == 4
    changed = target / 'demo-pair-a-control.json'
    changed.write_text(changed.read_text() + '\n')
    with pytest.raises(ValueError, match='SHA-256 mismatch|byte mismatch'):
        verify_demo_manifest(target)


def test_visualizer_static_regressions_for_demo_i18n_errors_and_sparse_chart():
    app_js = (ROOT / 'web' / 'app.js').read_text()
    html = (ROOT / 'web' / 'index.html').read_text()
    assert '/api/demo/build-week/understand/compare' in app_js
    assert 'understand-error' in html and 'rule_id' not in app_js.split('function renderUnderstandError', 1)[1].split('async function loadStoredVisualComparison', 1)[0]
    assert "coverage.complete': 'complète'" in app_js and "coverage.transmitted': 'transmis'" in app_js
    assert "Charger la démo Build Week" in app_js and "Langue" in app_js and "Résumé par règles, sans LLM" in app_js
    assert 'point.layer - previousLayer > 1' in app_js
    assert 'Intervention synthétique de démonstration' in app_js
    assert 'lab-v0.3.0-buildweek' in html
    assert 'globalLocaleSelect' in html and 'understandLocale' not in html
    assert 'const I18N' in app_js and 'function t(key' in app_js and 'prismora.locale' in app_js
    assert 'understandRequestSeq' in app_js and 'requestedLocale !== state.locale' in app_js
    assert 'Unknown error' not in app_js


def test_global_i18n_catalogue_completeness_and_navigation_glossary():
    app_js = (ROOT / 'web' / 'app.js').read_text()
    for key in ['nav.dashboard', 'nav.experiments', 'nav.registry', 'nav.campaign', 'nav.fleet', 'nav.runs', 'nav.inspector', 'nav.visualizer', 'nav.baseline', 'nav.causal', 'nav.compare', 'nav.claims']:
        assert key in app_js
    for text in ['Aperçu', 'Expériences', 'Registre des modèles', 'Créateur de campagne', 'Parc GPU / API', 'Exécutions', 'Inspecteur d’exécution', 'Visualiseur humain', 'Laboratoire de référence', 'Laboratoire causal', 'Studio de comparaison', 'Registre des affirmations']:
        assert text in app_js
    for text in ['Overview', 'Experiments', 'Model registry', 'Campaign builder', 'GPU / API fleet', 'Runs', 'Run inspector', 'Human Visualizer', 'Baseline lab', 'Causal lab', 'Comparison studio', 'Claim ledger']:
        assert text in app_js
    assert 'data-i18n="app.language"' in (ROOT / 'web' / 'index.html').read_text()


def test_empty_state_locale_switch_source_guard():
    app_js = (ROOT / 'web' / 'app.js').read_text()
    handler = app_js.split("$('globalLocaleSelect')?.addEventListener", 1)[1].split("$('visualSwapRunsBtn')", 1)[0]
    assert 'state.visualA && state.visualB' in handler
    assert 'clearUnderstandError()' in handler
    assert 'textContent' not in handler
    assert 'loadUnderstand().catch' in handler


def test_human_visualizer_i18n_inventory_and_static_bindings():
    app_js = (ROOT / 'web' / 'app.js').read_text()
    html = (ROOT / 'web' / 'index.html').read_text()
    inventory = (ROOT / 'HUMAN_VISUALIZER_I18N_INVENTORY.md').read_text()
    required_keys = [
        'shell.securityLead', 'shell.securityText', 'visual.title', 'visual.description', 'visual.badge',
        'visual.choose', 'visual.obsA', 'visual.obsB', 'visual.swap', 'visual.compareArchived',
        'visual.probeSummary', 'visual.probeHelp', 'visual.controls', 'visual.lens', 'visual.positions',
        'visual.metric', 'visual.output', 'visual.where', 'visual.selectedCell', 'visual.trajectory',
        'visual.factual', 'visual.ruleText', 'status.comparisonLoaded', 'status.probeResults',
        'error.noLens', 'visual.syntheticIntervention', 'visual.heatLegend', 'visual.caution'
    ]
    for key in required_keys:
        assert key in app_js
        assert key in inventory
    for key in ['visual.title', 'visual.description', 'visual.badge', 'visual.choose', 'visual.obsA', 'visual.obsB', 'visual.controls', 'visual.output', 'visual.where', 'visual.selectedCell', 'visual.trajectory', 'visual.factual']:
        assert f'data-i18n="{key}"' in html
    # Known old mixed-language static strings must not remain as uncontrolled Human Visualizer text.
    for old in ['Visualiseur humain</h2>', 'Comparer deux runs sans lire les JSON', 'Contrôle visuel</span>', 'Choisir ce que tu regardes', 'Réponse produite</h3>', 'Lecture factuelle</h3>']:
        assert old not in html
    # French dynamic strings may exist only inside the catalogue; runtime code must use t(...).
    assert "setStatus('visualStatus', `Comparaison" not in app_js
    assert "throw new Error('Aucune lentille" not in app_js


def test_i18n_catalogue_locale_markers_are_paired():
    app_js = (ROOT / 'web' / 'app.js').read_text()
    # A lightweight source guard: every key referenced by data-i18n in HTML appears in the central catalogue source.
    html = (ROOT / 'web' / 'index.html').read_text()
    import re
    for key in re.findall(r'data-i18n(?:-title|-aria-label)?="([^"]+)"', html):
        assert f"'{key}'" in app_js
    assert "'nav.visualizer': 'Human Visualizer'" in app_js
    assert "'nav.visualizer': 'Visualiseur humain'" in app_js
    assert "'visual.title': 'Human Visualizer'" in app_js
    assert "'visual.title': 'Visualiseur humain'" in app_js
