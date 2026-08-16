from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from kg_mnp_demo.amendment.errors import AmendmentError, AmendmentErrorCode
from kg_mnp_demo.amendment.review_bridge import require_explicit_review

ROOT = Path(__file__).resolve().parents[2]


def test_phase05_cannot_auto_confirm() -> None:
    with pytest.raises(AmendmentError) as error:
        require_explicit_review({"decisions": [], "review_session": {}})
    assert error.value.code == AmendmentErrorCode.AUTO_CONFIRM_BLOCKED


def test_completed_review_is_required_before_package_build() -> None:
    with pytest.raises(AmendmentError):
        require_explicit_review(
            {
                "decisions": [{"decision": "CONFIRM"}],
                "review_session": {"started_at": "2026-01-01T00:00:00Z"},
            }
        )


def test_licensed_entrypoint_supports_direct_script_execution() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/amendment_integration.py", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--stage08-artifact" in completed.stdout
