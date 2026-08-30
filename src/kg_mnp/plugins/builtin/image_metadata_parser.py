"""Bounded image metadata parser; deliberately no OCR or vision semantics."""

from io import BytesIO

from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import ParsedUnit, ParseRequest


class ImageMetadataParser:
    def parse(self, request: ParseRequest) -> tuple[ParsedUnit, ...]:
        try:
            from PIL import Image, UnidentifiedImageError
        except ImportError as exc:
            raise PluginError("MISSING_DEPENDENCY: Pillow") from exc
        try:
            with Image.open(BytesIO(request.content)) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > request.limits.max_image_pixels:
                    raise PluginError("IMAGE_PIXEL_LIMIT_EXCEEDED")
                entries = (
                    ("format", image.format or "UNKNOWN"),
                    ("width", width),
                    ("height", height),
                    ("mode", image.mode),
                )
        except (UnidentifiedImageError, OSError) as exc:
            raise PluginError(f"invalid image: {exc}") from exc
        return (
            ParsedUnit(
                "image-metadata",
                None,
                {
                    "locator_kind": "image-region",
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": height,
                },
                request.media_type,
                0,
                entries,
                ("MISSING_OCR_OR_VISION_PROVIDER",),
            ),
        )
