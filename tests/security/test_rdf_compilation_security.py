from __future__ import annotations

import pytest

from kg_mnp.semantic_kernel.literals import compile_literal
from kg_mnp.semantic_kernel.security import validate_iri, validate_relative_path


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/windows", "\\\\server\\share", "safe\\windows"])
def test_portable_paths_reject_traversal_absolute_windows_unc_and_backslash(path: str) -> None:
    with pytest.raises(ValueError):
        validate_relative_path(path)


@pytest.mark.parametrize("iri", ["file:///tmp/data", "javascript:alert(1)", "https://user:pass@example.test/x", "urn:test:<bad>"])
def test_unsafe_iri_schemes_credentials_and_injection_are_rejected(iri: str) -> None:
    with pytest.raises(ValueError):
        validate_iri(iri)


def test_external_code_like_text_remains_an_escaped_literal() -> None:
    text = "```python\nimport os; os.system('whoami')\n``` <urn:x> <urn:y> <urn:z> ."
    literal = compile_literal({"lexical_value": text, "datatype_iri": None, "language": None})
    assert str(literal) == text

