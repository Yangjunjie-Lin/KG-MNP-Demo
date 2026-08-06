from ._helpers import build


def test_shacl_report_is_deterministic(tmp_path):
    one, _, _ = build(tmp_path / "one")
    two, _, _ = build(tmp_path / "two")
    assert one.joinpath("shacl/report.json").read_bytes() == two.joinpath("shacl/report.json").read_bytes()
