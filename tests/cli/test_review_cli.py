from __future__ import annotations

import pytest

from kg_mnp.root_cli import main


def test_review_help_has_no_bypass_routes(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["review", "--help"])
    assert raised.value.code == 0
    output = capsys.readouterr().out
    for command in ("queue", "decide", "status", "replay", "finalize", "package"):
        assert command in output
    for forbidden in ("accept-all", "auto", "bypass", "force-finalize", "llm"):
        assert forbidden not in output
