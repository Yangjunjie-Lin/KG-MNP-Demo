import importlib.util
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

spec = importlib.util.spec_from_file_location("token_snapshot", Path(__file__).with_name("export_usage.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TokenReportTests(unittest.TestCase):
    def test_missing_usage_is_not_zero_or_budget_reservation(self):
        rows = [{"total_tokens": 0, "input_tokens": 0, "output_tokens": 0, "budget_charge": 0},
                {"total_tokens": 7, "input_tokens": 3, "output_tokens": 4, "budget_charge": 7},
                {"total_tokens": None, "input_tokens": None, "output_tokens": None, "budget_charge": 128000}]
        result = m.aggregate(rows)
        self.assertEqual(result["known_total"], 7)
        self.assertEqual(result["unknown_total_calls"], 1)
        self.assertIsNone(result["exact_total"])
        self.assertEqual(result["budget_charge"], 128007)

    def test_provider_integer_validation(self):
        for value in (True, -1, "7", 1.5, None):
            self.assertIsNone(m.integer(value))
        self.assertEqual(m.integer(0), 0)

    def test_public_diagnostic_usage_names_and_zero_are_preserved(self):
        self.assertEqual(m.provider_usage({"usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}}),
                         {"input": 3, "output": 4, "total": 7})
        self.assertEqual(m.provider_usage({"receipt": {"usage": {"prompt_tokens": 0, "completion_tokens": 5, "total_tokens": 5}}}),
                         {"input": 0, "output": 5, "total": 5})

    def test_direct_control_is_not_a_five_stage_run(self):
        request = {"instruction": "Independently self-check your previous output", "content": {"input": {}, "previous": {}}}
        self.assertEqual(m.classify(request, "DirectBudgetControl", [])[0], "DIRECT")

    def test_stage_mapping_requires_recorded_request_and_frozen_source(self):
        prefix = m.PREFIXES["vocabulary"]
        request = {"instruction": prefix + " synthetic", "content": {"input": {}, "reuse": {}, "retrieval": []}}
        self.assertEqual(m.classify(request, "TwoAgentKernelV1", [prefix + " synthetic"])[0], "S2")
        self.assertEqual(m.classify(request, "TwoAgentKernelV1", [])[0], "UNKNOWN")

    def test_feedback_does_not_turn_s3_into_s4(self):
        prefix = m.PREFIXES["triples"]
        request = {"instruction": prefix + " synthetic", "content": {"input": {}, "candidate_vocabulary": {}, "extraction_constraints": "x", "feedback": {}}}
        result = m.classify(request, "TwoAgentKernelV1", [prefix + " synthetic"])
        self.assertEqual(result[0], "S3")
        self.assertTrue(result[3])

    def test_snapshot_connections_reject_writes(self):
        intended = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=intended) as name:
            self.assertTrue(Path(name).resolve().is_relative_to(intended))
            path = Path(name) / "fixture.sqlite"
            with closing(sqlite3.connect(path)) as conn:
                conn.execute("CREATE TABLE fixture (value INTEGER)")
            conn = m.read_db(path)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    conn.execute("INSERT INTO fixture VALUES (1)")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
