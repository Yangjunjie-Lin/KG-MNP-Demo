"""Explicit new/legacy configuration compatibility without secret echo."""
from __future__ import annotations

import os
import warnings
from typing import overload


@overload
def get_setting(suffix: str, default: str) -> str: ...


@overload
def get_setting(suffix: str, default: None = None) -> str | None: ...


def get_setting(suffix: str, default: str | None = None) -> str | None:
    current, legacy = "ZHIGOU_" + suffix, "KG_MNP_" + suffix
    new, old = os.environ.get(current), os.environ.get(legacy)
    if new is not None and old is not None and new != old:
        raise ValueError(f"Conflicting configuration: {current} and {legacy}")
    if new is not None:
        return new
    if old is not None:
        warnings.warn(f"{legacy} is deprecated; use {current}", DeprecationWarning, stacklevel=2)
        return old
    return default
