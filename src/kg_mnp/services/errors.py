from __future__ import annotations


class ServiceBoundaryError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False, status_code: int = 400):
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message, "retryable": self.retryable, "details": []}}
