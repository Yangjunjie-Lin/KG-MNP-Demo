"""Stable public errors for the Contract Kernel."""

from __future__ import annotations


class ContractError(RuntimeError):
    """Base class for public contract failures."""


class ContractCatalogError(ContractError):
    """The authoritative catalog or its lock is inconsistent."""


class ContractRegistryError(ContractError):
    """A schema set is missing, invalid, cyclic, or not locally resolvable."""


class UnknownContractError(ContractError, KeyError):
    """A requested contract is not present in the authoritative catalog."""


class DocumentError(ContractError):
    """A JSON/YAML document cannot be read safely."""


class DocumentTooLargeError(DocumentError):
    """A document exceeds the configured byte limit."""


class DuplicateKeyError(DocumentError):
    """A JSON/YAML mapping contains a duplicate key."""


class PathSecurityError(ContractError, ValueError):
    """A supplied relative path is unsafe or escapes its authority root."""

