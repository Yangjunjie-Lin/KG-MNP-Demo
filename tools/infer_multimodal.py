"""Explicit local OCR / hosted ASR, producing unapproved source-bound observations.

Never called automatically by ingestion.plan/run. Network audio transfer requires
--authorize-network, and the caller must have authority over the input material.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from zhigou_toolchain.ingestion.multimodal import (
    HostedASR,
    InferenceLimits,
    LocalQwenVision,
    infer,
    verify_receipt,
)
from zhigou_toolchain.modeling.five_stage.tools import ModelLock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--media-type", required=True, choices=["image/png", "image/jpeg", "image/tiff", "application/pdf", "audio/wav", "video/mp4"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vision-path", type=Path, help="Existing immutable Qwen/Qwen2-VL-2B-Instruct snapshot directory")
    parser.add_argument("--authorize-network", action="store_true", help="Explicitly authorize uploading this audio/video audio track to SiliconFlow")
    parser.add_argument("--asr-model", default="Qwen/Qwen3-ASR-1.7B")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; choose a fresh receipt path")
    if args.source.stat().st_size > InferenceLimits().max_source_bytes:
        parser.error("source exceeds the bounded inference limit")
    content = args.source.read_bytes()
    vision = None
    if args.vision_path:
        path = args.vision_path.resolve(strict=True)
        vision = LocalQwenVision(ModelLock("Qwen/Qwen2-VL-2B-Instruct", path.name, str(path)))
    asr = None
    try:
        if args.authorize_network and args.media_type in {"audio/wav", "video/mp4"}:
            asr = HostedASR(ModelLock(args.asr_model, "provider-alias:" + args.asr_model, "https://api.siliconflow.cn/v1"), api_key=os.environ["SILICONFLOW_API_KEY"])
        receipt = infer(content, args.media_type, vision=vision, asr=asr, network_authorized=args.authorize_network)
        verify_receipt(receipt, content=content, expected_receipt_hash=receipt["receipt_hash"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
        print(json.dumps({"receipt_hash": receipt["receipt_hash"], "observations": len(receipt["observations"]), "approval": "NOT_GRANTED"}))
    finally:
        if asr:
            asr.close()


if __name__ == "__main__":
    main()
