import json
from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.config import Settings


ROOT = Path(__file__).resolve().parents[1]


def make_client(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        neuronpedia_api_key=None,
        worker_url=None,
        max_runs_per_request=8,
    )
    return TestClient(create_app(settings))


def test_end_to_end_mock_campaign(tmp_path):
    client = make_client(tmp_path)
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    assert client.get('/api/health').status_code == 200
    saved = client.post('/api/experiments', json=spec)
    assert saved.status_code == 200
    locked = client.post(f"/api/experiments/{spec['experiment_id']}/lock", json={})
    assert locked.status_code == 200
    plan = client.post(f"/api/experiments/{spec['experiment_id']}/plan", json={}).json()
    assert plan['summary']['run_count'] == 3
    executed = client.post('/api/runs/execute', json={"experiment_id": spec['experiment_id'], "limit": 3}).json()
    assert len(executed['completed']) == 3
    assert executed['errors'] == []
    runs = client.get('/api/runs').json()['runs']
    assert len(runs) == 3
    run_id = runs[0]['run_id']
    artifact = client.get(f'/api/runs/{run_id}').json()
    assert artifact['status'] == 'ok'
    cockpit = client.get(f'/api/runs/{run_id}/cockpit').json()
    assert cockpit['cockpit_schema_version'] == 1
    raw_response = client.get(f'/api/runs/{run_id}/raw', params={"experiment_id": spec['experiment_id']})
    assert raw_response.status_code == 200
    assert raw_response.content
    assert raw_response.headers['content-disposition'].endswith('.raw.json"')
    replay = client.post(f'/api/runs/{run_id}/make-filter-replay', json={"experiment_id": "api-filter-replay", "save": True})
    assert replay.status_code == 200
    assert replay.json()['readout']['input_token_ids']
    comparison = client.post('/api/compare', json={"run_a": runs[0]['run_id'], "run_b": runs[1]['run_id'], "lens": "JACOBIAN_LENS", "mode": "agreement"})
    assert comparison.status_code == 200
    assert comparison.json()['layers']
    bundle = client.get(f"/api/experiments/{spec['experiment_id']}/bundle")
    assert bundle.status_code == 200
    assert bundle.headers['content-type'] == 'application/zip'


def test_locked_experiment_cannot_be_silently_edited(tmp_path):
    client = make_client(tmp_path)
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    client.post('/api/experiments', json=spec)
    client.post(f"/api/experiments/{spec['experiment_id']}/lock", json={})
    locked = client.get(f"/api/experiments/{spec['experiment_id']}").json()
    locked['title'] = 'silently changed title'
    response = client.post('/api/experiments', json=locked)
    assert response.status_code == 409


def test_session_settings_never_return_neuronpedia_api_key(tmp_path):
    client = make_client(tmp_path)
    secret = "np_live_super_secret"
    response = client.put('/api/session/settings', json={"display_name": "Nico", "locale": "fr", "theme": "dark", "neuronpedia_api_key": secret})
    assert response.status_code == 200
    body = response.json()
    assert body["neuronpedia_key_configured"] is True
    assert body["neuronpedia_connected"] is False
    assert secret not in json.dumps(body)
    fetched = client.get('/api/session/settings').json()
    assert fetched["neuronpedia_key_configured"] is True
    assert fetched["neuronpedia_connected"] is False
    assert secret not in json.dumps(fetched)
    deleted = client.delete('/api/session/neuronpedia-key').json()
    assert deleted["neuronpedia_key_configured"] is False
    assert deleted["neuronpedia_connected"] is False
    assert secret not in json.dumps(deleted)


def test_neuronpedia_connection_test_allows_continue_without_key(tmp_path):
    client = make_client(tmp_path)
    response = client.post('/api/session/neuronpedia/test', json={})
    assert response.status_code == 200
    body = response.json()
    assert body["neuronpedia_connected"] is False
    assert "imports remain available" in body["message"]


def test_session_secret_not_persisted_to_artifacts_exports_or_next_process(tmp_path):
    secret = "np_test_redacted_secret"
    client = make_client(tmp_path)
    client.put('/api/session/settings', json={"neuronpedia_api_key": secret})
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    client.post('/api/experiments', json=spec)
    client.post(f"/api/experiments/{spec['experiment_id']}/lock", json={})
    executed = client.post('/api/runs/execute', json={"experiment_id": spec['experiment_id'], "limit": 1}).json()
    run_id = executed['completed'][0]['run_id']
    artifact_text = json.dumps(client.get(f'/api/runs/{run_id}').json())
    assert secret not in artifact_text
    bundle = client.get(f"/api/experiments/{spec['experiment_id']}/bundle")
    assert secret.encode() not in bundle.content
    fresh_client = make_client(tmp_path)
    fresh_settings = fresh_client.get('/api/session/settings').json()
    assert fresh_settings["neuronpedia_connected"] is False
    assert secret not in json.dumps(fresh_settings)
