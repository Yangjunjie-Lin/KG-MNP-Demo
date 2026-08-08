from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping
from math import isfinite
from typing import Any

from .policy import load_webvowl_policy


class WebVOWLVerificationError(ValueError):
    pass


_PROJECT_RUNTIME_IRI = re.compile(r"urn:kg-mnp:[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+")
_MODELED_DATA_IRI = re.compile(
    r"https://yangjunjie-lin\.github\.io/KG-MNP-Demo/data/modeled/"
    r"[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+"
)
_GRAPHDB_REPOSITORY_ID = re.compile(
    r"(?<![A-Za-z0-9_-])kg-mnp-[0-9a-f]{20}(?![0-9a-f])"
)
_ABOX_METADATA_KEYS = {
    "graphdbrepositoryid",
    "individual",
    "individuals",
    "publicationid",
    "repositoryid",
    "runtimeattestation",
    "shaclvalidationresult",
    "validationresult",
}
_REVIEW_PROVENANCE_KEYS = {
    "provenance",
    "provenanceassertion",
    "provenancerecord",
    "reviewdecision",
    "reviewdecisionlog",
    "reviewevidence",
    "reviewrecord",
    "reviewer",
    "reviewsession",
    "sourcefield",
    "sourcerecord",
}
_REVIEW_PROVENANCE_PREFIXES = (
    "urn:kg-mnp:candidate:",
    "urn:kg-mnp:compiled-assertion:",
    "urn:kg-mnp:confirmed-item:",
    "urn:kg-mnp:confirmed-modeling-package:",
    "urn:kg-mnp:graph:modeling-provenance:",
    "urn:kg-mnp:graph:review-audit:",
    "urn:kg-mnp:issue:",
    "urn:kg-mnp:mapping-rule:",
    "urn:kg-mnp:modeling-evidence:",
    "urn:kg-mnp:modeling-proposal:",
    "urn:kg-mnp:review-",
    "urn:kg-mnp:reviewer:",
    "urn:kg-mnp:source-field:",
    "urn:kg-mnp:source-record:",
)


def tbox_equivalence(
    *, stage03_semantic_hash: str, graphdb_semantic_hash: str
) -> dict[str, Any]:
    equal = stage03_semantic_hash == graphdb_semantic_hash
    report = {
        "status": "PASS" if equal else "FAILED",
        "stage03_tbox_semantic_hash": stage03_semantic_hash,
        "graphdb_tbox_semantic_hash": graphdb_semantic_hash,
        "equal": equal,
    }
    if not equal:
        raise WebVOWLVerificationError(
            "GraphDB TBox semantic hash differs from Stage 03 source"
        )
    return report


def scan_vowl_leakage(
    vowl: Mapping[str, Any], forbidden_terms: Iterable[str] = ()
) -> dict[str, Any]:
    """Scan every JSON key and scalar value for non-TBox runtime content."""

    def walk(value: Any) -> Iterator[tuple[str, str]]:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise WebVOWLVerificationError(
                        "VOWL leakage scan requires text JSON keys"
                    )
                yield "key", key
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)
        elif isinstance(value, str):
            yield "value", value
        elif (
            value is None
            or isinstance(value, (bool, int))
            or isinstance(value, float)
            and isfinite(value)
        ):
            return
        else:
            raise WebVOWLVerificationError(
                "VOWL leakage scan received a non-JSON value"
            )

    try:
        text = json.dumps(
            vowl,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise WebVOWLVerificationError(
            f"VOWL leakage scan received invalid JSON: {exc}"
        ) from exc

    hits: set[str] = set()
    review_provenance_hits: set[str] = set()

    def review_or_provenance(value: str) -> bool:
        lowered = value.lower()
        return lowered.startswith(_REVIEW_PROVENANCE_PREFIXES) or any(
            marker in lowered
            for marker in (
                "reviewdecision",
                "review_decision",
                "review-decision",
                "reviewsession",
                "review_session",
                "review-session",
                "reviewer",
                "provenance",
                "source-record",
                "source_record",
            )
        )

    for kind, value in walk(vowl):
        if kind == "key":
            normalized_key = re.sub(r"[^a-z0-9]", "", value.lower())
            if normalized_key in _ABOX_METADATA_KEYS:
                hits.add(value)
            if normalized_key in _REVIEW_PROVENANCE_KEYS:
                hits.add(value)
                review_provenance_hits.add(value)
        for pattern in (
            _PROJECT_RUNTIME_IRI,
            _MODELED_DATA_IRI,
            _GRAPHDB_REPOSITORY_ID,
        ):
            for match in pattern.finditer(value):
                hit = match.group(0)
                hits.add(hit)
                if review_or_provenance(hit):
                    review_provenance_hits.add(hit)

    for term in forbidden_terms:
        if not isinstance(term, str):
            raise WebVOWLVerificationError("forbidden VOWL term must be text")
        if term and term in text:
            hits.add(term)
            if review_or_provenance(term):
                review_provenance_hits.add(term)
    return {
        "status": "PASS" if not hits else "FAILED",
        "hits": sorted(hits),
        "review_provenance_hits": sorted(review_provenance_hits),
    }


def validate_runtime_policy(
    *, policy: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    value = dict(policy or load_webvowl_policy())
    network = value["network"]
    if (
        network["bind_host"] != "127.0.0.1"
        or network["external_exposure"] != "FORBIDDEN"
        or network["runtime_internet_access"] != "FORBIDDEN"
    ):
        raise WebVOWLVerificationError("runtime network boundary violated")
    return {
        "status": "PASS",
        "bind_host": network["bind_host"],
        "port": network["port"],
        "external_network": "BLOCKED",
    }


def build_determinism_report(
    run1: Mapping[str, Any], run2: Mapping[str, Any]
) -> dict[str, Any]:
    import hashlib

    b1 = json.dumps(
        run1, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    b2 = json.dumps(
        run2, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return {
        "contract_version": "1.0",
        "run_1_sha256": hashlib.sha256(b1).hexdigest(),
        "run_2_sha256": hashlib.sha256(b2).hexdigest(),
        "sha256_differences": [] if b1 == b2 else ["normalized_vowl"],
    }
