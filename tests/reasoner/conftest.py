from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


@pytest.fixture(scope="module")
def actual_reasoner_report(tmp_path_factory):
    """Execute pinned HermiT in a fresh corpus, never reuse ignored host output."""
    import run_reasoner as reasoner

    root = tmp_path_factory.mktemp("reasoner-report-corpus")
    sources = set(reasoner.release_source_files(ROOT, include_alignments=False))
    sources.add(ROOT / "config/reasoner-allowlist.yaml")
    for source in sources:
        destination = root / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    downloads = ROOT / "third_party/downloads"
    jar = downloads / reasoner.ROBOT_JAR_NAME
    assert jar.is_file() and reasoner.sha256_file(jar) == reasoner.EXPECTED_ROBOT_SHA256
    runtime = root / "runtime_reports/ontology"
    assert reasoner.run_reasoner(root=root, runtime_dir=runtime, download_dir=downloads) == 0
    report = reasoner.read_json(runtime / "reasoner-run.json")
    options = {"root": root, "runtime_dir": runtime, "download_dir": downloads}
    assert reasoner.validate_runtime_report(report, **options) == []
    return report, options
