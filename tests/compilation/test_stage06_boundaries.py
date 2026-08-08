import argparse
from pathlib import Path

from kg_mnp_demo.modeling.cli import build_parser

ROOT = Path(__file__).resolve().parents[2]


def test_stage06_compiler_remains_separate_from_final_integrations():
    parser = build_parser()
    action = next(item for item in parser._actions if isinstance(item, argparse._SubParsersAction))
    assert "compile" in action.choices
    assert "graphdb" in action.choices
    assert {"webvowl", "publication"} <= set(action.choices)
    assert "api" not in action.choices
    assert not (ROOT / "src/kg_mnp_demo/graphdb.py").exists()
