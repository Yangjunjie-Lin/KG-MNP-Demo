"""Explicitly prepare immutable public model snapshots; never run on app startup."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


def main():
    root = Path(__file__).resolve().parents[1] / "runtime" / "models"
    root.mkdir(parents=True, exist_ok=True)
    api = HfApi()
    models = ["BAAI/bge-m3", "BAAI/bge-reranker-v2-m3", "Qwen/Qwen2.5-7B-Instruct"]
    for model_id in models:
        info = api.model_info(model_id)
        revision = info.sha
        files = [s.rfilename for s in info.siblings]
        patterns = ["config.json", "tokenizer*", "special_tokens_map.json", "sentencepiece.bpe.model", "vocab.json", "merges.txt", "modules.json", "sentence_bert_config.json", "config_sentence_transformers.json", "1_Pooling/config.json"]
        if model_id.startswith("BAAI/"):
            patterns += ["model.safetensors" if "model.safetensors" in files else "pytorch_model.bin", "sparse_linear.pt", "colbert_linear.pt"]
        target = root / model_id.replace("/", "--") / revision
        print(json.dumps({"preparing": model_id, "revision": revision}), flush=True)
        snapshot_download(model_id, revision=revision, local_dir=target, allow_patterns=patterns, max_workers=3)
        hashes = {}
        for path in sorted(target.rglob("*")):
            if path.is_file() and ".cache" not in path.relative_to(target).parts:
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                hashes[path.relative_to(target).as_posix()] = {"sha256": digest, "bytes": path.stat().st_size}
        manifest = {"model_id": model_id, "revision": revision, "location": str(target.resolve()), "files": hashes}
        (root / (model_id.replace("/", "--") + ".json")).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"prepared": model_id, "files": len(hashes)}), flush=True)


if __name__ == "__main__":
    main()
