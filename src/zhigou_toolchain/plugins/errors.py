"""Fail-closed Plugin SDK exceptions."""


class PluginError(RuntimeError):
    """Base Plugin SDK error."""


class PluginManifestError(PluginError):
    """A manifest is invalid, incompatible, or unsafe."""


class PluginUnavailableError(PluginError):
    """A provider is not enabled or has an unmet requirement."""


class PluginTamperedError(PluginError):
    """A manifest or implementation differs from its snapshot."""


class ProviderSelectionError(PluginError):
    """No policy-compliant provider can be selected."""


class AmbiguousProviderSelectionError(ProviderSelectionError):
    """More than one highest-priority equivalent provider is eligible."""


class PluginConformanceError(PluginError):
    """A provider violates Plugin SDK request/response constraints."""
