import pytest

from ._helpers import authorities
from kg_mnp_demo.compilation.compiler import CompilationError, validate_ready_package


def test_ready_gate_rejects_blocked_package():
    values = list(authorities("deferred-review"))
    with pytest.raises((CompilationError, ValueError)):
        validate_ready_package(*values)
