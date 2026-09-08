"""One complete development/CI collection with unique owned evidence/temp roots."""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from verify_release_candidate import run

    directory = ROOT / "runtime_logs" / ("backend-" + uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    # pytest does not create missing parents of an explicit basetemp. Keeping
    # it beneath the fresh evidence directory also avoids deleting old runs.
    result = run(directory, "run", [sys.executable, "-m", "pytest", "-q", "--basetemp=" + str(directory / "temp")], pytest_run=True)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
