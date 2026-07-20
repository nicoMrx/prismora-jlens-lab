from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.config import Settings
from prismora_lab.store import LabStore


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_live_chat_intercepts_fake_composer_and_restores_real_artifact():
    script = (WEB / "v4-live-chat.js").read_text(encoding="utf-8")
    assert "/api/live/models" in script
    assert "/api/live/chat" in script
    assert "document.addEventListener('submit', submitLive, true)" in script
    assert "event.stopImmediatePropagation()" in script
    assert "sourceType: 'live'" in script
    assert "max_new_tokens: 128" in script
    assert "['JACOBIAN_LENS', 'LOGIT_LENS']" in script
    assert "Neuronpedia live · raw archivé" in script
    assert "sessionStorage.setItem(SESSION_KEY" in script
    assert "location.assign(`/v4.html?live=" in script
    assert "neuronpedia_api_key" not in script
    assert "BEGIN PRIVATE KEY" not in script


def test_v4_live_chat_restores_user_prompt_and_hides_template_markers():
    script = (WEB / "v4-live-chat.js").read_text(encoding="utf-8")
    assert "function livePrompt" in script
    assert "request?.chat" in script
    assert "derived?.live_chat?.user_message" in script
    assert "function cleanCompletion" in script
    assert "<|im_end|>" in script
    assert "trimTechnicalTokenButtons" in script
    assert "buttons.slice(index).forEach((button) => button.remove())" in script
    assert "user.textContent !== prompt" in script
    assert "output.textContent !== completion" in script


def test_v4_live_chat_source_and_package_are_identical():
    assert (WEB / "v4-live-chat.js").read_text(encoding="utf-8") == (
        PKG / "v4-live-chat.js"
    ).read_text(encoding="utf-8")


def test_v4_route_injects_live_chat_after_connection_semantics_and_before_campaign(tmp_path):
    client = TestClient(
        create_app(
            Settings(data_dir=tmp_path, neuronpedia_api_key=None, worker_url=None),
            store=LabStore(tmp_path),
        )
    )
    response = client.get("/v4.html?v=live")
    assert response.status_code == 200
    html = response.text
    connection = '/v4-connection-semantics.js?v=1'
    live = '/v4-live-chat.js?v=1'
    campaign = '/v4-campaign-center.js?v=2'
    assert connection in html and live in html and campaign in html
    assert html.index(connection) < html.index(live) < html.index(campaign)
    assert "no-store" in response.headers.get("cache-control", "")
