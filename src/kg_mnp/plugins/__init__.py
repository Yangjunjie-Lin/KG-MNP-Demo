"""KG-MNP Plugin SDK v1 and metadata-first provider registry."""

from .api import (
    MediaDetectorPlugin,
    NormalizerPlugin,
    ParserPlugin,
    QualityEvaluatorPlugin,
    SourceAdapterPlugin,
)
from .models import (
    MediaDetection,
    NormalizedUnit,
    ParsedUnit,
    PluginDescriptor,
    PluginStatus,
)
from .registry import PluginRegistry

PLUGIN_API_VERSION = "1.0.0"
ENTRY_POINT_GROUP = "kg_mnp.plugins"

__all__ = [
    "ENTRY_POINT_GROUP",
    "PLUGIN_API_VERSION",
    "MediaDetection",
    "MediaDetectorPlugin",
    "NormalizedUnit",
    "NormalizerPlugin",
    "ParsedUnit",
    "ParserPlugin",
    "PluginDescriptor",
    "PluginRegistry",
    "PluginStatus",
    "QualityEvaluatorPlugin",
    "SourceAdapterPlugin",
]
