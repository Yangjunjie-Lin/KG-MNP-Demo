"""Independent exact-content audit, using frozen visual gold, NOT model labels.

MP4 constant-frame-rate conversion can retain the outgoing image on a boundary
frame. Identify each decoded frame by pixel distance to the already frozen gold
images; never choose its expected text by looking at the model's prediction.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import cv2
import numpy as np


def normalize(value):
    return re.sub(r"[^\w]", "", value.casefold())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gold = json.loads((args.fixtures / "gold.json").read_bytes())
    report = json.loads(args.report.read_bytes())
    rows = []
    references = {name: cv2.imdecode(np.frombuffer((args.fixtures / name).read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR).astype(np.float32)
        for name in ("positive.png", "negative.png")}
    for case in report["cases"]:
        for index, observation in enumerate(case["receipt"]["observations"]):
            source = case["source"]
            scores = None
            if observation["method"] == "OCR_SAMPLED_VIDEO_FRAME":
                capture = cv2.VideoCapture(str(args.fixtures / source))
                try:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, observation["inference"]["frame_index"])
                    ok, frame = capture.read()
                    assert ok
                finally:
                    capture.release()
                scores = {name: float(np.mean((frame.astype(np.float32) - reference) ** 2)) for name, reference in references.items()}
                ranked = sorted(scores, key=scores.get)
                # Fail on an unclear visual oracle, independently of OCR output.
                assert scores[ranked[0]] < 5 and scores[ranked[1]] - scores[ranked[0]] > 5, scores
                expected = gold["visual"][ranked[0]]
            elif source == "speech.wav" or observation["method"] == "ASR_VIDEO_AUDIO_TRACK":
                expected = gold["speech"]
            elif source.endswith(".pdf"):
                expected = gold["visual"]["positive.png"]
            else:
                expected = gold["visual"][source]
            rows.append({"source": source, "ordinal": index, "method": observation["method"],
                "receipt_hash": case["receipt"]["receipt_hash"], "exact_match": normalize(observation["text"]) == normalize(expected),
                "visual_reference_mse": scores})
    result = {"normalization": "Unicode casefold; remove punctuation and whitespace; preserve letters, numbers and underscores",
        "gold_origin": "Frozen fixture gold.json and source images, never predicted text", "cases": len(report["cases"]),
        "observations": len(rows), "results": rows, "passed": len(rows) == 11 and len(report["cases"]) == 7 and all(r["exact_match"] for r in rows)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}))
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
