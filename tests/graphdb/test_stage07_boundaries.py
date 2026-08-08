from pathlib import Path


def test_stage07_remains_separate_after_stage08_completion():
    root = Path(__file__).resolve().parents[2]
    source = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (root / "src/kg_mnp_demo/graphdb").glob("*.py"))
    assert "WebVOWL" not in source
    assert "GraphRAG" not in source
    assert (root / "src/kg_mnp_demo/webvowl").is_dir()
    assert not (root / "src/kg_mnp_demo/stage09").exists()
