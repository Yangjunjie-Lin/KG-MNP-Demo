"""Structural, semantic, RDF/SPARQL and filesystem Domain Pack validation."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import ValidationError
from pyparsing import ParseBaseException
from rdflib import Graph
from rdflib.namespace import OWL, RDF
from rdflib.plugins.sparql.parser import parseQuery

from kg_mnp.contracts.document_io import DocumentError, read_document
from kg_mnp.contracts.errors import ContractError, PathSecurityError
from kg_mnp.contracts.registry import validate_contract
from kg_mnp.contracts.validation import ValidationCheck, validation_report

from .locking import DomainPackLockError, verify_pack_lock
from .models import DomainPackManifest, DomainPackValidationResult
from .security import asset_path, is_executable_content, semantic_files

_CAPABILITY_BY_KIND = {
    "ontology-root": "ontology",
    "ontology-module": "ontology",
    "ontology-catalog": "ontology",
    "ontology-alignment": "ontology",
    "shacl-shapes": "shacl",
    "terminology": "terminology",
    "mapping-rules": "mappings",
    "domain-rules": "rules",
    "competency-questions": "competency-questions",
    "query": "queries",
    "fixture": "fixtures",
}
_RDF_MEDIA_TYPES = {
    "text/turtle": "turtle",
    "application/rdf+xml": "xml",
    "application/trig": "trig",
    "application/n-triples": "nt",
    "application/n-quads": "nquads",
}
_SPARQL_PLACEHOLDER = re.compile(r"@@(?:PARAM|GRAPH)_[A-Za-z0-9_-]+@@")


@lru_cache(maxsize=128)
def _rdf_syntax_facts(raw:bytes,format_name:str,base_uri:str)->tuple[frozenset[str],frozenset[str]]:
    """Only immutable parse facts are cached; paths, locks and verdicts are not."""
    graph=Graph()
    graph.parse(data=raw,format=format_name,publicID=base_uri)
    return frozenset(map(str,graph.subjects(RDF.type,OWL.Ontology))),frozenset(map(str,graph.objects(None,OWL.imports)))


@lru_cache(maxsize=128)
def _query_syntax_kind(raw:bytes)->str:
    query=raw.decode("utf8")
    query=_SPARQL_PLACEHOLDER.sub("<urn:kg-mnp:query-placeholder>",query).replace("@@LIMIT@@","1").replace("@@OFFSET@@","0")
    return parseQuery(query)[1].name


def load_domain_pack_manifest(pack_root: Path | str) -> DomainPackManifest:
    root = Path(pack_root).resolve(strict=True)
    path = root / "pack.yaml"
    value = read_document(path)
    if not isinstance(value, dict):
        raise DocumentError("Domain Pack manifest root must be an object")
    validate_contract("domain-pack-manifest", value)
    return DomainPackManifest(document=value, path=path)


def _error(
    code: str,
    path: str,
    message: str,
) -> ValidationCheck:
    return ValidationCheck(
        code=code,
        severity="ERROR",
        path=path,
        message=message,
        contract_name="domain-pack-manifest",
    )


def _validate_asset_content(
    pack_root: Path,
    asset: dict[str, Any],
    ontology_iris: set[str],
) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    relative = asset["path"]
    try:
        path = asset_path(pack_root, relative)
        if not path.is_file():
            return [_error("ASSET_NOT_REGULAR_FILE", relative, "asset is not a regular file")]
        if is_executable_content(path):
            return [_error("EXECUTABLE_CONTENT", relative, "executable Pack content is forbidden")]
        media_type = asset["media_type"]
        if media_type in _RDF_MEDIA_TYPES:
            declared_ontologies,imports=_rdf_syntax_facts(path.read_bytes(),_RDF_MEDIA_TYPES[media_type],path.resolve().as_uri())
            declared = asset.get("ontology_iri")
            if declared and declared not in declared_ontologies:
                checks.append(
                    _error(
                        "ONTOLOGY_IRI_MISMATCH",
                        relative,
                        f"declared ontology_iri is not an owl:Ontology: {declared}",
                    )
                )
            for imported in imports:
                if imported not in ontology_iris:
                    checks.append(
                        _error(
                            "UNRESOLVED_ONTOLOGY_IMPORT",
                            relative,
                            f"owl:imports is not declared in this Pack: {imported}",
                        )
                    )
        elif media_type == "application/sparql-query":
            _query_syntax_kind(path.read_bytes())
        elif media_type in {"application/json", "application/schema+json", "application/yaml"}:
            read_document(path)
        elif media_type == "application/xml":
            ET.parse(path)
    except (DocumentError, PathSecurityError) as exc:
        checks.append(_error("ASSET_SECURITY_VIOLATION", relative, str(exc)))
    except (
        OSError,
        UnicodeError,
        ValueError,
        SyntaxError,
        ET.ParseError,
        ParseBaseException,
    ) as exc:
        checks.append(_error("ASSET_PARSE_FAILED", relative, str(exc)))
    return checks


def validate_domain_pack(
    pack_root: Path | str,
    *,
    verify_lock: bool = True,
    strict: bool = True,
) -> DomainPackValidationResult:
    root = Path(pack_root)
    checks: list[ValidationCheck] = []
    manifest: DomainPackManifest | None = None
    try:
        manifest = load_domain_pack_manifest(root)
    except ValidationError as exc:
        path = "$" + "".join(f"/{item}" for item in exc.absolute_path)
        checks.append(_error("MANIFEST_SCHEMA_INVALID", path, exc.message))
    except (OSError, ContractError) as exc:
        checks.append(_error("MANIFEST_UNREADABLE", "$", str(exc)))
    if manifest is None:
        return DomainPackValidationResult(
            validation_report(
                validator="kg-mnp-domain-pack",
                subject=root.name or "domain-pack",
                contract_name="domain-pack-manifest",
                checks=checks,
            )
        )

    document = manifest.document
    if document["pack_id"] != manifest.path.parent.name:
        checks.append(
            _error(
                "PACK_ID_DIRECTORY_MISMATCH",
                "$/pack_id",
                "pack_id must equal the local Pack directory name",
            )
        )
    capabilities = document["capabilities"]
    if capabilities != sorted(capabilities):
        checks.append(_error("NONDETERMINISTIC_ORDER", "$/capabilities", "capabilities must be sorted"))
    assets = document["assets"]
    asset_ids = [item["asset_id"] for item in assets]
    asset_paths = [item["path"] for item in assets]
    if len(asset_ids) != len(set(asset_ids)):
        checks.append(_error("DUPLICATE_ASSET_ID", "$/assets", "asset_id values must be unique"))
    if len(asset_paths) != len(set(asset_paths)):
        checks.append(_error("DUPLICATE_ASSET_PATH", "$/assets", "asset paths must be unique"))
    if asset_ids != sorted(asset_ids):
        checks.append(_error("NONDETERMINISTIC_ORDER", "$/assets", "assets must be sorted by asset_id"))
    dependencies = document["dependencies"]
    if dependencies != sorted(dependencies, key=lambda item: (item["pack_id"], item["pack_version"])):
        checks.append(_error("NONDETERMINISTIC_ORDER", "$/dependencies", "dependencies must be sorted"))
    dependency_keys = [(item["pack_id"], item["pack_version"]) for item in dependencies]
    if len(dependency_keys) != len(set(dependency_keys)):
        checks.append(_error("DUPLICATE_DEPENDENCY", "$/dependencies", "dependencies must be unique"))
    lifecycle = document["lifecycle"]
    formal_capabilities = set(capabilities)
    if lifecycle == "PLANNED" and (formal_capabilities or assets):
        checks.append(
            _error("PLANNED_CAPABILITY_CLAIM", "$/lifecycle", "PLANNED packs cannot claim implemented assets or capabilities")
        )
    if lifecycle in {"EXPERIMENTAL", "MIGRATED_BASELINE", "STABLE"} and not assets:
        checks.append(_error("LIFECYCLE_ASSET_REQUIRED", "$/assets", f"{lifecycle} requires at least one asset"))
    if lifecycle == "STABLE" and not document["license"]["expression"]:
        checks.append(_error("STABLE_LICENSE_REQUIRED", "$/license", "STABLE packs require a license expression"))

    expected_capabilities = {
        _CAPABILITY_BY_KIND[item["kind"]]
        for item in assets
        if item["kind"] in _CAPABILITY_BY_KIND
    }
    missing = sorted(expected_capabilities - formal_capabilities)
    unsupported = sorted(formal_capabilities - expected_capabilities)
    if missing:
        checks.append(_error("ASSET_WITHOUT_CAPABILITY", "$/capabilities", f"missing capabilities: {', '.join(missing)}"))
    if unsupported:
        checks.append(_error("CAPABILITY_WITHOUT_ASSET", "$/capabilities", f"capabilities lack assets: {', '.join(unsupported)}"))
    known_assets = set(asset_ids)
    for name, asset_id in document["entrypoints"].items():
        if asset_id not in known_assets:
            checks.append(_error("DANGLING_ENTRYPOINT", f"$/entrypoints/{name}", f"unknown asset_id: {asset_id}"))

    ontology_iris = {
        item["ontology_iri"] for item in assets if "ontology_iri" in item
    }
    for asset in assets:
        checks.extend(_validate_asset_content(manifest.path.parent, asset, ontology_iris))
    try:
        declared_files = set(asset_paths)
        shadow_files = sorted(set(semantic_files(manifest.path.parent)) - declared_files)
        if strict and shadow_files:
            checks.append(
                _error(
                    "UNDECLARED_SEMANTIC_FILE",
                    "$",
                    "undeclared semantic files: " + ", ".join(shadow_files),
                )
            )
    except PathSecurityError as exc:
        checks.append(_error("PACK_FILESYSTEM_VIOLATION", "$", str(exc)))
    if verify_lock:
        try:
            verify_pack_lock(manifest)
        except (DomainPackLockError, ValidationError, DocumentError) as exc:
            checks.append(_error("DOMAIN_PACK_LOCK_MISMATCH", "pack.lock.json", str(exc)))

    report = validation_report(
        validator="kg-mnp-domain-pack",
        subject=manifest.pack_id,
        contract_name="domain-pack-manifest",
        checks=checks,
    )
    return DomainPackValidationResult(report=report, manifest=manifest)


def require_valid_domain_pack(
    pack_root: Path | str,
    *,
    verify_lock: bool = True,
) -> DomainPackManifest:
    result = validate_domain_pack(pack_root, verify_lock=verify_lock)
    if not result.valid or result.manifest is None:
        messages = "; ".join(item["message"] for item in result.report["checks"])
        raise ContractError(f"invalid Domain Pack: {messages}")
    return result.manifest
