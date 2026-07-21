import json

import httpx
import pytest
from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.config import Settings
from prismora_lab.store import LabStore
import prismora_lab.session_security as session_security


def make_client(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        neuronpedia_api_key=None,
        worker_url=None,
        max_runs_per_request=8,
    )
    return TestClient(create_app(settings, store=LabStore(tmp_path)))


def fake_async_client(status_code=None, error=None):
    class FakeResponse:
        def __init__(self, status):
            self.status_code = status

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, path, headers=None):
            assert path == "/api/health"
            assert headers and headers.get("x-api-key")
            if error is not None:
                raise error
            return FakeResponse(status_code)

    return FakeAsyncClient


def test_saving_key_configures_but_never_connects_or_leaks(tmp_path):
    client = make_client(tmp_path)
    secret = "np_live_super_secret"

    response = client.put(
        "/api/session/settings",
        json={
            "display_name": "NicoMrx",
            "locale": "fr",
            "theme": "dark",
            "neuronpedia_api_key": secret,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["neuronpedia_key_configured"] is True
    assert body["neuronpedia_connected"] is False
    assert secret not in json.dumps(body)

    fetched = client.get("/api/session/settings").json()
    assert fetched["neuronpedia_key_configured"] is True
    assert fetched["neuronpedia_connected"] is False
    assert secret not in json.dumps(fetched)


@pytest.mark.parametrize("status", [401, 403])
def test_authentication_errors_are_never_connected(tmp_path, monkeypatch, status):
    client = make_client(tmp_path)
    secret = "np_rejected_secret"
    client.put("/api/session/settings", json={"locale": "fr", "neuronpedia_api_key": secret})
    monkeypatch.setattr(session_security.httpx, "AsyncClient", fake_async_client(status_code=status))

    response = client.post("/api/session/neuronpedia/test", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["neuronpedia_key_configured"] is True
    assert body["neuronpedia_connected"] is False
    assert body["upstream_status"] == status
    assert f"HTTP {status}" in body["message"]
    assert secret not in json.dumps(body)


def test_only_2xx_test_enables_connected_backend(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    secret = "np_verified_for_session"
    client.put("/api/session/settings", json={"neuronpedia_api_key": secret})
    monkeypatch.setattr(session_security.httpx, "AsyncClient", fake_async_client(status_code=200))

    response = client.post("/api/session/neuronpedia/test", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["neuronpedia_key_configured"] is True
    assert body["neuronpedia_connected"] is True
    assert body["upstream_status"] == 200
    assert secret not in json.dumps(body)
    assert client.app.state.lab.backends["neuronpedia"].api_key == secret


@pytest.mark.parametrize("status", [400, 404, 429, 500, 503])
def test_non_2xx_statuses_remain_disconnected(tmp_path, monkeypatch, status):
    client = make_client(tmp_path)
    client.put("/api/session/settings", json={"neuronpedia_api_key": "np_status_test"})
    monkeypatch.setattr(session_security.httpx, "AsyncClient", fake_async_client(status_code=status))

    body = client.post("/api/session/neuronpedia/test", json={}).json()
    assert body["neuronpedia_connected"] is False
    assert body["upstream_status"] == status


def test_network_failure_and_delete_keep_local_features_available(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    secret = "np_network_test"
    client.put("/api/session/settings", json={"locale": "en", "neuronpedia_api_key": secret})
    monkeypatch.setattr(
        session_security.httpx,
        "AsyncClient",
        fake_async_client(error=httpx.ConnectError("offline")),
    )

    failed = client.post("/api/session/neuronpedia/test", json={}).json()
    assert failed["neuronpedia_key_configured"] is True
    assert failed["neuronpedia_connected"] is False
    assert failed["upstream_status"] is None
    assert "imports remain available" in failed["message"]

    deleted = client.delete("/api/session/neuronpedia-key").json()
    assert deleted["neuronpedia_key_configured"] is False
    assert deleted["neuronpedia_connected"] is False
    assert secret not in json.dumps(deleted)


def test_continue_without_key_stays_available(tmp_path):
    client = make_client(tmp_path)
    body = client.post("/api/session/neuronpedia/test", json={}).json()
    assert body["neuronpedia_key_configured"] is False
    assert body["neuronpedia_connected"] is False
    assert body["upstream_status"] is None
    assert "imports remain available" in body["message"]
