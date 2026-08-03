"""Unified application error model for CLI, API, and services."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    INPUT_SCHEMA_ERROR = "INPUT_SCHEMA_ERROR"
    INPUT_GRAPH_INVALID = "INPUT_GRAPH_INVALID"
    RULE_CONFIGURATION_ERROR = "RULE_CONFIGURATION_ERROR"
    ASSESSMENT_GRAPH_INVALID = "ASSESSMENT_GRAPH_INVALID"
    TRACE_INTEGRITY_ERROR = "TRACE_INTEGRITY_ERROR"
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    EXECUTION_NOT_FOUND = "EXECUTION_NOT_FOUND"
    STORAGE_ERROR = "STORAGE_ERROR"
    QUERY_NOT_FOUND = "QUERY_NOT_FOUND"
    QUERY_EXECUTION_ERROR = "QUERY_EXECUTION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_MESSAGES_ZH: dict[ErrorCode, str] = {
    ErrorCode.INPUT_SCHEMA_ERROR: "输入数据不符合 Schema。",
    ErrorCode.INPUT_GRAPH_INVALID: "输入图未通过 SHACL 验证。",
    ErrorCode.RULE_CONFIGURATION_ERROR: "规则配置无效。",
    ErrorCode.ASSESSMENT_GRAPH_INVALID: "评估结果图未通过 SHACL 验证。",
    ErrorCode.TRACE_INTEGRITY_ERROR: "追溯子图与 RDF 图不一致。",
    ErrorCode.CASE_NOT_FOUND: "未找到指定案件。",
    ErrorCode.EXECUTION_NOT_FOUND: "未找到指定评估执行记录。",
    ErrorCode.STORAGE_ERROR: "持久化存储不可用。",
    ErrorCode.QUERY_NOT_FOUND: "未找到指定能力问题。",
    ErrorCode.QUERY_EXECUTION_ERROR: "能力问题查询执行失败。",
    ErrorCode.INTERNAL_ERROR: "内部错误。",
}


class ApplicationError(Exception):
    """Stable, JSON-serializable application error."""

    def __init__(
        self,
        code: ErrorCode | str,
        message: str | None = None,
        *,
        details: list[Any] | None = None,
        retryable: bool = False,
    ) -> None:
        if isinstance(code, str):
            code = ErrorCode(code)
        self.code = code
        self.message = message or _MESSAGES_ZH.get(code, code.value)
        self.details = list(details or [])
        self.retryable = bool(retryable)
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "retryable": self.retryable,
            }
        }
