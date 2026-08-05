from __future__ import annotations

import subprocess

import run_reasoner as reasoner


def test_portability_detector_rejects_common_local_absolute_paths():
    samples = [
        "D:" + "\\workspace\\KG-MNP-Demo\\robot.jar",
        "C:" + "/workspace/KG-MNP-Demo/robot.jar",
        "/" + "home/alice/KG-MNP-Demo/robot.jar",
        "/" + "Users/alice/KG-MNP-Demo/robot.jar",
        "/" + "workspace/KG-MNP-Demo/robot.jar",
        "/" + "tmp/build/KG-MNP-Demo/robot.jar",
    ]
    for sample in samples:
        assert reasoner.find_portability_violations(sample), sample


def test_portable_placeholder_and_https_release_url_are_allowed():
    assert reasoner.find_portability_violations(reasoner.PORTABLE_ROBOT_COMMAND) == []
    assert reasoner.find_portability_violations(reasoner.ROBOT_URL) == []


def test_all_tracked_reasoner_reports_and_attestations_are_portable():
    result = subprocess.run(
        ["git", "ls-files", "docs/ontology/reasoner-*"],
        cwd=reasoner.ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    proof_files = [reasoner.ROOT / line for line in result.stdout.splitlines() if line]
    assert proof_files
    for path in proof_files:
        text = path.read_text(encoding="utf-8")
        assert reasoner.find_portability_violations(text) == [], path


def test_formal_proof_uses_only_portable_commands():
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    assert attestation["execution_command"] == "python scripts/run_reasoner.py"
    assert "<ROBOT_JAR>" in attestation["robot_command"]
    assert "<REASONER_INPUT>" in attestation["robot_command"]
