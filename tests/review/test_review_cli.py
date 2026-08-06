from __future__ import annotations

from pathlib import Path

from kg_mnp_demo.modeling.cli import main

from ._helpers import EXAMPLES, ROOT


def test_review_cli_init_status_record_finalize(tmp_path: Path):
    proposal = ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json"
    draft = tmp_path / "log-0.json"
    assert (
        main(
            [
                "review",
                "init",
                "--proposal",
                str(proposal),
                "--reviewer-id",
                "urn:kg-mnp:reviewer:professor-001",
                "--display-name",
                "Reviewer One",
                "--role",
                "Ontology Reviewer",
                "--session-id",
                "cli-session",
                "--started-at",
                "2026-08-06T00:00:00Z",
                "--output",
                str(draft),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "review",
                "status",
                "--proposal",
                str(proposal),
                "--decision-log",
                str(draft),
            ]
        )
        == 0
    )
    current = draft
    for index in range(1, 6):
        nxt = tmp_path / f"log-{index}.json"
        assert (
            main(
                [
                    "review",
                    "record",
                    "--proposal",
                    str(proposal),
                    "--decision-log",
                    str(current),
                    "--action",
                    str(EXAMPLES / "actions/full-confirmation" / f"action-{index:03d}.json"),
                    "--output",
                    str(nxt),
                ]
            )
            == 0
        )
        current = nxt
    final = tmp_path / "log-final.json"
    assert (
        main(
            [
                "review",
                "finalize",
                "--proposal",
                str(proposal),
                "--decision-log",
                str(current),
                "--completed-at",
                "2026-08-06T02:00:00Z",
                "--output",
                str(final),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "review",
                "validate",
                "--proposal",
                str(proposal),
                "--decision-log",
                str(final),
            ]
        )
        == 0
    )
