"""No-network request-shape tests for explicit reasoning and image inputs."""
import base64
import json

import httpx
import pytest

from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import ModelLock, ToolBlocked

LOCK = ModelLock("gpt-6-astra", "configured-alias:gpt-6-astra", "http://localhost:51900/v1")
SCHEMA = {"type": "object", "required": ["ok"], "additionalProperties": False, "properties": {"ok": {"type": "boolean"}}}


def test_xhigh_is_sent_and_attested_only_as_strongly_as_the_provider_echo():
    def handle(request):
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-6-astra" and payload["reasoning_effort"] == "xhigh"
        assert payload["max_completion_tokens"] == 8192 and "max_tokens" not in payload
        return httpx.Response(200, json={"id": "fixture", "model": "gpt-6-astra", "choices": [
            {"finish_reason": "stop", "message": {"content": '{"ok":true}', "reasoning_content": "HIDDEN_DO_NOT_RETAIN"}}]})
    client = CompatibleClient(LOCK, api_key="fixture-secret", reasoning_effort="xhigh", timeout_seconds=180, transport=httpx.MockTransport(handle))
    try:
        result = client.propose("Return JSON", {}, SCHEMA)
    finally:
        client.close()
    assert result["model"]["reasoning_attestation"] == "REQUEST_ONLY_NOT_ECHOED"
    assert result["model"]["requested_reasoning_effort"] == "xhigh"
    assert "fixture-secret" not in json.dumps(result) and "HIDDEN_DO_NOT_RETAIN" not in json.dumps(result)


@pytest.mark.parametrize("effort", ["none", "invalid"])
def test_astra_invalid_reasoning_configuration_rejected(effort):
    with pytest.raises(ToolBlocked, match="REASONING_EFFORT_INVALID"):
        CompatibleClient(LOCK, reasoning_effort=effort)


def test_inline_png_is_sent_as_multimodal_content_not_as_a_json_string():
    url = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
    def handle(request):
        content = json.loads(request.content)["messages"][1]["content"]
        assert content[0]["type"] == "text" and content[1] == {"type": "image_url", "image_url": {"url": url}}
        return httpx.Response(200, json={"model": "gpt-6-astra", "reasoning_effort": "xhigh", "choices": [
            {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]})
    client = CompatibleClient(LOCK, reasoning_effort="xhigh", transport=httpx.MockTransport(handle))
    try:
        result = client.propose("Read image", {}, SCHEMA, image_data_urls=[url])
        assert result["model"]["reasoning_attestation"] == "RESPONSE_ECHO"
    finally:
        client.close()


@pytest.mark.parametrize("url", ["https://example.invalid/image.png", "file:///private.png", "data:image/png;base64,not-valid"])
def test_image_inputs_never_fetch_arbitrary_urls(url):
    client = CompatibleClient(LOCK, transport=httpx.MockTransport(lambda _: pytest.fail("must reject before network")))
    try:
        with pytest.raises(ToolBlocked, match="MODEL_IMAGE_INPUT_INVALID"):
            client.propose("Read image", {}, SCHEMA, image_data_urls=[url])
    finally:
        client.close()
