"""Stable error model retained for the legacy eligibility example."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    INVALID_QUERY_ID = "INVALID_QUERY_ID"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    INVALID_IRI = "INVALID_IRI"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    RESULT_LIMIT_EXCEEDED = "RESULT_LIMIT_EXCEEDED"
    FOUNDATION_NOT_VERIFIED = "FOUNDATION_NOT_VERIFIED"
    PUBLICATION_MISMATCH = "PUBLICATION_MISMATCH"
    GRAPHDB_UNAVAILABLE = "GRAPHDB_UNAVAILABLE"
    READ_ONLY_POLICY_VIOLATION = "READ_ONLY_POLICY_VIOLATION"
    INPUT_SCHEMA_ERROR = "INPUT_SCHEMA_ERROR"
    INPUT_GRAPH_INVALID = "INPUT_GRAPH_INVALID"
    RULE_CONFIGURATION_ERROR = "RULE_CONFIGURATION_ERROR"
    ASSESSMENT_GRAPH_INVALID = "ASSESSMENT_GRAPH_INVALID"
    TRACE_INTEGRITY_ERROR = "TRACE_INTEGRITY_ERROR"
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    EXECUTION_NOT_FOUND = "EXECUTION_NOT_FOUND"
    ONTOLOGY_TERM_NOT_FOUND = "ONTOLOGY_TERM_NOT_FOUND"
    RULE_NOT_FOUND = "RULE_NOT_FOUND"
    EXAMPLE_NOT_FOUND = "EXAMPLE_NOT_FOUND"
    QUERY_NOT_FOUND = "QUERY_NOT_FOUND"
    QUERY_EXECUTION_ERROR = "QUERY_EXECUTION_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    PROCESS_ERROR = "PROCESS_ERROR"
    PROCESS_ASSESSMENT_TIME_REQUIRED = "PROCESS_ASSESSMENT_TIME_REQUIRED"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_MESSAGES_ZH: dict[ErrorCode, str] = {
    ErrorCode.INVALID_QUERY_ID: "未知或未注册的查询标识。",
    ErrorCode.INVALID_PARAMETER: "查询参数无效。",
    ErrorCode.INVALID_IRI: "IRI 无效或不在允许的命名空间内。",
    ErrorCode.QUERY_TIMEOUT: "查询超过允许的执行时间。",
    ErrorCode.RESULT_LIMIT_EXCEEDED: "查询结果超过允许上限。",
    ErrorCode.FOUNDATION_NOT_VERIFIED: "Foundation 尚未通过验证。",
    ErrorCode.PUBLICATION_MISMATCH: "Publication 与 GraphDB lineage 不匹配。",
    ErrorCode.GRAPHDB_UNAVAILABLE: "GraphDB 只读服务不可用。",
    ErrorCode.READ_ONLY_POLICY_VIOLATION: "操作违反只读策略。",
    ErrorCode.INPUT_SCHEMA_ERROR: "输入数据不符合 Schema。",
    ErrorCode.INPUT_GRAPH_INVALID: "输入图未通过 SHACL 验证。",
    ErrorCode.RULE_CONFIGURATION_ERROR: "规则配置无效。",
    ErrorCode.ASSESSMENT_GRAPH_INVALID: "评估结果图未通过 SHACL 验证。",
    ErrorCode.TRACE_INTEGRITY_ERROR: "追溯子图与 RDF 图不一致。",
    ErrorCode.CASE_NOT_FOUND: "未找到指定案件。",
    ErrorCode.EXECUTION_NOT_FOUND: "未找到指定评估执行记录。",
    ErrorCode.ONTOLOGY_TERM_NOT_FOUND: "未找到指定本体术语。",
    ErrorCode.RULE_NOT_FOUND: "未找到指定规则。",
    ErrorCode.EXAMPLE_NOT_FOUND: "未找到指定示例案例。",
    ErrorCode.QUERY_NOT_FOUND: "未找到指定能力问题。",
    ErrorCode.QUERY_EXECUTION_ERROR: "能力问题查询执行失败。",
    ErrorCode.STORAGE_ERROR: "持久化存储不可用。",
    ErrorCode.PROCESS_ERROR: "流程评估失败。",
    ErrorCode.PROCESS_ASSESSMENT_TIME_REQUIRED: "流程评估必须提供 assessment_time。",
    ErrorCode.REQUEST_TOO_LARGE: "请求体超过大小限制。",
    ErrorCode.INTERNAL_ERROR: "内部错误。",
}


ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_QUERY_ID: 404,
    ErrorCode.INVALID_PARAMETER: 422,
    ErrorCode.INVALID_IRI: 422,
    ErrorCode.QUERY_TIMEOUT: 504,
    ErrorCode.RESULT_LIMIT_EXCEEDED: 413,
    ErrorCode.FOUNDATION_NOT_VERIFIED: 503,
    ErrorCode.PUBLICATION_MISMATCH: 503,
    ErrorCode.GRAPHDB_UNAVAILABLE: 503,
    ErrorCode.READ_ONLY_POLICY_VIOLATION: 405,
    ErrorCode.INPUT_SCHEMA_ERROR: 422,
    ErrorCode.INPUT_GRAPH_INVALID: 400,
    ErrorCode.RULE_CONFIGURATION_ERROR: 500,
    ErrorCode.ASSESSMENT_GRAPH_INVALID: 400,
    ErrorCode.TRACE_INTEGRITY_ERROR: 500,
    ErrorCode.CASE_NOT_FOUND: 404,
    ErrorCode.EXECUTION_NOT_FOUND: 404,
    ErrorCode.ONTOLOGY_TERM_NOT_FOUND: 404,
    ErrorCode.RULE_NOT_FOUND: 404,
    ErrorCode.EXAMPLE_NOT_FOUND: 404,
    ErrorCode.QUERY_NOT_FOUND: 404,
    ErrorCode.QUERY_EXECUTION_ERROR: 400,
    ErrorCode.STORAGE_ERROR: 503,
    ErrorCode.PROCESS_ERROR: 400,
    ErrorCode.PROCESS_ASSESSMENT_TIME_REQUIRED: 400,
    ErrorCode.REQUEST_TOO_LARGE: 413,
    ErrorCode.INTERNAL_ERROR: 500,
}


def http_status_for(code: ErrorCode) -> int:
    return ERROR_HTTP_STATUS.get(code, 500)


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

    @property
    def http_status(self) -> int:
        return http_status_for(self.code)
