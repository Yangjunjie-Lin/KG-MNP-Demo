"""Repeatable actual-model engineering tests. Synthetic gold is never a model input.

Run prepare, then original and multimodal in isolated processes to bound RAM.
All attempts are retained. A PASS is not a production/research accuracy claim.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import re
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zhigou_toolchain.contracts.canonical import bytes_sha256, semantic_hash
from zhigou_toolchain.ingestion.multimodal import (
    HostedASR,
    LocalQwenVision,
    infer,
    verify_receipt,
)
from zhigou_toolchain.modeling.five_stage.tools import (
    ModelLock,
    ToolBlocked,
    bind_quote,
    rerank,
    text_chunks,
    vector_recall,
)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def normalized(text):
    return re.sub(r"[^\w]", "", text.casefold())


def prepare(root):
    import imageio_ffmpeg
    from PIL import Image, ImageDraw, ImageFont
    from pypdf import PdfReader
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    folder = root / "fixtures"
    folder.mkdir(parents=True, exist_ok=False)
    plan = {"data_origin": "SYNTHETIC_ENGINEERING_FIXTURES", "not_research_benchmark": True,
        "visual": {"positive.png": "Tree GT-001\nInspection I-001\nDamage: YES",
                   "negative.png": "Tree GT-002\nInspection I-002\nDamage: NO",
                   "chinese.png": "巡检记录\n树木 GT-003\n损伤：未知\n状态：待复查"},
        "speech": "Tree one has damage. Tree two has no damage. Tree three needs inspection.",
        "retrieval": [{"query": "tree damage inspection", "expected_iri": "urn:test:Inspection"},
                      {"query": "employee salary payment", "expected_iri": "urn:test:Payroll"}]}
    save(folder / "gold.json", plan)  # Frozen before files or model inference.
    for name, value in plan["visual"].items():
        image = Image.new("RGB", (800, 480), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc" if name == "chinese.png" else "C:/Windows/Fonts/arial.ttf", 42)
        draw.multiline_text((50, 50), value, fill="black", font=font, spacing=24)
        image.save(folder / name)
    scan = Canvas(str(folder / "scanned.pdf"), pagesize=(800, 480))
    scan.drawImage(ImageReader(str(folder / "positive.png")), 0, 0, width=800, height=480)
    scan.save()
    text_pdf = Canvas(str(folder / "text.pdf"), pagesize=(800, 480))
    text_pdf.setFont("Helvetica", 32)
    for i, line in enumerate(plan["visual"]["positive.png"].splitlines()):
        text_pdf.drawString(50, 400 - i * 60, line)
    text_pdf.save()
    assert not PdfReader(folder / "scanned.pdf").pages[0].extract_text().strip()
    assert "GT-001" in PdfReader(folder / "text.pdf").pages[0].extract_text()
    # Fixed script and paths supplied through environment: no interpolated shell text.
    env = {**os.environ, "ZHIGOU_FIXTURE_WAV": str((folder / "speech.wav").resolve()), "ZHIGOU_FIXTURE_SPEECH": plan["speech"]}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Add-Type -AssemblyName System.Speech; $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speaker.SetOutputToWaveFile($env:ZHIGOU_FIXTURE_WAV); $speaker.Speak($env:ZHIGOU_FIXTURE_SPEECH); $speaker.Dispose()"], env=env, check=True)
    # Two genuinely distinct visual segments plus an actual audio track.
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error", "-loop", "1", "-t", "5", "-i", str(folder / "positive.png"),
        "-loop", "1", "-t", "5", "-i", str(folder / "negative.png"), "-i", str(folder / "speech.wav"),
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", "2", "-c:a", "aac", "-t", "10", str(folder / "inspection.mp4")], check=True, timeout=45)
    files = {p.name: {"sha256": bytes_sha256(p.read_bytes()), "bytes": p.stat().st_size} for p in folder.iterdir() if p.is_file()}
    save(root / "fixture-lock.json", {"files": files, "gold_frozen_before_inference": True, "files_hash": semantic_hash(files)})


def locked_model(model_id):
    manifest = json.loads((ROOT / "runtime/models" / (model_id.replace("/", "--") + ".json")).read_bytes())
    location = Path(manifest["location"])
    for name, expected in manifest["files"].items():
        path = location / name
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected["sha256"]:
            raise ToolBlocked("MODEL_FILE_CHANGED")
    return ModelLock(model_id, manifest["revision"], str(location)), manifest


def original(root, record):
    cards = [
        {"iri": "urn:test:Inspection", "label": "Tree damage inspection", "definition": "A survey of a tree for damage, disease and safety.", "element_kind": "CLASS"},
        {"iri": "urn:test:Payroll", "label": "Employee payroll", "definition": "Salary payments and compensation for employees.", "element_kind": "CLASS"},
        {"iri": "urn:test:Department", "label": "Department", "definition": "An organizational unit employing staff.", "element_kind": "CLASS"},
        {"iri": "urn:test:locatedAt", "label": "located at", "definition": "Object property relating a tree to its site.", "element_kind": "OBJECT_PROPERTY"}]
    gold = json.loads((root / "fixtures/gold.json").read_bytes())
    embedding, em = locked_model("BAAI/bge-m3")
    ranking, rm = locked_model("BAAI/bge-reranker-v2-m3")
    tokenizer, tm = locked_model("Qwen/Qwen2.5-7B-Instruct")
    record["model_manifests"] = [em, rm, tm]
    record["retrieval"] = []
    for case in gold["retrieval"]:
        recall = vector_recall(case["query"], cards, embedding, top_k=4)
        gc.collect()
        ranked = rerank(case["query"], recall["candidates"], ranking, expected_kind="CLASS")
        passed = ranked["candidates"][0]["card"]["iri"] == case["expected_iri"]
        record["retrieval"].append({"query": case["query"], "recall": recall, "rerank": ranked, "passed": passed})
        save(root / (record["attempt_id"] + "-original-in-progress.json"), record)
        assert passed
        gc.collect()
    text = "树木 GT-001 存在损伤。树木 GT-002 没有损伤。树木 GT-003 损伤状态未知。"
    chunks = text_chunks(text, text_id="synthetic:inspection", text_version=semantic_hash(text), lock=tokenizer, window=16, overlap=4)
    quote = "树木 GT-002 没有损伤。"
    matching = next(c for c in chunks["chunks"] if quote in c["text"])
    binding = bind_quote(text, matching, quote)
    assert text[binding["start"]:binding["end"]] == quote
    record.update(tokenizer=chunks, exact_negative_quote=binding)


def multimodal(root, record, vision_path, asr_model):
    from zhigou_toolchain.plugins.builtin.image_metadata_parser import (
        ImageMetadataParser,
    )
    from zhigou_toolchain.plugins.builtin.wav_metadata_parser import WavMetadataParser
    from zhigou_toolchain.plugins.models import ParseRequest
    vision_path = vision_path.resolve(strict=True)
    lock = ModelLock("Qwen/Qwen2-VL-2B-Instruct", vision_path.name, str(vision_path))
    hashes = {}
    for path in sorted(vision_path.iterdir()):
        if path.is_file():
            with path.open("rb") as stream:
                hashes[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    record["vision_manifest"] = {"model_id": lock.model_id, "revision": lock.revision, "files": hashes}
    print(json.dumps({"loading_local_vision": lock.model_id, "device": "CPU"}), flush=True)
    vision = LocalQwenVision(lock)
    asr = HostedASR(ModelLock(asr_model, "provider-alias:" + asr_model, "https://api.siliconflow.cn/v1"), api_key=os.environ["SILICONFLOW_API_KEY"])
    gold = json.loads((root / "fixtures/gold.json").read_bytes())
    cases = [(name, "image/png", [value]) for name, value in gold["visual"].items()]
    cases += [("scanned.pdf", "application/pdf", [gold["visual"]["positive.png"]]),
              ("text.pdf", "application/pdf", [gold["visual"]["positive.png"]]),
              ("speech.wav", "audio/wav", [gold["speech"]]),
              ("inspection.mp4", "video/mp4", [gold["visual"]["positive.png"], gold["visual"]["negative.png"], gold["speech"]])]
    record["cases"] = []
    try:
        for filename, media_type, expected in cases:
            started = perf_counter()
            raw = (root / "fixtures" / filename).read_bytes()
            receipt = infer(raw, media_type, vision=vision, asr=asr, network_authorized=True)
            verify_receipt(receipt, content=raw, expected_receipt_hash=receipt["receipt_hash"])
            observed = "\n".join(r["text"] for r in receipt["observations"])
            passed = all(normalized(wanted) in normalized(observed) for wanted in expected)
            item = {"source": filename, "passed": passed, "receipt": receipt, "duration_seconds": perf_counter() - started}
            record["cases"].append(item)
            save(root / (record["attempt_id"] + "-receipt-" + filename + ".json"), item)
            print(json.dumps({"case": filename, "passed": passed, "seconds": item["duration_seconds"]}), flush=True)
        # Existing metadata providers remain metadata; the new adapter never relabels them.
        image_units = ImageMetadataParser().parse(ParseRequest((root / "fixtures/positive.png").read_bytes(), "image/png"))
        wav_units = WavMetadataParser().parse(ParseRequest((root / "fixtures/speech.wav").read_bytes(), "audio/wav"))
        record["legacy_metadata_honest"] = all(u.unit_kind != "text-block" for u in [*image_units, *wav_units])
        assert record["legacy_metadata_honest"] and all(c["passed"] for c in record["cases"])
    finally:
        asr.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "original", "multimodal"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vision-path", type=Path)
    parser.add_argument("--asr-model", default="Qwen/Qwen3-ASR-1.7B")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from evaluate_research import fingerprint
    before, started = fingerprint(), perf_counter()
    record = {"stage": args.stage, "attempt_id": uuid4().hex, "source": before, "data_origin": "SYNTHETIC", "research_status": "INSUFFICIENT_EVIDENCE",
        "versions": {name: version(name) for name in ["torch", "transformers", "FlagEmbedding", "faiss-cpu", "httpx", "Pillow", "pypdfium2", "imageio-ffmpeg"]}}
    try:
        if args.stage == "prepare":
            prepare(args.output)
        else:
            lock = json.loads((args.output / "fixture-lock.json").read_bytes())
            assert semantic_hash(lock["files"]) == lock["files_hash"]
            for name, expected in lock["files"].items():
                assert bytes_sha256((args.output / "fixtures" / name).read_bytes()) == expected["sha256"]
            record["fixture_lock_hash"] = semantic_hash(lock)
            if args.stage == "original":
                original(args.output, record)
            else:
                multimodal(args.output, record, args.vision_path, args.asr_model)
        record["status"] = "PASS"
    except Exception as exc:  # noqa: BLE001 - persist all failed runs without secret-bearing exception messages
        import traceback
        record.update(status="FAIL", error_type=type(exc).__name__,
            error_code=str(exc) if isinstance(exc, ToolBlocked) else "STAGE_FAILED",
            location=[{"file": Path(f.filename).name, "line": f.lineno, "function": f.name} for f in traceback.extract_tb(exc.__traceback__)])
    record.update(duration_seconds=perf_counter() - started, source_unchanged=before == fingerprint())
    target = args.output / (args.stage + "-" + record["attempt_id"] + ".json")
    save(target, record)
    print(json.dumps({"status": record["status"], "report": str(target), "seconds": record["duration_seconds"]}), flush=True)
    return int(record["status"] != "PASS" or not record["source_unchanged"])


if __name__ == "__main__":
    raise SystemExit(main())
