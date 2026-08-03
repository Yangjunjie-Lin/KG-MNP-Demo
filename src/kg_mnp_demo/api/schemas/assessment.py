from typing import Any

from pydantic import BaseModel, Field


class AssessmentCreateRequest(BaseModel):
    payload: dict[str, Any]
    persist: bool = True
    force_recompute: bool = False


class WhatIfRequest(BaseModel):
    changes: dict[str, Any] = Field(default_factory=dict)
