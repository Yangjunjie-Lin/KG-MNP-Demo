import pytest

from kg_mnp.compilation.compiler import CompilationError, validate_ready_package

from ._helpers import authorities


def test_ready_gate_rejects_blocked_package():
    values = list(authorities("deferred-review"))
    with pytest.raises((CompilationError, ValueError)):
        validate_ready_package(*values)
