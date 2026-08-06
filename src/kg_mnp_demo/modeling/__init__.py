"""Modeling contracts, proposal generation, human review, and confirmation."""

from .confirmation import build_confirmed_modeling_package
from .proposal import GENERATOR_VERSION, generate_modeling_proposal

__all__ = [
    "GENERATOR_VERSION",
    "build_confirmed_modeling_package",
    "generate_modeling_proposal",
]

