"""Frozen safety policy for Application Phase 01."""

from __future__ import annotations

from enum import Enum

CONTRACT_VERSION = "1.0"
QUERY_REGISTRY_VERSION = "1.0.0"
DEFAULT_QUERY_TIMEOUT_SECONDS = 5.0
MAX_QUERY_TIMEOUT_SECONDS = 10.0
DEFAULT_RESULT_LIMIT = 100
ABSOLUTE_RESULT_LIMIT = 1000
MAX_REQUEST_BODY_BYTES = 64 * 1024
MAX_RESPONSE_BODY_BYTES = 2 * 1024 * 1024
MAX_IRI_LENGTH = 2048
MAX_STRING_PARAMETER_LENGTH = 4096
LOCAL_BIND_HOST = "127.0.0.1"
ALLOWED_IRI_SCHEMES = frozenset({"https", "urn"})
PROJECT_HTTPS_PREFIX = "https://yangjunjie-lin.github.io/KG-MNP-Demo/"
PROJECT_URN_PREFIX = "urn:kg-mnp:"
EXTERNAL_ONTOLOGY_PREFIXES = (
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/2002/07/owl#",
    "http://www.w3.org/2004/02/skos/core#",
    "http://www.w3.org/ns/prov#",
    "http://purl.org/dc/terms/",
)


class QueryCategory(str, Enum):
    FOUNDATION_METADATA = "FOUNDATION_METADATA"
    ONTOLOGY = "ONTOLOGY"
    BUSINESS_FACT = "BUSINESS_FACT"
    PROVENANCE = "PROVENANCE"
    REVIEW_TRACE = "REVIEW_TRACE"
    SOURCE_TRACE = "SOURCE_TRACE"
    EVIDENCE_TRACE = "EVIDENCE_TRACE"
    CROSS_TRACE = "CROSS_TRACE"


class GraphRole(str, Enum):
    TBOX = "TBOX"
    BUSINESS_ABOX = "BUSINESS_ABOX"
    MODELING_PROVENANCE = "MODELING_PROVENANCE"
    REVIEW_AUDIT = "REVIEW_AUDIT"


GRAPH_ROLE_MARKERS = {
    GraphRole.TBOX: ":graph:tbox:",
    GraphRole.BUSINESS_ABOX: ":graph:abox:",
    GraphRole.MODELING_PROVENANCE: ":graph:modeling-provenance:",
    GraphRole.REVIEW_AUDIT: ":graph:review-audit:",
}


def graph_role_for_iri(iri: str) -> GraphRole | None:
    matches = [role for role, marker in GRAPH_ROLE_MARKERS.items() if marker in iri]
    return matches[0] if len(matches) == 1 else None
