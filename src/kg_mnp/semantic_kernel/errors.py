"""Stable Prompt 5 failures and CLI exit codes."""

from __future__ import annotations

EXIT_CODES = {
    "COMPILER_INPUT_INVALID": 28,
    "COMPILATION_PLAN_INVALID": 29,
    "COMPILATION_FAILED": 30,
    "RDF_VALIDATION_FAILED": 31,
    "OWL_PROFILE_FAILED": 32,
    "OWL_CONSISTENCY_FAILED": 33,
    "SHACL_VALIDATION_FAILED": 34,
    "COMPETENCY_QUESTION_FAILED": 35,
    "PROVENANCE_CLOSURE_FAILED": 36,
    "ONTOLOGY_PACKAGE_INVALID": 37,
    "ONTOLOGY_PACKAGE_CONFLICT": 38,
    "PACKAGE_ARCHIVE_INVALID": 39,
    "BUILD_REPRODUCTION_MISMATCH": 40,
    "REASONER_UNAVAILABLE": 41,
}


class SemanticKernelError(ValueError):
    """Fail-closed semantic-kernel error with a stable machine code."""

    def __init__(self, message: str, *, code: str = "COMPILATION_FAILED") -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = EXIT_CODES.get(code, 30)


class InputAttestationError(SemanticKernelError):
    def __init__(self, message: str, *, code: str = "COMPILER_INPUT_INVALID") -> None:
        super().__init__(message, code=code)


class CompilationPlanError(SemanticKernelError):
    def __init__(self, message: str, *, code: str = "COMPILATION_PLAN_INVALID") -> None:
        super().__init__(message, code=code)


class PackageError(SemanticKernelError):
    def __init__(self, message: str, *, code: str = "ONTOLOGY_PACKAGE_INVALID") -> None:
        super().__init__(message, code=code)
