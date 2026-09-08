"""Optional pytest evidence plugin: complete unique collection and executed nodes."""
from __future__ import annotations

import json
import os
from pathlib import Path

COLLECTION = []
REPORTS = []


def pytest_collection_finish(session):
    COLLECTION.extend(item.nodeid for item in session.items)


def pytest_runtest_logreport(report):
    row = {"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome,
           "duration": report.duration, "skip_reason": str(report.longrepr) if report.skipped else None,
           "wasxfail": getattr(report, "wasxfail", None)}
    REPORTS.append(row)
    # Per-process append streams survive a killed/incomplete run, but do not
    # turn its partial node union into a completed regression claim.
    directory = Path(os.environ["KG_MNP_RECEIPT_ROOT"])
    with (directory / f"progress-{os.getpid()}.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")


def pytest_sessionfinish(session, exitstatus):
    if hasattr(session.config, "workerinput"):
        return
    directory = Path(os.environ["KG_MNP_RECEIPT_ROOT"])
    # xdist reports carry all executed nodeids on the controller. Collection is
    # separately collected serially for the required union check.
    (directory / "collection.json").write_text(json.dumps(sorted(set(COLLECTION)), indent=2), encoding="utf-8")
    (directory / "reports.json").write_text(json.dumps(REPORTS, indent=2), encoding="utf-8")
