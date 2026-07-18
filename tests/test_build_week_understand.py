import copy, hashlib, json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prismora_lab.analysis.compare import strict_comparison_facts
from prismora_lab.analysis.understand import understand_compare, understand_run
from prismora_lab.api.app import create_app
from prismora_lab.config import Settings
from prismora_lab.coverage import validate_coverage
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
    assert validate_coverage(new['coverage'])['source_tokens_total'] == 2
    bad = copy.deepcopy(new['coverage']); bad['transmitted_tokens'] = -1
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
    assert facts['first_strict_divergence']['layer'] == 40
    earlier = [r for r in facts['per_layer'] if r['layer'] < 40]
    assert all(r['strict_divergence_rate'] == 0 for r in earlier)
    narrative = understand_compare(a, b, lens='JACOBIAN_LENS', scope='prompt_fixed')
    assert any(s['rule_id'] == 'compare.intervention.coincides' for s in narrative['sentences'])
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
    assert response.json()['facts']['first_strict_divergence']['layer'] == 40
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
