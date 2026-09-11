"""Historical compilation readers; current builds use semantic_kernel."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .compiler import CompilationError, validate_compilation_authorities
    from .validator import validate_compilation_package_against_authorities

__all__ = [
    "CompilationError",
    "validate_compilation_authorities",
    "validate_compilation_package_against_authorities",
]


def __getattr__(name):
    # Reading a canonical RDF primitive must not import repository-only legacy
    # builders during installed service/CLI startup.
    if name in {"CompilationError", "validate_compilation_authorities"}:
        from .compiler import CompilationError, validate_compilation_authorities
        return {"CompilationError": CompilationError, "validate_compilation_authorities": validate_compilation_authorities}[name]
    if name == "validate_compilation_package_against_authorities":
        from .validator import validate_compilation_package_against_authorities
        return validate_compilation_package_against_authorities
    raise AttributeError(name)
