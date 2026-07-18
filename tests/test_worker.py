from fastapi.testclient import TestClient

from prismora_worker.app import app


def test_worker_contract_mock():
    client = TestClient(app)
    caps = client.get('/v1/capabilities').json()
    assert caps['backend_id'] == 'worker'
    request = {
        "backend": "worker",
        "model": {"alias": "W01", "model_id": "mock/12-layer-lab-model"},
        "prompt_id": "p1",
        "prompt": "Explain photosynthesis.",
        "factors": {},
        "repeat": 1,
        "generation": {"temperature": 0, "max_new_tokens": 8},
        "readout": {"types": ["JACOBIAN_LENS"], "top_k": 4, "filter_nonword_tokens": True},
        "intervention": None,
    }
    response = client.post('/v1/run', json={"request": request})
    assert response.status_code == 200
    raw = response.json()
    assert set(raw) >= {"meta", "tokens", "done"}
    assert raw['meta']['worker_runtime'] == 'mock'
