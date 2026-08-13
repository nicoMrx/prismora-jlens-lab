import asyncio
import importlib

import httpx
import pytest
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


@pytest.mark.asyncio
async def test_worker_serializes_concurrent_runtime_calls(monkeypatch):
    worker_app = importlib.import_module("prismora_worker.app")

    class TrackingRuntime:
        runtime_id = "tracking"
        is_mock = False

        def __init__(self):
            self.active = 0
            self.max_active = 0

        async def run(self, request):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.03)
            self.active -= 1
            return {"meta": {}, "tokens": [], "done": {}}

        async def capabilities(self):
            return {}

    runtime = TrackingRuntime()
    monkeypatch.setattr(worker_app, "RUNTIME", runtime)
    transport = httpx.ASGITransport(app=worker_app.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://worker.test") as client:
        responses = await asyncio.gather(
            client.post("/v1/run", json={"request": {"model": {"model_id": "one"}}}),
            client.post("/v1/run", json={"request": {"model": {"model_id": "two"}}}),
        )
    assert [response.status_code for response in responses] == [200, 200]
    assert runtime.max_active == 1
