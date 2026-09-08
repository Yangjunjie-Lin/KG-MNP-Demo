from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.amendment.errors import AmendmentError, AmendmentErrorCode
from kg_mnp.amendment.review_bridge import require_explicit_review

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


def test_obsolete_licensed_publisher_is_retired() -> None:
    assert not (ROOT / "scripts/amendment_integration.py").exists()
