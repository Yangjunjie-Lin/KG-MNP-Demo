"""Keep all capability gates active on both long-lived branches."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ("ci-backend", "ci-quality", "ci-release-check", "ci-security", "ci-workbench")


def workflow(name):
    # BaseLoader keeps GitHub's YAML 1.2 `on` key as a string (not YAML 1.1 True).
    return yaml.load((ROOT / ".github/workflows" / f"{name}.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


@pytest.mark.parametrize("name", WORKFLOWS)
def test_all_gates_run_on_long_lived_branch_pushes_and_pull_requests(name):
    config = workflow(name)
    assert set(config["on"]) == {"push", "pull_request", "workflow_dispatch"}
    for event in ("push", "pull_request"):
        assert config["on"][event] == {"branches": ["main", "develop"]}
    assert config["permissions"] == {"contents": "read"}
    assert config["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.ref }}", "cancel-in-progress": "true",
    }
    for job in config["jobs"].values():
        assert int(job["timeout-minutes"]) > 0
        assert "continue-on-error" not in job
        for step in job["steps"]:
            assert "continue-on-error" not in step
            assert "|| true" not in step.get("run", "")
            if step.get("uses", "").startswith("actions/upload-artifact@"):
                assert step["if"] == "always()"


@pytest.mark.parametrize(("name", "job"), [("ci-backend", "backend"), ("ci-release-check", "distributions")])
def test_backend_and_isolated_installs_cover_both_platforms(name, job):
    strategy = workflow(name)["jobs"][job]["strategy"]
    assert strategy["fail-fast"] == "false"
    assert set(strategy["matrix"]["os"]) == {"ubuntu-latest", "windows-latest"}


def test_quality_includes_every_generated_input_and_hygiene_gate():
    commands = {step["run"] for step in workflow("ci-quality")["jobs"]["quality"]["steps"] if "run" in step}
    assert {
        "python -m ruff check .", "python tools/check_types.py",
        "python tools/generate_compiler_contracts.py --check",
        "python scripts/generate_contract_catalog.py --check",
        "python tools/check_domain_baselines.py --check",
        "python scripts/generate_ingestion_examples.py --check",
        "python scripts/check_repo_hygiene.py",
        "npm --prefix workbench run lint", "npm --prefix workbench run typecheck",
        "git diff --exit-code",
    } <= commands


def test_real_business_workflows_and_component_rendering_are_separate_gates():
    jobs = workflow("ci-workbench")["jobs"]
    commands = {name: {step["run"] for step in job["steps"] if "run" in step} for name, job in jobs.items()}
    assert "python tools/run_browser_verification.py" in commands["workbench"]
    assert "npm --prefix workbench run test:rendering" in commands["rendering"]
