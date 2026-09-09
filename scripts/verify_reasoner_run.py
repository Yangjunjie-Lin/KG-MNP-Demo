#!/usr/bin/env python3
"""Verify the current ignored ROBOT/HermiT runtime evidence."""

from __future__ import annotations

from run_reasoner import (
    ROOT,
    RUNTIME_REPORT_PATH,
    read_json,
    validate_runtime_report,
)


def main() -> int:
    if not RUNTIME_REPORT_PATH.is_file():
        print("REASONER RUN CHECK FAILED")
        print("- reasoner-run.json: missing; run `python scripts/run_reasoner.py`")
        return 1
    try:
        report = read_json(RUNTIME_REPORT_PATH)
        errors = validate_runtime_report(report, root=ROOT)
    except Exception as exc:  # noqa: BLE001 - verifier must fail with context
        errors = [f"reasoner-run.json: cannot be verified: {exc}"]
    if errors:
        print("REASONER RUN CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Reasoner runtime evidence check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
