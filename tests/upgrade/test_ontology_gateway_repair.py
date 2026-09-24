"""Offline tests for an explicitly authorized gateway diagnostic, no live calls."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import httpx
import pytest

from tests.upgrade.test_ontology_model_recovery import authorization, latched
from zhigou_toolchain.ontology_io import gateway_repair
from zhigou_toolchain.ontology_io.gateway_repair import (
    MODEL_RULE,
    active_auth_files,
    native_only_route,
    public_response,
    variant_config,
)


def test_variant_limits_only_private_diagnostic_and_preserves_credentials(tmp_path):
    config = {"host": "127.0.0.1", "port": 51900, "api-keys": ["SYNTHETIC"], "auth-dir": "original",
        "codex": {"safe-setting": True}, "routing": {"strategy": "existing"}, "request-retry": 1}
    original = copy.deepcopy(config)
    result = variant_config(config, tmp_path / "auths")
    assert config == original
    assert result["payload"] == {"override": [MODEL_RULE]}
    assert result["port"] == 0 and result["host"] == "127.0.0.1"
    assert result["request-retry"] == 0 and result["max-retry-credentials"] == 1
    assert not result["request-log"] and not result["debug"] and not result["logging-to-file"]
    assert result["disable-auth-auto-refresh"] and result["disable-image-generation"] is True
    assert result["api-keys"] == config["api-keys"] and result["routing"] == config["routing"]


@pytest.mark.parametrize("config", [{"host": "0.0.0.0"}, {"host": "127.0.0.1", "payload": {"override": [{"unreviewed": True}]}}])
def test_unreviewed_config_never_silently_overwritten(tmp_path, config):
    with pytest.raises(ValueError):
        variant_config(config, tmp_path)


def test_native_routing_allows_no_new_provider_or_fallback():
    native = {"defaultRoute": "oauth", "failurePolicy": "strict", "routes": [], "nativeModels": ["gpt-5.6-luna"]}
    assert native_only_route({})
    assert native_only_route({"modelRouting": native})
    assert not native_only_route({"providerGateway": {"endpoint": "other"}})
    for update in ({"defaultRoute": "other"}, {"failurePolicy": "fallback"}, {"routes": [{"id": "another-provider"}]}, {"nativeModels": []}):
        assert not native_only_route({"modelRouting": {**native, **update}})


def test_active_auth_inventory_matches_upstream_not_old_backups(tmp_path):
    (tmp_path / "active.json").write_text("SYNTHETIC")
    (tmp_path / "historical.json.bak").write_text("OLD_SYNTHETIC")
    assert [p.name for p in active_auth_files(tmp_path)] == ["active.json"]
    (tmp_path / "unexpected-directory").mkdir()
    with pytest.raises(ValueError, match="UNEXPECTED"):
        active_auth_files(tmp_path)


def test_upstream_rejection_captured_without_raw_private_error_or_reasoning():
    raw = json.dumps({"error": {"message": "Unsupported parameter: max_output_tokens. Secret diagnostic: token-FAKE"},
        "reasoning": "PRIVATE_DO_NOT_CAPTURE", "authorization": "Bearer FAKE"}).encode()
    result = public_response(400, raw)
    assert result["unsupported_max_output_tokens"]
    assert result["error_message"] == "Unsupported parameter: max_output_tokens"
    assert result["response_sha256"] == hashlib.sha256(raw).hexdigest()
    assert not any(s in json.dumps(result) for s in ("PRIVATE_DO_NOT_CAPTURE", "FAKE", "authorization"))
    assert result["public_response"]["usage"] == {}


def test_limit_truncation_and_usage_preserved_without_reasoning():
    raw = json.dumps({"model": "gpt-5.6-luna", "choices": [{"finish_reason": "length", "message": {
        "content": '{"numbers":[1,2', "reasoning_content": "PRIVATE"}}], "usage": {
        "prompt_tokens": 30, "completion_tokens": 128, "total_tokens": 158}}).encode()
    result = public_response(200, raw)
    assert result["public_response"]["choices"][0]["finish_reason"] == "length"
    assert result["public_response"]["usage"]["total_tokens"] == 158
    assert "PRIVATE" not in json.dumps(result) and not result["unsupported_max_output_tokens"]


@pytest.mark.parametrize("raw", [b"[]", b"null", b"not-json", b'{"usage":null,"choices":{}}',
    b'{"choices":[null,2,{"message":[]}]}' ])
def test_malformed_responses_are_not_success_or_zero_usage(raw):
    result = public_response(502, raw)
    assert result["public_response"]["usage"] == {}
    assert result["public_response"]["model"] is None


def test_invalid_usage_marked_and_no_secret_text_copied():
    raw = json.dumps({"choices": [{"message": {"content": "sk-NOT-A-SYNTHETIC-ARRAY"}}],
        "usage": {"total_tokens": -5, "completion_tokens": True}}).encode()
    result = public_response(200, raw)
    assert result["public_response"]["choices"][0]["content"] is None
    assert set(result["public_response"]["invalid_usage_fields"]) == {"total_tokens", "completion_tokens"}


def test_same_gateway_patch_cannot_retry_via_different_local_port(tmp_path):
    ledger = latched(tmp_path, max_calls=5, max_tokens=800000)
    auth = {**authorization(), "gateway_change_sha256": "b" * 64}
    ledger.reserve_recovery_probe("probe-first", 131000, authorization=auth)
    ledger.finish("probe-first", status="FAILED", usage=None, result_hash="failed-upstream")
    before = ledger.snapshot()
    with pytest.raises(sqlite3.IntegrityError):
        ledger.reserve_recovery_probe("probe-second", 131000, authorization={**auth, "endpoint_sha256": "c" * 64})
    assert before == ledger.snapshot()
    with pytest.raises(ValueError, match="LATCHED"):
        ledger.reserve("full", "e2e", 1)


def test_bad_gateway_change_digest_refused_before_reservation(tmp_path):
    ledger = latched(tmp_path)
    with pytest.raises(ValueError, match="DIGEST"):
        ledger.reserve_recovery_probe("bad", 131000, authorization={**authorization(), "gateway_change_sha256": "not-a-digest"})
    assert ledger.snapshot()["calls"] == 1


@pytest.mark.parametrize("counts", [None, {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50}])
def test_forwarded_rejection_is_charged_once_retains_usage_and_stop(tmp_path, monkeypatch, counts):
    ledger = latched(tmp_path, max_tokens=500000)
    (tmp_path / "STOP").write_bytes(b"historical-stop")
    with ledger.connection() as conn:
        previous = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY request_id")]
    observations = []

    def handler(request):
        observations.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "gpt-5.6-luna"}]})
        assert ledger.snapshot()["calls"] == 2
        assert json.loads(request.content)["max_completion_tokens"] == 128
        return httpx.Response(400, json={"error": {"message": "Unsupported parameter: max_output_tokens"}, "usage": counts})

    real_client = httpx.Client
    monkeypatch.setattr(gateway_repair.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(gateway_repair, "input_digests", lambda *args: {"0": "unchanged"})
    output = tmp_path / "out"
    output.mkdir()
    result = gateway_repair.execute_probe(tmp_path, output, tmp_path / "private", SimpleNamespace(pid=12345), 50001, {},
        "SYNTHETIC_KEY_DO_NOT_EXPORT", ledger, previous, ledger.snapshot(), {"0": "unchanged"},
        hashlib.sha256(b"historical-stop").hexdigest(), tmp_path / "app", tmp_path / "exe", "SYNTHETIC_USER_AUTHORIZATION")
    assert observations == [("GET", "/v1/models"), ("POST", "/v1/chat/completions")]
    assert result["status"] == "BLOCKED_UPSTREAM_REJECTS_MAX_OUTPUT_TOKENS"
    assert result["usage"] == (counts["total_tokens"] if counts else None)
    assert result["budget_after"]["known_tokens_are_partial"] == (counts is None)
    assert result["historical_attempts_unchanged"] and result["stop_unchanged"] and result["installed_files_unchanged"]
    assert not result["full_e2e_resumed"] and result["budget_after"]["provider_limit_latched"]
    assert "SYNTHETIC_KEY_DO_NOT_EXPORT" not in "".join(p.read_text(encoding="utf-8") for p in output.glob("*.json"))


def test_private_sidecar_is_stopped_even_when_probe_raises(tmp_path, monkeypatch):
    ledger = latched(tmp_path)
    (tmp_path / "STOP").write_bytes(b"historical-stop")
    app = tmp_path / "app"
    app.mkdir()
    (app / "auths").mkdir()
    (app / "auths/account.json").write_text('{"token":"SYNTHETIC_TOKEN"}')
    config = {"host": "127.0.0.1", "api-keys": ["SYNTHETIC"], "auth-dir": str(app / "auths")}
    manifest = {"apiKeys": [{"key": "SYNTHETIC", "enabled": True}], "accounts": [{"authKind": "oauth"}]}
    for name, value in (("config.json", config), ("manifest.json", manifest), ("quota-reserve.json", {}), ("quota-pool-state.json", {})):
        (app / name).write_text(json.dumps(value))
    binary = tmp_path / "binary.exe"
    binary.write_bytes(b"SYNTHETIC_NOT_EXECUTABLE")
    old = gateway_repair.input_digests(app, binary)
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC")
    monkeypatch.setattr(gateway_repair, "secure_directory", lambda path: path.mkdir())

    class Process:
        pid = 333
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, **kwargs):
            return self.returncode

    process = Process()
    monkeypatch.setattr(gateway_repair, "launch", lambda *args: (process, 50001, {}))

    def fail(*args):
        raise ValueError("SYNTHETIC_DIAGNOSTIC_FAILURE")

    monkeypatch.setattr(gateway_repair, "execute_probe", fail)
    with pytest.raises(ValueError, match="SYNTHETIC_DIAGNOSTIC_FAILURE"):
        gateway_repair._run(tmp_path, tmp_path / "out", app, tmp_path / "private", binary, "SYNTHETIC_REQUEST")
    cleanup = json.loads((tmp_path / "out/cleanup.json").read_bytes())
    assert cleanup["temporary_process_stopped"] and cleanup["installed_files_unchanged"]
    assert process.poll() == 0 and gateway_repair.input_digests(app, binary) == old
    assert ledger.snapshot()["calls"] == 1
