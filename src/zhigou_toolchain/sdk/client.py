from __future__ import annotations

from typing import Protocol

from zhigou_toolchain.services.models import OperationRequest, OperationResult


class ToolchainClient(Protocol):
    def execute(self, request: OperationRequest) -> OperationResult: ...
