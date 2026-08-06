from kg_mnp_demo.compilation.validator import validate_compilation_package_against_authorities
from ._helpers import authorities, build


def test_independent_validator_reconstructs_expected_set(tmp_path):
    directory, _, _ = build(tmp_path)
    assert validate_compilation_package_against_authorities(directory, *authorities())["valid"] is True
