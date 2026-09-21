"""Prepare full request profiles/job and budget manifests; no model inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from zhigou_toolchain.modeling.five_stage.compatible import configured_client
from zhigou_toolchain.ontology_io.formal_calls import prepare_call_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-root", type=Path, default=Path("runtime_reports/ontology-io-final-matrix-20260913/full/prepared"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    client = configured_client()
    try:
        # Metadata query only; does NOT attest POST support or model weights.
        health = client.health()
        observed = {"model_id": client.lock.model_id, "declared_revision": client.lock.revision,
            "reasoning_effort": getattr(client, "reasoning_effort", None), "configured_response_format": getattr(client, "response_format", None),
            "health": health, "post_parameter_probe": "NOT_RUN", "weight_revision": "NOT_INDEPENDENTLY_ATTESTED"}
    finally:
        client.close()
    print(json.dumps(prepare_call_pack(args.prepared_root, args.output, observed_configuration=observed), ensure_ascii=False))


if __name__ == "__main__":
    main()
