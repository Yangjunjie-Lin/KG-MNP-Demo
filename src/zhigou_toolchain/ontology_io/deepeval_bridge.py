"""Optional DeepEval bridge to PINNED native scores, never an LLM judge.

Loaded only in a credential-free offline scoring worker. DeepEval is a test
framework, not an ontology benchmark or a replacement for native aggregation.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from .native_metrics import llms4ol_exact, llms4ol_fuzzy

DEEPEVAL_VERSION = "4.1.0"
OFFLINE_SETTINGS = {
    "DEEPEVAL_TELEMETRY_OPT_OUT": "1", "ERROR_REPORTING": "0", "DEEPEVAL_DISABLE_DOTENV": "1",
    "DEEPEVAL_DISABLE_LEGACY_KEYFILE": "1", "DEEPEVAL_UPDATE_WARNING_OPT_IN": "0",
    "CONFIDENT_TRACE_FLUSH": "0", "CONFIDENT_TRACE_SAMPLE_RATE": "0", "CONFIDENT_TRACE_INTERNAL": "0",
}
METRICS = ("edge_f1", "neighborhood_similarity", "taxonomy_similarity", "graph_similarity")


def require_offline_settings():
    if any(os.environ.get(k) != v for k, v in OFFLINE_SETTINGS.items()):
        raise ValueError("DEEPEVAL_OFFLINE_PROFILE_REQUIRED_BEFORE_IMPORT")
    if any(os.environ.get(k) for k in ("OPENAI_API_KEY", "CONFIDENT_API_KEY", "ANTHROPIC_API_KEY")):
        raise ValueError("DEEPEVAL_SCORING_WORKER_MUST_NOT_INHERIT_PROVIDER_CREDENTIALS")
    if version("deepeval") != DEEPEVAL_VERSION:
        raise ValueError("DEEPEVAL_VERSION_DIFFERS_FROM_AUDITED_LOCAL_LOCK")


def native_metric_class():
    """Import through the real public API only after offline preconditions."""
    require_offline_settings()
    from deepeval.metrics import BaseMetric

    class NativeOntologyMetric(BaseMetric):
        def __init__(self, upstream, *, name="edge_f1", matching="exact"):
            if name not in METRICS or matching not in {"exact", "fuzzy"}:
                raise ValueError("ONLY_PINNED_NATIVE_EXACT_OR_FUZZY_SUPPORTED")
            self.upstream = Path(upstream)
            self.metric_name = name
            self.matching = matching
            self.threshold = 1.0  # Full-match diagnostic only, NOT research acceptance.
            self.async_mode = False
            self.verbose_mode = False
            self.include_reason = False
            self.evaluation_model = "NO_LLM_PINNED_NATIVE_SCORER"
            self.evaluation_cost = None
            self.input_tokens = None
            self.output_tokens = None
            self.score = None
            self.success = False
            self.error = None

        def measure(self, test_case, *args, **kwargs):
            self.score, self.success, self.error = None, False, None
            try:
                if not isinstance(test_case.expected_output, str) or not isinstance(test_case.actual_output, str):
                    raise TypeError("NATIVE_SCORER_REQUIRES_BOTH_FROZEN_OUTPUTS")
                expected = json.loads(test_case.expected_output)
                predicted = json.loads(test_case.actual_output)
                for graph in (expected, predicted):
                    if not isinstance(graph, list) or any(not isinstance(t, list) or len(t) != 3
                            or any(not isinstance(x, str) for x in t) for t in graph):
                        raise ValueError("INVALID_NATIVE_TRIPLE_LIST")
                scorer = llms4ol_exact if self.matching == "exact" else llms4ol_fuzzy
                value = float(scorer(self.upstream, expected, predicted)[self.metric_name])
                self.score = value
                self.success = math.isfinite(value) and value >= self.threshold
                return value
            except Exception as exc:
                self.error = type(exc).__name__
                raise

        async def a_measure(self, test_case, *args, **kwargs):
            return self.measure(test_case, *args, **kwargs)

        def is_successful(self):
            return bool(self.error is None and self.success)

        @property
        def __name__(self):
            return "LLMs4OL_NATIVE_" + self.matching + "_" + self.metric_name

    return NativeOntologyMetric


def native_llms4ol_scorer(upstream, *, matching):
    """Reusable callable for the existing score CLI; only independent scoring."""
    metric_type = native_metric_class()
    from deepeval.test_case import LLMTestCase
    metrics = {name: metric_type(upstream, name=name, matching=matching) for name in METRICS}

    def score(gold, prediction):
        case = LLMTestCase(input="FROZEN_NATIVE_GRAPH_SCORING", expected_output=json.dumps(gold), actual_output=json.dumps(prediction))
        return {name: metric.measure(case) for name, metric in metrics.items()}

    return score


def offline_equivalence(upstream):
    """Synthetic matcher boundary checks only; NEVER baseline/Ours results."""
    require_offline_settings()
    if "deepeval" in sys.modules:
        raise ValueError("DEEPEVAL_WORKER_MUST_START_WITH_FRESH_IMPORT_STATE")
    # Windows implements asyncio's local wake-up pipe using a loopback
    # socketpair. Initialize that stdlib-only pipe BEFORE denying all network;
    # do not create an exception allowing arbitrary loopback/model endpoints.
    runner = asyncio.Runner()
    runner.get_loop()
    attempts = []

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            attempts.append(event)
            raise PermissionError("OFFLINE_SCORER_NETWORK_DENIED")

    sys.addaudithook(audit)
    try:
        return _equivalence_cases(upstream, attempts, runner)
    finally:
        runner.close()


def _equivalence_cases(upstream, attempts, runner):
    started = perf_counter()
    metric_type = native_metric_class()
    from deepeval.test_case import LLMTestCase
    import_seconds = perf_counter() - started
    cases = [([], []), ([["Oak", "is-a", "Tree"]], [["Oak", "is-a", "Tree"]]),
        ([["a", "p", "b"]], [["a", "p", "b"]]), ([["a", "p", "b"]], []), ([], [["a", "p", "b"]]),
        ([["Oak", "is-a", "Tree"]], [["Tree", "is-a", "Oak"]]),
        ([["Oak", "is-a", "Tree"]], [["Oak", "instance-of", "Tree"]]),
        ([["blue oak", "is-a", "tree"]], [[" blue oaks ", " IS-A ", " tree "]] * 2),
        ([["a", "is-a", "b"], ["b", "is-a", "c"]], [["a", "is-a", "c"]]),
        ([["a", "p", "b"]], [["a", "p", "b"], ["extra", "p", "wrong"]])]
    rows = []
    started = perf_counter()
    for matching in ("exact", "fuzzy"):
        scorer = llms4ol_exact if matching == "exact" else llms4ol_fuzzy
        for index, (gold, pred) in enumerate(cases):
            native = scorer(upstream, gold, pred)
            case = LLMTestCase(input="SYNTHETIC_MATCHER_BOUNDARY_ONLY", actual_output=json.dumps(pred), expected_output=json.dumps(gold))
            for name in METRICS:
                metric = metric_type(upstream, name=name, matching=matching)
                sync = metric.measure(case)
                asynchronous = runner.run(metric.a_measure(case))
                if sync != native[name] or asynchronous != native[name]:
                    raise ValueError("DEEPEVAL_WRAPPER_CHANGED_NATIVE_SEMANTICS")
                rows.append({"case": index, "metric": name, "matching": matching, "native": native[name],
                    "deepeval": sync, "async": asynchronous, "equivalent": True})
    # A malformed next prediction must not retain the previous score.
    rejected = False
    try:
        metric.measure(LLMTestCase(input="invalid", actual_output="not JSON", expected_output="[]"))
    except json.JSONDecodeError:
        rejected = metric.score is None and not metric.is_successful()
    if attempts or not rejected:
        raise ValueError("DEEPEVAL_OFFLINE_OR_FAILURE_ACCOUNTING_CHECK_FAILED")
    return {"status": "ENGINEERING_EQUIVALENCE_VERIFIED", "deepeval_version": version("deepeval"),
        "synthetic_cases": len(cases), "metric_comparisons": len(rows), "sync_and_async": True,
        "failed_metric_state_cleared": rejected, "rows": rows, "import_seconds": import_seconds,
        "scoring_check_seconds": perf_counter() - started, "network_attempts": attempts, "live_generation_calls": 0,
        "llm_judge_calls": 0, "research_scores": None, "telemetry": "DISABLED",
        "isolation_scope": "PYTHON_NETWORK_GUARD_NOT_OS_GOLD_SANDBOX",
        "scope": "SCORER_WRAPPER_TEST_NOT_MODEL_QUALITY_OR_FULL_BENCHMARK"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = offline_equivalence(args.upstream)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}))


if __name__ == "__main__":
    main()
