from pydantic import BaseModel, Field
from typing import Any


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[Any] = Field(default_factory=list)
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorBody
