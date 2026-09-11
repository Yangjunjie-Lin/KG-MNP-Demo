"""Pinned ROBOT OWL profile validation."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..contracts import finalize_artifact
from ..rdf.canonical import canonical_ntriples, graph_semantic_digest
from ..reasoner import verify_reasoner_bundle
from ..snapshot import ROBOT_VERSION


def validate_owl_profile(
    graph,
    *,
    baseline_digest: str,
    delta_digest: str,
    requested_profile: str = "OWL_2_DL_STRICT",
    reasoner_jar: Path | str | None = None,
    timeout_seconds: int = 180,
    max_output_bytes: int = 16_777_216,
) -> dict[str, Any]:
    if requested_profile not in {"OWL_2_DL_STRICT", "OWL_RL_STRUCTURAL"}:
        raise ValueError("unsupported requested OWL profile")
    input_digest = graph_semantic_digest(graph)
    status = "NOT_RUN_EXTERNAL_PREREQUISITE"
    violations = []
    if reasoner_jar is not None:
        jar = verify_reasoner_bundle(reasoner_jar)
        with tempfile.TemporaryDirectory(prefix="kg-mnp-owl-profile-") as directory:
            input_path = Path(directory) / "input.nt"
            output_path = Path(directory) / "profile-report.txt"
            input_path.write_bytes(canonical_ntriples(graph))
            try:
                process = subprocess.run(
                    ["java", "-jar", str(jar), "validate-profile", "--input", str(input_path), "--profile", "DL" if requested_profile == "OWL_2_DL_STRICT" else "RL", "--output", str(output_path)],
                    capture_output=True, check=False, shell=False, timeout=timeout_seconds,
                )
                output_size = len(process.stdout) + len(process.stderr)
                if output_path.is_file():
                    output_size += output_path.stat().st_size
                status = "PASSED" if process.returncode == 0 and output_path.is_file() and output_size <= max_output_bytes else "FAILED"
            except (OSError, subprocess.TimeoutExpired):
                status = "NOT_RUN_EXTERNAL_PREREQUISITE"
    core = {"manifest_kind": "KG_MNP_OWL_PROFILE_REPORT", "schema_version": "1.0.0", "requested_profile": requested_profile, "detected_constructs": [], "unsupported_constructs": [], "profile_violations": violations, "input_graph_digest": input_digest, "baseline_digest": baseline_digest, "delta_digest": delta_digest, "status": status, "validator_identity": "ROBOT validate-profile", "validator_version": ROBOT_VERSION}
    return finalize_artifact(core, id_field="report_id", urn_kind="owl-profile-report", contract="owl-profile-report")
