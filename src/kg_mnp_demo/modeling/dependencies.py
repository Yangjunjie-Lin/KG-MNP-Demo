"""Frozen, offline Stage 04 modeling dependencies.

The ontology baseline is an auditable view of the formal Stage 03 release.  It
does not copy ontology axioms and it never writes ontology assets.  Release and
semantic hashes are delegated to ``scripts/run_reasoner.py`` so Stage 04 cannot
quietly acquire a second definition of the Stage 03 release boundary.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

import yaml

from .canonical_json import semantic_hash


ROOT = Path(__file__).resolve().parents[3]
MODELING_CONFIG_DIR = ROOT / "config" / "modeling"
ONTOLOGY_BASELINE_PATH = MODELING_CONFIG_DIR / "ontology-baseline-1.0.0.json"
MAPPING_RULES_PATH = MODELING_CONFIG_DIR / "mapping-rules-1.0.0.yaml"
TERMINOLOGY_PROFILE_PATH = MODELING_CONFIG_DIR / "terminology-profile-1.0.0.yaml"
PROPOSAL_POLICY_PATH = MODELING_CONFIG_DIR / "proposal-policy-1.0.0.yaml"
REVIEW_POLICY_PATH = MODELING_CONFIG_DIR / "review-policy-1.0.0.yaml"
TERM_INVENTORY_PATH = ROOT / "docs" / "ontology" / "term-inventory.csv"
REASONER_ATTESTATION_PATH = (
    ROOT / "docs" / "ontology" / "reasoner-attestation.json"
)

BASELINE_ID = "kg-mnp-ontology-baseline"
BASELINE_MANIFEST_VERSION = "1.0"


class DependencyError(ValueError):
    """A frozen dependency is missing, malformed, stale, or incompatible."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DependencyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def normalize_lf_bytes(data: bytes) -> bytes:
    """Return bytes with CRLF and lone CR line endings normalized to LF."""

    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def normalized_file_hash(path: Path) -> str:
    """SHA-256 of a file after portable LF normalization."""

    import hashlib

    return hashlib.sha256(normalize_lf_bytes(path.read_bytes())).hexdigest()


# A concise alias used by callers that construct dependency snapshots.
dependency_file_hash = normalized_file_hash


def dependency_document_hash(document: Mapping[str, Any]) -> str:
    """Hash a parsed dependency by its canonical JSON semantic form."""

    return semantic_hash(document)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DependencyError(f"cannot read JSON dependency {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DependencyError(f"dependency root must be an object: {path}")
    return value


def _read_yaml_object(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(
            path.read_text(encoding="utf-8"),
            Loader=_UniqueKeyLoader,
        )
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise DependencyError(f"cannot read YAML dependency {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DependencyError(f"dependency root must be an object: {path}")
    return value


def load_ontology_baseline(path: Path = ONTOLOGY_BASELINE_PATH) -> dict[str, Any]:
    return _read_json_object(path)


def load_mapping_rules(path: Path = MAPPING_RULES_PATH) -> dict[str, Any]:
    return _read_yaml_object(path)


def load_terminology_profile(
    path: Path = TERMINOLOGY_PROFILE_PATH,
) -> dict[str, Any]:
    return _read_yaml_object(path)


def load_proposal_policy(path: Path = PROPOSAL_POLICY_PATH) -> dict[str, Any]:
    return _read_yaml_object(path)


def load_review_policy_document(path: Path = REVIEW_POLICY_PATH) -> dict[str, Any]:
    return _read_yaml_object(path)


def validate_modeling_evidence_references(
    mapping_rules: Mapping[str, Any],
    *,
    root: Path = ROOT,
) -> None:
    """Resolve every rule-level modeling evidence reference locally."""

    errors: list[str] = []
    root = root.resolve()
    for rule in mapping_rules.get("rules", []):
        for reference in rule.get("modeling_evidence_refs", []):
            path_text, separator, fragment = reference.partition("#")
            pure_path = PurePosixPath(path_text)
            if (
                not path_text
                or pure_path.is_absolute()
                or ".." in pure_path.parts
                or "\\" in path_text
            ):
                errors.append(f"unsafe modeling evidence reference: {reference}")
                continue
            path = (root / Path(*pure_path.parts)).resolve()
            if root not in path.parents or not path.is_file():
                errors.append(f"missing modeling evidence resource: {reference}")
                continue
            if not separator:
                continue
            try:
                if path.suffix.lower() in {".yaml", ".yml"}:
                    document = _read_yaml_object(path)
                    identifiers = {
                        str(item.get("id"))
                        for item in document.get("mappings", [])
                        if isinstance(item, Mapping) and item.get("id") is not None
                    }
                    resolved = fragment in identifiers
                elif path.suffix.lower() == ".csv":
                    with path.open("r", encoding="utf-8", newline="") as stream:
                        rows = list(csv.DictReader(stream))
                    resolved = any(
                        fragment
                        in {
                            row.get("local_name", ""),
                            row.get("term_iri", "").rsplit("#", 1)[-1],
                        }
                        for row in rows
                    )
                else:
                    resolved = fragment in path.read_text(encoding="utf-8")
            except (OSError, UnicodeError, csv.Error, DependencyError) as exc:
                errors.append(f"cannot resolve modeling evidence {reference}: {exc}")
                continue
            if not resolved:
                errors.append(f"unknown modeling evidence fragment: {reference}")
    if errors:
        raise DependencyError("; ".join(errors))


def load_term_inventory_iris(
    path: Path = TERM_INVENTORY_PATH,
) -> frozenset[str]:
    """Load the authoritative Stage 03 inventory without ontology inference."""

    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DependencyError(f"cannot read term inventory {path}: {exc}") from exc
    if not rows or not {"term_iri", "term_type"} <= set(rows[0]):
        raise DependencyError(f"term inventory has no term_iri/term_type columns: {path}")
    # Ontology document resources are inventoried for release auditability but
    # are not terms that mapping rules or terminology aliases may target.
    iris = [
        row.get("term_iri", "").strip()
        for row in rows
        if row.get("term_type") != "Ontology"
    ]
    if any(not iri for iri in iris):
        raise DependencyError(f"term inventory contains an empty term_iri: {path}")
    if len(iris) != len(set(iris)):
        raise DependencyError(f"term inventory contains duplicate term_iri values: {path}")
    return frozenset(iris)


@lru_cache(maxsize=1)
def _stage03_reasoner() -> ModuleType:
    """Load the Stage 03 implementation from its authoritative script."""

    path = ROOT / "scripts" / "run_reasoner.py"
    module_name = "_kg_mnp_stage03_run_reasoner"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise DependencyError(f"cannot load Stage 03 hash implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise DependencyError(f"manifest source is outside repository root: {path}") from exc


def _module_record(
    root: Path,
    entry: Mapping[str, Any],
    *,
    included_in_reasoner_input: bool,
) -> dict[str, Any]:
    required = ("code", "file", "ontology_iri", "version_iri")
    missing = [field for field in required if not isinstance(entry.get(field), str)]
    if missing:
        raise DependencyError(
            "ontology module entry is missing string field(s): " + ", ".join(missing)
        )
    source = root / "ontology" / str(entry["file"])
    if not source.is_file():
        raise DependencyError(f"ontology module source is missing: {source}")
    return {
        "code": entry["code"],
        "file": _relative(root, source),
        "ontology_iri": entry["ontology_iri"],
        "version_iri": entry["version_iri"],
        "source_hash": normalized_file_hash(source),
        "included_in_reasoner_input": included_in_reasoner_input,
    }


def _manifest_source_paths(root: Path, reasoner: ModuleType) -> list[Path]:
    paths = set(reasoner.release_source_files(root, include_alignments=True))
    paths.update(
        {
            root / "docs" / "ontology" / "reasoner-attestation.json",
            root / "docs" / "ontology" / "term-inventory.csv",
        }
    )
    missing = sorted(path for path in paths if not path.is_file())
    if missing:
        raise DependencyError(f"baseline source is missing: {_relative(root, missing[0])}")
    return sorted(paths, key=lambda path: _relative(root, path))


def _validate_stage03_attestation(
    root: Path,
    reasoner: ModuleType,
    module_config: Mapping[str, Any],
    attestation: Mapping[str, Any],
    *,
    release_source_hash: str,
    reasoner_semantic_hash: str,
) -> None:
    root_config = module_config.get("root")
    if not isinstance(root_config, Mapping):
        raise DependencyError("ontology module configuration has no root object")
    expected_sources = [
        _relative(root, path)
        for path in reasoner.release_source_files(
            root,
            include_alignments=False,
        )
    ]
    expected = {
        "status": "PASS",
        "ontology_version": module_config.get("ontology_version"),
        "root_ontology_iri": root_config.get("ontology_iri"),
        "release_source_hash": release_source_hash,
        "reasoner_input_semantic_hash": reasoner_semantic_hash,
        "release_source_includes_optional_alignments": False,
        "release_source_files": expected_sources,
    }
    differences = [
        f"{field}: expected {value!r}, got {attestation.get(field)!r}"
        for field, value in expected.items()
        if attestation.get(field) != value
    ]
    if differences:
        raise DependencyError(
            "Stage 03 reasoner attestation is stale or non-passing: "
            + "; ".join(differences)
        )


def build_ontology_baseline_manifest(
    root: Path = ROOT,
) -> dict[str, Any]:
    """Build the deterministic baseline manifest entirely from local assets."""

    root = root.resolve()
    reasoner = _stage03_reasoner()
    module_config_path = root / "config" / "ontology_modules.yaml"
    attestation_path = root / "docs" / "ontology" / "reasoner-attestation.json"
    inventory_path = root / "docs" / "ontology" / "term-inventory.csv"
    module_config = _read_yaml_object(module_config_path)
    attestation = _read_json_object(attestation_path)
    root_config = module_config.get("root")
    modules = module_config.get("modules")
    if not isinstance(root_config, Mapping) or not isinstance(modules, list):
        raise DependencyError("invalid config/ontology_modules.yaml structure")

    for entry in modules:
        if not isinstance(entry, Mapping):
            raise DependencyError("ontology module entries must be objects")
        if not isinstance(entry.get("runtime"), bool) or not isinstance(
            entry.get("optional"), bool
        ):
            raise DependencyError(
                "ontology module runtime and optional flags must be YAML booleans"
            )
        if entry["runtime"] == entry["optional"]:
            raise DependencyError(
                "each ontology module must be exactly one of runtime or optional"
            )

    release_hash = reasoner.ontology_release_source_hash(
        root,
        include_alignments=False,
    )
    reasoner_graph = reasoner.asserted_reasoner_graph(root)
    semantic_input_hash = reasoner.reasoner_input_semantic_hash(reasoner_graph)
    _validate_stage03_attestation(
        root,
        reasoner,
        module_config,
        attestation,
        release_source_hash=release_hash,
        reasoner_semantic_hash=semantic_input_hash,
    )

    runtime_entries = [
        entry
        for entry in modules
        if isinstance(entry, Mapping) and entry.get("runtime") is True
    ]
    optional_entries = [
        entry
        for entry in modules
        if isinstance(entry, Mapping) and entry.get("optional") is True
    ]
    if len(runtime_entries) + len(optional_entries) != len(modules):
        raise DependencyError(
            "every ontology module must be explicitly runtime or optional"
        )

    generated_from = [
        {
            "path": _relative(root, path),
            "sha256": normalized_file_hash(path),
        }
        for path in _manifest_source_paths(root, reasoner)
    ]
    manifest = {
        "manifest_version": BASELINE_MANIFEST_VERSION,
        "baseline_id": BASELINE_ID,
        "ontology_version": module_config.get("ontology_version"),
        "root_ontology_iri": root_config.get("ontology_iri"),
        "root_version_iri": root_config.get("version_iri"),
        "release_source_hash": release_hash,
        "release_source_includes_optional_alignments": False,
        "reasoner_input_semantic_hash": semantic_input_hash,
        "reasoner_attestation_hash": normalized_file_hash(attestation_path),
        "term_inventory_hash": normalized_file_hash(inventory_path),
        "ontology_module_config_hash": normalized_file_hash(module_config_path),
        "runtime_modules": [
            _module_record(
                root,
                entry,
                included_in_reasoner_input=True,
            )
            for entry in runtime_entries
        ],
        "optional_modules": [
            _module_record(
                root,
                entry,
                included_in_reasoner_input=False,
            )
            for entry in optional_entries
        ],
        "generated_from": generated_from,
    }
    if not all(isinstance(manifest[field], str) and manifest[field] for field in (
        "ontology_version",
        "root_ontology_iri",
        "root_version_iri",
    )):
        raise DependencyError("ontology root/version identifiers are incomplete")
    return manifest


# Short aliases make the script and tests pleasant without obscuring the
# contract's full public name.
build_baseline_manifest = build_ontology_baseline_manifest


def _manifest_differences(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    actual_fields = set(actual)
    expected_fields = set(expected)
    for field in sorted(expected_fields - actual_fields):
        errors.append(f"missing field: {field}")
    for field in sorted(actual_fields - expected_fields):
        errors.append(f"unexpected field: {field}")
    for field in sorted(actual_fields & expected_fields):
        if actual[field] != expected[field]:
            errors.append(f"{field} does not match current Stage 03 assets")
    return errors


def verify_ontology_baseline_manifest(
    manifest: Mapping[str, Any] | None = None,
    *,
    root: Path = ROOT,
    manifest_path: Path | None = None,
) -> list[str]:
    """Return verification errors; an empty list is a passing baseline."""

    path = manifest_path or root / "config" / "modeling" / ONTOLOGY_BASELINE_PATH.name
    try:
        actual = dict(manifest) if manifest is not None else _read_json_object(path)
        expected = build_ontology_baseline_manifest(root)
    except Exception as exc:  # verification must fail closed with useful context
        return [str(exc)]
    return _manifest_differences(actual, expected)


verify_baseline_manifest = verify_ontology_baseline_manifest


def load_modeling_dependencies(
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Load all four versioned dependencies and the Stage 03 term inventory."""

    config_dir = root / "config" / "modeling"
    baseline = load_ontology_baseline(config_dir / ONTOLOGY_BASELINE_PATH.name)
    mapping_rules = load_mapping_rules(config_dir / MAPPING_RULES_PATH.name)
    terminology = load_terminology_profile(
        config_dir / TERMINOLOGY_PROFILE_PATH.name
    )
    policy = load_proposal_policy(config_dir / PROPOSAL_POLICY_PATH.name)
    errors = verify_ontology_baseline_manifest(baseline, root=root)
    if errors:
        raise DependencyError("ontology baseline verification failed: " + "; ".join(errors))
    if mapping_rules.get("ontology_baseline_version") != baseline.get(
        "ontology_version"
    ):
        raise DependencyError("mapping rules ontology baseline version mismatch")
    if mapping_rules.get("terminology_profile_version") != terminology.get(
        "profile_version"
    ):
        raise DependencyError("mapping rules terminology profile version mismatch")
    validate_modeling_evidence_references(mapping_rules, root=root)
    return {
        "ontology_baseline": baseline,
        "mapping_rules": mapping_rules,
        "terminology_profile": terminology,
        "proposal_policy": policy,
        "term_iris": load_term_inventory_iris(
            root / "docs" / "ontology" / "term-inventory.csv"
        ),
    }
