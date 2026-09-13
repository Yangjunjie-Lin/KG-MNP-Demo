"""At most four real gpt-6-astra/xhigh requests with synthetic inputs only.

Credentials come from a hidden prompt or explicit process environment, never
arguments or files. This is an engineering smoke test, not a benchmark score.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hmac
import json
import os
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import ModelLock, ToolBlocked
from zhigou_toolchain.ontology_io.adapters import native_exact_key
from zhigou_toolchain.ontology_io.contracts import Budget, ModelingInput, Protocol
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.provenance import runtime_versions, source_identity

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "http://localhost:51900/v1"
MODEL = "gpt-6-astra"
EFFORT = "xhigh"


class BoundedClient(CompatibleClient):
    def __init__(self, api_key):
        super().__init__(ModelLock(MODEL, "configured-alias:" + MODEL, ENDPOINT), api_key=api_key,
            reasoning_effort=EFFORT, response_format="json_object", timeout_seconds=180)
        self.attempts = 0
        self._credential_guard = api_key

    def _request(self, *args, **kwargs):
        response = super()._request(*args, **kwargs)
        if self._credential_guard in json.dumps(response, ensure_ascii=False):
            self.last_public_response = None
            raise ToolBlocked("CREDENTIAL_ECHO_REJECTED")
        return response

    def propose(self, *args, **kwargs):
        if self.attempts >= 4:
            raise ToolBlocked("SMOKE_CALL_LIMIT")
        self.attempts += 1
        print(json.dumps({"event": "REQUEST_STARTED", "request": self.attempts, "model": MODEL, "reasoning_effort": EFFORT}), flush=True)
        return super().propose(*args, **kwargs)


def synthetic_image(colours):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (300, 100), "white")
    drawing = ImageDraw.Draw(image)
    for index, colour in enumerate(colours):
        drawing.rectangle((20 + 95 * index, 20, 80 + 95 * index, 80), fill=colour)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-source", choices=["prompt", "environment"], default="prompt")
    args = parser.parse_args()
    # Import and prepare deterministic fixtures before spending any requests.
    images = [synthetic_image(order) for order in (["blue", "green", "red"], ["green", "red", "blue"])]
    if args.credential_source == "prompt":
        if not sys.stdin.isatty():
            raise ValueError("HIDDEN_CREDENTIAL_PROMPT_REQUIRES_TTY")
        api_key = getpass.getpass("Local gateway API key (hidden): ")
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("API_KEY_REQUIRED")
    output = ROOT / "runtime_reports" / ("astra-xhigh-smoke-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    identity = source_identity(ROOT)
    report = {"report_kind": "LIVE_SYNTHETIC_ENGINEERING_SMOKE", "status": "RUNNING", "model": MODEL, "reasoning_effort": EFFORT,
        "started_at": datetime.now(UTC).isoformat(), "max_model_requests": 4, "max_completion_tokens_per_request": 8192,
        "endpoint": ENDPOINT, "credential_source": args.credential_source, "credential_matches_process_configuration": hmac.compare_digest(api_key, os.environ.get("OPENAI_API_KEY", "")),
        "source_identity": identity, "runtime": runtime_versions(), "checks": [], "benchmark_score": None,
        "approval": "NOT_GRANTED", "release_status": "NOT_RELEASED", "data_origin": "SYNTHETIC_NOT_BUSINESS_DATA",
        "limitations": ["Primitive pipeline smoke, not complete TwoAgentV3 or a public benchmark experiment",
            "Proxy model ID/effort echoes are not cryptographic attestation of model weights or upstream routing",
            "Two synthetic images are not a complete multimodal benchmark or ingestion pipeline test"]}
    client, started = BoundedClient(api_key), perf_counter()
    try:
        report["model_listing"] = client.health()
        print(json.dumps({"event": "MODEL_LISTED", "model": MODEL, "credential_matches_process_configuration": report["credential_matches_process_configuration"]}), flush=True)
        text = "North Grove is a woodland. Every woodland is an ecosystem. Sensor Alpha monitors North Grove. Sensor Alpha is a sensor."
        sample = ModelingInput(sample_id="synthetic-woodland", benchmark_id="synthetic-engineering", task_id="text-new",
            dataset_version="synthetic-v1", split="ENGINEERING_CHECK", evaluation_scope="ENGINEERING_CHECK", group_id=semantic_hash(text),
            mode="TEXT_NEW", text=text, requirements=["Use source labels and preserve instance-of versus is-a."])
        protocol = Protocol(protocol_id="astra-xhigh-synthetic-v1", model_id=MODEL, declared_revision="configured-alias:" + MODEL,
            reasoning_effort=EFFORT, systems=["DirectGeneralLLM", "TwoAgentV3"], replicates=1,
            budget=Budget(max_calls=2, max_output_tokens=8192, max_total_tokens=60000, max_input_characters=14000, context_window_tokens=32768))
        # Expected engineering facts stay out of both model inputs.
        expected = {native_exact_key(row) for row in [("North Grove", "instance-of", "woodland"), ("woodland", "is-a", "ecosystem"),
            ("Sensor Alpha", "monitors", "North Grove"), ("Sensor Alpha", "instance-of", "sensor")]}
        for system in protocol.systems:
            result = generate_sample(sample, protocol, system, output / system, client=client)
            check = {"case": system, "status": result["status"], "result_ref": system + "/result.json", "resources": result["resources"]}
            if result["status"] != "GENERATED":
                check.update(failure_type=result.get("failure_type"), failure_code=result.get("failure_code"), transport=getattr(client, "last_transport_error", None))
                report["checks"].append(check)
                raise ToolBlocked("MODEL_GENERATION_FAILED_STOPPING_SMOKE")
            actual = {native_exact_key(row) for row in result["prediction"]["triples"]}
            check.update(status="PASS" if actual == expected else "FAIL_SYNTHETIC_FACT_CHECK", actual_triple_count=len(actual), expected_triple_count=len(expected),
                observed_model_ids=sorted({c["model"]["observed_model_id"] for c in result["calls"]}),
                reasoning_attestations=[c["model"]["reasoning_attestation"] for c in result["calls"]])
            report["checks"].append(check)
            print(json.dumps({"event": "CASE_COMPLETED", "case": system, "status": check["status"]}), flush=True)
        for index, raw in enumerate(images):
            (output / f"image-{index + 1}.png").write_bytes(raw)
        vision = client.propose("Read both attached images. Each has three coloured squares. For each image, list the square fill colours left to right in lower-case English. Ignore the white background.",
            {"image_order": ["image-1", "image-2"]},
            {"type": "object", "additionalProperties": False, "required": ["image_1", "image_2"], "properties": {
                key: {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "string"}} for key in ("image_1", "image_2")}},
            image_data_urls=["data:image/png;base64," + base64.b64encode(raw).decode() for raw in images])
        (output / "vision-response.json").write_text(json.dumps(vision, ensure_ascii=False, indent=2), encoding="utf-8")
        report["checks"].append({"case": "TWO_IMAGE_COLOUR_ORDER", "status": "PASS" if vision["proposal"] == {"image_1": ["blue", "green", "red"], "image_2": ["green", "red", "blue"]} else "FAIL_SYNTHETIC_IMAGE_CHECK",
            "model": vision["model"], "usage": vision["usage"], "response_ref": "vision-response.json"})
        report["status"] = "PASS" if all(c["status"] == "PASS" for c in report["checks"]) else "FAIL_ENGINEERING_CHECK"
    except Exception as exc:  # noqa: BLE001 - no credential-bearing messages
        report.update(status="FAILED", error_type=type(exc).__name__, transport=getattr(client, "last_transport_error", None), rejection=getattr(client, "last_rejection", None))
    finally:
        report.update(model_requests=client.attempts, elapsed_seconds=perf_counter() - started, source_unchanged=source_identity(ROOT) == identity)
        client.close()
        # Fail closed if a provider unexpectedly echoes authentication material.
        for path in output.rglob("*.json"):
            if api_key.encode() in path.read_bytes():
                path.write_bytes(path.read_bytes().replace(api_key.encode(), b"[REDACTED]"))
                report["credential_echo_redacted"] = True
        serialized = json.dumps(report, ensure_ascii=False, indent=2).replace(api_key, "[REDACTED]")
        (output / "report.json").write_text(serialized, encoding="utf-8")
        print(json.dumps({"status": report["status"], "model_requests": client.attempts, "evidence": str(output / "report.json")}), flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
