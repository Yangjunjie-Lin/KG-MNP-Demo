from __future__ import annotations

import run_reasoner as reasoner


def test_success_log_may_contain_word_unsatisfiable():
    status = reasoner.classify_reasoner_status(
        executed=True,
        exit_code=0,
        output="Checking for unsatisfiable classes... none found",
        reasoned_output_ready=True,
        equivalence_check_ran=True,
    )
    assert status == (reasoner.STATUS_PASS, reasoner.CONSISTENT)


def test_not_executed_is_not_run_not_pass():
    assert reasoner.classify_reasoner_status(executed=False, exit_code=None) == (
        reasoner.STATUS_NOT_RUN,
        reasoner.UNKNOWN,
    )


def test_nonzero_exit_without_logical_signal_is_tool_error():
    assert reasoner.classify_reasoner_status(
        executed=True,
        exit_code=2,
        output="Could not open input file",
    ) == (reasoner.STATUS_FAIL_TOOL_ERROR, reasoner.UNKNOWN)


def test_explicit_inconsistency_is_distinct_from_tool_error():
    assert reasoner.classify_reasoner_status(
        executed=True,
        exit_code=1,
        output="The ontology is inconsistent.",
    ) == (reasoner.STATUS_FAIL_INCONSISTENT, reasoner.INCONSISTENT)


def test_unsatisfiable_named_class_is_distinct_failure():
    iri = reasoner.TERM_NAMESPACE + "Impossible"
    assert reasoner.unsatisfiable_classes_from_robot_output(
        f"unsatisfiable: <{iri}>"
    ) == [iri]
    assert reasoner.classify_reasoner_status(
        executed=True,
        exit_code=1,
        output=f"unsatisfiable: <{iri}>",
        unsatisfiable_named_classes=[iri],
    ) == (reasoner.STATUS_FAIL_UNSATISFIABLE_CLASSES, reasoner.CONSISTENT)


def test_unsatisfiable_class_is_extracted_from_robot_logback_line():
    iri = reasoner.TERM_NAMESPACE + "Impossible"
    output = (
        "2026-08-05 14:20:31,000 ERROR org.obolibrary.robot.ReasonerHelper - "
        f"    unsatisfiable: {iri}\n"
    )
    assert reasoner.unsatisfiable_classes_from_robot_output(output) == [iri]


def test_incidental_unsatisfiable_text_remains_a_tool_error():
    output = "ERROR parser - failed to parse unsatisfiable: report"
    assert reasoner.unsatisfiable_classes_from_robot_output(output) == []
    assert reasoner.classify_reasoner_status(
        executed=True,
        exit_code=2,
        output=output,
    ) == (reasoner.STATUS_FAIL_TOOL_ERROR, reasoner.UNKNOWN)


def test_missing_reasoned_output_is_tool_error():
    assert reasoner.classify_reasoner_status(
        executed=True,
        exit_code=0,
        reasoned_output_ready=False,
    ) == (reasoner.STATUS_FAIL_TOOL_ERROR, reasoner.UNKNOWN)


def test_equivalence_check_not_run_cannot_pass():
    assert reasoner.classify_reasoner_status(
        executed=True,
        exit_code=0,
        reasoned_output_ready=True,
        equivalence_check_ran=False,
    ) == (reasoner.STATUS_FAIL_TOOL_ERROR, reasoner.CONSISTENT)


def test_unexpected_equivalence_has_dedicated_failure():
    assert reasoner.classify_reasoner_status(
        executed=True,
        exit_code=0,
        reasoned_output_ready=True,
        equivalence_check_ran=True,
        unexpected_equivalent_classes=[["https://example.test/A", "https://example.test/B"]],
    ) == (reasoner.STATUS_FAIL_UNEXPECTED_EQUIVALENCES, reasoner.CONSISTENT)
