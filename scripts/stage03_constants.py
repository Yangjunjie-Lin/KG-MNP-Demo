"""Shared Stage 03 ontology release constants."""

from __future__ import annotations

OLD_TERM_NS = "http://example.org/kg-mnp#"
OLD_MODULE_BASE = "http://example.org/kg-mnp/"

TERM_NS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"
ONT_BASE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/"
SHAPE_NS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#"
DATA_NS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/"
EVIDENCE_NS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/evidence/"
MAPPING_NS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/mapping/"
REVIEW_NS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/review/"

ONTOLOGY_VERSION = "1.0.0"
LICENSE_IRI = "https://www.apache.org/licenses/LICENSE-2.0"

# Module code -> file stem / IRI local name
MODULE_FILES = {
    "CORE": "mnp-core",
    "IDENTITY": "mnp-identity",
    "ACCOUNT_BILLING": "mnp-account-billing",
    "SERVICE_CONTRACT": "mnp-service-contract",
    "PROCESS": "mnp-process",
    "COMPLIANCE": "mnp-compliance",
    "EVIDENCE_TIME": "mnp-evidence-time",
    "MODELING_PROVENANCE": "mnp-modeling-provenance",
    "CODE_LIST": "mnp-code-list",
    "ALIGNMENTS": "mnp-alignments",
    "ROOT": "kg-mnp",
}

RUNTIME_MODULES = [
    "mnp-core",
    "mnp-identity",
    "mnp-account-billing",
    "mnp-service-contract",
    "mnp-process",
    "mnp-compliance",
    "mnp-evidence-time",
    "mnp-modeling-provenance",
    "mnp-code-list",
]

OPTIONAL_MODULES = ["mnp-alignments"]


def ontology_iri(module: str) -> str:
    return f"{ONT_BASE}{module}"


def version_iri(module: str, version: str = ONTOLOGY_VERSION) -> str:
    return f"{ONT_BASE}{version}/{module}"


def term_iri(local: str) -> str:
    return f"{TERM_NS}{local}"


def old_term_iri(local: str) -> str:
    return f"{OLD_TERM_NS}{local}"


def shape_iri(local: str) -> str:
    return f"{SHAPE_NS}{local}"
