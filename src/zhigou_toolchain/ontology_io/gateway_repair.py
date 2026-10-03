"""Test Cockpit's supported payload override in a private, temporary sidecar.

No installed binary/config overwrite, raw secret export, new provider, automatic
retry or experiment unlock. Credentials stay in an ACL-restricted app directory.
The independent sidecar is always stopped, including when the probe fails.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import threading
from pathlib import Path
from time import monotonic

import httpx

from zhigou_toolchain.contracts.canonical import semantic_hash

from .cli import load, save
from .live_budget import BudgetLedger
from .live_runner import supervisor_lock
from .model_recovery import OUTPUT_CEILING, TARGET_MODEL, evaluate_probe, probe_request

INSTALLED_SHA256 = "5ab1b1c51c24777ca54f8ef2501bade0287e3bd10d85e635c876779897aba0ce"
SOURCE_COMMIT = "3a83b85a18f9f62ff2f4b34679796229072b4129"
MODEL_RULE = {"models": [{"name": TARGET_MODEL, "protocol": "codex"}], "params": {"max_output_tokens": 128}}
CHANGE = {"kind": "COCKPIT_PAYLOAD_OVERRIDE_AFTER_TRANSLATION", "source_commit": SOURCE_COMMIT,
    "installed_sha256": INSTALLED_SHA256, "override": MODEL_RULE, "upstream_credentials": "SAME_AUTHORIZED_POOL",
    "request_retry": 0, "max_retry_credentials": 1, "image_generation": "DISABLED", "limits_unlocked": False}


def variant_config(config, auth_dir):
    value = copy.deepcopy(config)
    if config.get("host") != "127.0.0.1":
        raise ValueError("ONLY_EXISTING_LOOPBACK_GATEWAY_SUPPORTED")
    value.update({"host": "127.0.0.1", "port": 0, "auth-dir": str(auth_dir), "request-retry": 0,
        "max-retry-credentials": 1, "max-retry-interval": 0, "debug": False, "request-log": False,
        "logging-to-file": False, "disable-auth-auto-refresh": True, "disable-image-generation": True})
    # All original model routing and limits remain. Refuse an overlapping rule
    # rather than quietly change unrelated payload behavior.
    if config.get("payload"):
        raise ValueError("EXISTING_PAYLOAD_RULES_REQUIRE_SEPARATE_REVIEW")
    value["payload"] = {"override": [copy.deepcopy(MODEL_RULE)]}
    return value


def native_only_route(entry):
    if entry.get("providerGateway"):
        return False
    routing = entry.get("modelRouting")
    if not routing:
        return True
    return (isinstance(routing, dict) and routing.get("defaultRoute") == "oauth"
        and routing.get("failurePolicy") == "strict" and not routing.get("routes")
        and TARGET_MODEL in routing.get("nativeModels", []))


def public_response(status, raw):
    """Keep only allowlisted diagnostics; never log headers or error prose."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    text = raw.decode("utf-8", errors="replace")
    unsupported = bool(re.search(r"(?i)(unsupported\s+parameter|unknown\s+parameter|not\s+supported)[^\r\n]{0,80}max_output_tokens", text)
        or re.search(r"(?i)max_output_tokens[^\r\n]{0,80}(?:not\s+supported|unsupported)", text))
    usage = data.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    counts = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens") if type(usage.get(k)) is int and usage[k] >= 0}
    invalid = [k for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage and k not in counts]
    choices = data.get("choices")
    choices = choices if isinstance(choices, list) else []
    safe_choices = []
    for row in choices:
        if not isinstance(row, dict):
            continue
        message = row.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        # This one synthetic response has no need for arbitrary text/reasoning.
        allowed = isinstance(content, str) and len(content) <= 20000 and re.fullmatch(r'[\s\d,\[\]{}:"a-z]*', content) is not None
        safe_choices.append({"finish_reason": row.get("finish_reason") if row.get("finish_reason") in {"stop", "length", "content_filter"} else None,
            "content": content if allowed else None, "content_capture": "SYNTHETIC_WHITELIST" if allowed else "OMITTED"})
    return {"http_status": status, "response_sha256": hashlib.sha256(raw).hexdigest(), "response_size": len(raw),
        "unsupported_max_output_tokens": unsupported,
        "public_response": {"model": TARGET_MODEL if data.get("model") == TARGET_MODEL else None,
            "usage": counts, "invalid_usage_fields": invalid, "choices": safe_choices},
        "error_message": "Unsupported parameter: max_output_tokens" if unsupported else None,
        "capture_policy": "ALLOWLISTED_PUBLIC_DIAGNOSTIC_NOT_FULL_RAW_RESPONSE"}


def secure_directory(path):
    if os.name != "nt":
        raise ValueError("WINDOWS_COCKPIT_DIAGNOSTIC_ONLY")
    path.mkdir(parents=True, exist_ok=False)
    account = os.environ["USERDOMAIN"] + "\\" + os.environ["USERNAME"]
    check = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", account + ":(OI)(CI)F", "SYSTEM:(OI)(CI)F"],
        capture_output=True, check=False, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    if check.returncode:
        raise ValueError("PRIVATE_DIAGNOSTIC_ACL_FAILED")


def input_digests(app_dir, binary):
    paths = [binary, app_dir / "config.json", app_dir / "manifest.json", app_dir / "quota-reserve.json", app_dir / "quota-pool-state.json"]
    paths.extend(sorted((app_dir / "auths").glob("*.json")))
    if any(p.is_symlink() for p in paths):
        raise ValueError("GATEWAY_SOURCE_LINK_REFUSED")
    # Account filenames are private; expose only ordered digests.
    return {str(index): hashlib.sha256(p.read_bytes()).hexdigest() for index, p in enumerate(paths) if p.is_file()}


def active_auth_files(directory):
    # Match Cockpit sdk/auth/filestore.go: historical .bak files are not active
    # credentials and must not be copied into a new live credential inventory.
    members = list(Path(directory).iterdir())
    if any(p.is_symlink() or not p.is_file() for p in members):
        raise ValueError("AUTH_DIRECTORY_UNEXPECTED_MEMBERS")
    return [p for p in members if p.suffix.lower() == ".json"]


def startup_redactor(private):
    values = set()

    def collect(value):
        if isinstance(value, str) and len(value) >= 4:
            values.add(value)
        elif isinstance(value, dict):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for path in (private / "config.json", private / "manifest.json", *active_auth_files(private / "auths")):
        collect(load(path))

    def redact(message):
        text = str(message)
        for value in sorted(values, key=len, reverse=True):
            text = text.replace(value, "[REDACTED]")
        text = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+|Bearer\s+\S+", "[REDACTED]", text)
        return text[:1500]

    return redact


def launch(binary, private):
    redact = startup_redactor(private)
    process = subprocess.Popen([str(binary), "--config", str(private / "config.json"), "--manifest", str(private / "manifest.json"),
        "--quota-reserve-state", str(private / "quota-reserve.json"), "--quota-pool-state", str(private / "quota-pool-state.json"),
        "--parent-pid", str(os.getpid())], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW)
    events = queue.Queue()
    observations = {"stdout_lines": 0, "stderr_lines": 0, "error_events": 0}

    def consume(stream, label):
        assert stream is not None
        for line in iter(stream.readline, ""):
            observations[label + "_lines"] += 1
            if label != "stdout" or len(line) > 100000:
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "ready" and item.get("host") == "127.0.0.1" and type(item.get("port")) is int:
                events.put(("ready", item["port"]))
            if item.get("type") == "error":
                observations["error_events"] += 1
                events.put(("error", redact(item.get("message", "UNSPECIFIED_STARTUP_ERROR"))))

    for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
        threading.Thread(target=consume, args=(stream, label), daemon=True).start()
    try:
        state, port = events.get(timeout=30)
    except queue.Empty:
        process.terminate()
        process.wait(timeout=10)
        raise ValueError("DIAGNOSTIC_GATEWAY_NOT_READY") from None
    if state == "error":
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        save(private / "startup-error-redacted.json", {"message": port, "exit_code": process.returncode})
        raise ValueError("DIAGNOSTIC_GATEWAY_STARTUP_ERROR:" + str(port))
    if not 1024 <= port <= 65535:
        process.terminate()
        process.wait(timeout=10)
        raise ValueError("DIAGNOSTIC_GATEWAY_PORT_INVALID")
    return process, port, observations


def run(workspace, output, app_dir, private, binary, *, user_request):
    workspace, output, app_dir, private, binary = [Path(p).resolve() for p in (workspace, output, app_dir, private, binary)]
    if not user_request or output.exists() or private.exists() or private.parent != app_dir.parent or private == app_dir:
        raise ValueError("NEW_OUTPUT_AND_PRIVATE_APP_SIBLING_REQUIRED")
    if hashlib.sha256(binary.read_bytes()).hexdigest() != INSTALLED_SHA256:
        raise ValueError("GATEWAY_BINARY_CHANGED_REAUDIT_REQUIRED")
    if not (workspace / "budget.sqlite").is_file():
        raise ValueError("EXISTING_BUDGET_REQUIRED")
    with supervisor_lock(workspace):
        return _run(workspace, output, app_dir, private, binary, user_request)


def _run(workspace, output, app_dir, private, binary, user_request):
    config, manifest = load(app_dir / "config.json"), load(app_dir / "manifest.json")
    key = os.environ.get("OPENAI_API_KEY")
    if not key or key not in config.get("api-keys", []):
        raise ValueError("CONFIGURED_GATEWAY_CREDENTIAL_NOT_BOUND")
    matches = [row for row in manifest["apiKeys"] if row.get("key") == key and row.get("enabled")]
    if len(matches) != 1 or not native_only_route(matches[0]):
        raise ValueError("UNREVIEWED_PROVIDER_ROUTE")
    if any(row.get("authKind") != "oauth" or row.get("upstreamApiKey") for row in manifest["accounts"]):
        raise ValueError("ONLY_EXISTING_OAUTH_POOL_DIAGNOSTIC_REVIEWED")
    if Path(config["auth-dir"]).resolve() != (app_dir / "auths").resolve():
        raise ValueError("UNEXPECTED_AUTH_DIRECTORY")
    patched = variant_config(config, private / "auths")
    before = input_digests(app_dir, binary)
    ledger = BudgetLedger(workspace / "budget.sqlite")
    budget_before = ledger.snapshot()
    stop_digest = hashlib.sha256((workspace / "STOP").read_bytes()).hexdigest()
    with ledger.connection() as conn:
        old_attempts = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY request_id")]
    secure_directory(private)
    (private / "backup").mkdir()
    for name in ("config.json", "manifest.json", "quota-reserve.json", "quota-pool-state.json"):
        shutil.copy2(app_dir / name, private / "backup" / name)
        if name.startswith("quota"):
            shutil.copy2(app_dir / name, private / name)
    auth_files = active_auth_files(app_dir / "auths")
    (private / "auths").mkdir()
    for member in auth_files:
        shutil.copy2(member, private / "auths" / member.name)
    save(private / "config.json", patched)
    variant_manifest = copy.deepcopy(manifest)
    variant_manifest.update(maxAccountConcurrency=1, immediateSseResponse=False, debugLogs=False)
    save(private / "manifest.json", variant_manifest)
    if before != input_digests(app_dir, binary):
        raise ValueError("SOURCE_CONFIG_CHANGED_DURING_BACKUP")
    output.mkdir(parents=True, exist_ok=False)
    save(output / "change-plan.json", {**CHANGE, "user_request": user_request, "private_directory": str(private),
        "original_inputs_sha256": before, "private_config_sha256": hashlib.sha256((private / "config.json").read_bytes()).hexdigest(),
        "installed_files_overwritten": False, "raw_credentials_exported": False})
    try:
        process, port, observations = launch(binary, private)
    except ValueError:
        save(output / "cleanup.json", {"temporary_process_stopped": True, "failure_stage": "GATEWAY_STARTUP",
            "installed_files_unchanged": before == input_digests(app_dir, binary), "private_backup_retained": str(private),
            "live_service_restarted": False, "model_requests": 0})
        raise
    try:
        return execute_probe(workspace, output, private, process, port, observations, key, ledger,
            old_attempts, budget_before, before, stop_digest, app_dir, binary, user_request)
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        save(output / "cleanup.json", {"temporary_process_stopped": process.poll() is not None,
            "installed_files_unchanged": before == input_digests(app_dir, binary), "private_backup_retained": str(private),
            "live_service_restarted": False, "temporary_pid": process.pid})


def execute_probe(workspace, output, private, process, port, observations, key, ledger, old_attempts, budget_before,
                  before, stop_digest, app_dir, binary, user_request):
    endpoint = f"http://127.0.0.1:{port}/v1/"
    request = probe_request()
    payload = {"model": TARGET_MODEL, "messages": [{"role": "system", "content": request["instruction"]},
        {"role": "user", "content": json.dumps(request["content"])}], "max_completion_tokens": 128,
        "reasoning_effort": "low", "response_format": {"type": "json_object"}, "n": 1, "stream": False, "store": False}
    reservation = OUTPUT_CEILING + len(json.dumps(payload).encode()) + 2048
    change_digest = semantic_hash(CHANGE)
    request_id = "gateway-forwarding-probe:" + change_digest[:24]
    auth = {"user_request": user_request, "model_id": TARGET_MODEL, "endpoint_sha256": semantic_hash(endpoint),
        "request_sha256": semantic_hash(payload), "prior_violation_ids": sorted(r["request_id"] for r in old_attempts if r["state"] == "USAGE_BOUND_VIOLATION"),
        "max_calls": 1, "documented_output_ceiling": OUTPUT_CEILING, "purpose": "SYNTHETIC_LIMIT_DIAGNOSTIC_NOT_RESUME", "gateway_change_sha256": change_digest}
    with httpx.Client(base_url=endpoint, timeout=120, trust_env=False, follow_redirects=False,
            headers={"Authorization": "Bearer " + key}) as client:
        health = client.get("models")
        health.raise_for_status()
        if not any(row.get("id") == TARGET_MODEL for row in health.json().get("data", [])):
            raise ValueError("DIAGNOSTIC_LUNA_NOT_LISTED")
        save(output / "request.json", payload)
        save(output / "authorization.json", auth)
        ledger.reserve_recovery_probe(request_id, reservation, authorization=auth)
        started = monotonic()
        try:
            response = client.post("chat/completions", json=payload)
            safe = public_response(response.status_code, response.content)
        except httpx.HTTPError as exc:
            safe = {"http_status": None, "transport_error_type": type(exc).__name__, "public_response": {}, "unsupported_max_output_tokens": False}
        elapsed = monotonic() - started
    save(output / "response-public.json", safe)
    result = evaluate_probe(safe, requested_limit=128, reserved_tokens=reservation)
    if safe["unsupported_max_output_tokens"]:
        result["status"] = "BLOCKED_UPSTREAM_REJECTS_MAX_OUTPUT_TOKENS"
        if result["budget_state"] != "USAGE_BOUND_VIOLATION":
            result["budget_state"] = "FAILED"
    try:
        ledger.finish(request_id, status=result["budget_state"], usage=result["usage"], result_hash=semantic_hash(safe))
    except ValueError as exc:
        if str(exc) != "PROVIDER_EXCEEDED_RESERVED_TOKEN_BOUND":
            raise
    with ledger.connection() as conn:
        retained = [dict(r) for r in conn.execute("SELECT * FROM attempts WHERE request_id!=? ORDER BY request_id", (request_id,))]
    result.update(http_status=safe["http_status"], request_id=request_id, duration_seconds=elapsed, budget_before=budget_before,
        budget_after=ledger.snapshot(), historical_attempts_unchanged=old_attempts == retained,
        stop_unchanged=stop_digest == hashlib.sha256((workspace / "STOP").read_bytes()).hexdigest(),
        installed_files_unchanged=before == input_digests(app_dir, binary), configuration_change=CHANGE,
        temporary_process_pid=process.pid, gateway_event_counts=dict(observations), full_e2e_resumed=False,
        caller_requests=1, physical_upstream_attempts="NOT_INDEPENDENTLY_OBSERVED_RETRIES_DISABLED", private_artifacts=str(private))
    save(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workspace", "output", "app-dir", "private-dir", "binary", "authorization"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--execute-authorized-probe", action="store_true", required=True)
    args = parser.parse_args()
    result = run(args.workspace, args.output, args.app_dir, args.private_dir, args.binary,
        user_request=load(args.authorization)["user_request"])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
