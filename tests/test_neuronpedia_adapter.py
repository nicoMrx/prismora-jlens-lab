import httpx
import pytest

from prismora_lab.backends.neuronpedia import NeuronpediaBackend


REQUEST = {
    "backend": "neuronpedia",
    "model": {"alias": "M01", "model_id": "qwen3.6-27b"},
    "prompt_id": "p1",
    "chat": [{"role": "user", "content": "Hello"}],
    "factors": {},
    "repeat": 1,
    "generation": {"temperature": 0, "max_new_tokens": 32, "prepend_bos": True, "enable_thinking": False},
    "readout": {"types": ["LOGIT_LENS", "JACOBIAN_LENS"], "top_k": 8, "filter_nonword_tokens": True},
    "intervention": None,
}


def test_payload_matches_documented_buffered_api_shape():
    payload = NeuronpediaBackend.build_payload(REQUEST)
    assert payload == {
        "modelId": "qwen3.6-27b",
        "type": ["LOGIT_LENS", "JACOBIAN_LENS"],
        "topN": 8,
        "temperature": 0,
        "numCompletionTokens": 32,
        "prependBos": True,
        "enableThinking": False,
        "filterNonWordTokens": True,
        "stream": False,
        "chat": [{"role": "user", "content": "Hello"}],
    }


def test_swap_payload():
    request = dict(REQUEST)
    request["intervention"] = {
        "mode": "swap",
        "source_tokens": [{"token": " formula", "type": "JACOBIAN_LENS"}],
        "target_token": {"token": " factor", "type": "JACOBIAN_LENS"},
        "layers": [30, 31],
        "strength": 1.0,
        "apply_to_generated_tokens": True,
    }
    payload = NeuronpediaBackend.build_payload(request)
    assert payload["steerTokens"][0]["token"] == " formula"
    assert payload["swapToken"]["token"] == " factor"
    assert payload["steerLayers"] == [30, 31]
    assert payload["steerGeneratedTokens"] is True


@pytest.mark.asyncio
async def test_backend_parses_buffered_response_and_sends_api_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("x-api-key")
        seen["path"] = request.url.path
        return httpx.Response(200, json={"meta": {}, "tokens": [], "done": {}})

    backend = NeuronpediaBackend(api_key="secret", base_url="https://example.test", transport=httpx.MockTransport(handler))
    result = await backend.run(REQUEST)
    assert result.value == {"meta": {}, "tokens": [], "done": {}}
    assert result.raw_bytes == b'{"meta":{},"tokens":[],"done":{}}'
    assert seen == {"key": "secret", "path": "/api/lens/prompt"}
