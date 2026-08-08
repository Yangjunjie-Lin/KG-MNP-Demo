from kg_mnp_demo.modeling.cli import build_parser


def test_graphdb_cli_surface_remains_available_with_stage08_commands():
    parser = build_parser()
    args = parser.parse_args(["graphdb", "package", "inspect", "--package-dir", "x"])
    assert args.graphdb_package_command == "inspect"
    help_text = parser.format_help()
    assert "webvowl" in help_text.lower()
    assert "publication" in help_text.lower()
    assert "graphrag" not in help_text.lower()
