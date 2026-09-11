"""Runtime-checkable Plugin SDK v1 protocols.

Plugins receive immutable, bounded request values. No Workspace or artifact
writer is exposed, and responses have no authoritative Evidence/KG-IR IDs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import (
    MediaDetection,
    MediaDetectionRequest,
    NormalizedUnit,
    NormalizeRequest,
    ParsedUnit,
    ParseRequest,
    QualityEvaluationRequest,
    QualityEvaluationResult,
    SourceReadRequest,
    SourceReadResult,
)


@runtime_checkable
class SourceAdapterPlugin(Protocol):
    def read(self, request: SourceReadRequest) -> SourceReadResult: ...


@runtime_checkable
class MediaDetectorPlugin(Protocol):
    def detect(self, request: MediaDetectionRequest) -> MediaDetection: ...


@runtime_checkable
class ParserPlugin(Protocol):
    def parse(self, request: ParseRequest) -> tuple[ParsedUnit, ...]: ...


@runtime_checkable
class NormalizerPlugin(Protocol):
    def normalize(self, request: NormalizeRequest) -> NormalizedUnit: ...


@runtime_checkable
class QualityEvaluatorPlugin(Protocol):
    def evaluate(self, request: QualityEvaluationRequest) -> QualityEvaluationResult: ...
