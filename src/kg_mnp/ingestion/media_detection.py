"""Core-owned invocation of the deterministic signature media detector."""

from kg_mnp.plugins.builtin.media_detector import SignatureMediaDetector
from kg_mnp.plugins.models import MediaDetection, MediaDetectionRequest, ResourceLimits


def detect_media_type(
    content: bytes,
    original_name: str,
    *,
    declared_media_type: str | None = None,
    limits: ResourceLimits | None = None,
) -> MediaDetection:
    return SignatureMediaDetector().detect(
        MediaDetectionRequest(
            content=content,
            original_name=original_name,
            declared_media_type=declared_media_type,
            limits=limits or ResourceLimits(),
        )
    )
