"""Shared Term dataclass for Stage 03 catalog."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Term:
    local: str
    term_type: str
    module: str
    label_en: str
    label_zh: str
    definition_en: str
    definition_zh: str
    superclass: str = ""
    domain: str = ""
    range: str = ""
    inverse: str = ""
    characteristics: str = ""
    deprecated: bool = False
    replacement: str = ""
    source: str = "LOCAL_EXTENSION"
    source_status: str = "LOCAL_EXTENSION"
    audit_decision: str = "ACCEPT"
    audit_notes: str = ""
    disjoint_with: list[str] = field(default_factory=list)
    code_list_name: str = ""
    code_value: str = ""
    code_label_en: str = ""
    code_label_zh: str = ""


def T(**kwargs) -> Term:
    return Term(**kwargs)
