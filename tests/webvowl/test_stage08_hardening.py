from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from kg_mnp_demo.webvowl import converter, package_builder
from kg_mnp_demo.webvowl.converter import (
    ConversionError,
    convert_with_owl2vowl_docker,
)
from kg_mnp_demo.webvowl.coverage import build_coverage_report
from kg_mnp_demo.webvowl.identifiers import normalized_vowl_semantic_hash
from kg_mnp_demo.webvowl.package_builder import (
    WebVOWLPackageError,
    _validated_upstream_lock,
    build_webvowl_visualization_package,
)
from kg_mnp_demo.webvowl.policy import load_webvowl_policy
from kg_mnp_demo.webvowl.verifier import scan_vowl_leakage


@pytest.fixture(scope="module")
def visualization_package() -> dict:
    return build_webvowl_visualization_package()


def _conversion_script() -> ModuleType:
    path = Path("scripts/verify_owl2vowl_conversion.py").resolve()
    spec = importlib.util.spec_from_file_location("verify_owl2vowl_conversion", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _exact_checkout(root: Path, name: str, remote: str) -> tuple[str, str, str]:
    repository = root / "upstream-source" / name
    repository.mkdir(parents=True)
    _git(repository, "init", "--quiet")
    _git(repository, "config", "user.name", "Stage 08 Test")
    _git(repository, "config", "user.email", "stage08@example.invalid")
    _git(repository, "config", "commit.gpgsign", "false")
    _git(repository, "config", "core.autocrlf", "false")
    (repository / ".gitignore").write_text("ignored.tmp\n", encoding="utf-8")
    (repository / "source.txt").write_text("exact source\n", encoding="utf-8")
    _git(repository, "add", ".gitignore", "source.txt")
    _git(repository, "commit", "--quiet", "-m", "frozen source")
    branch = _git(repository, "branch", "--show-current")
    commit = _git(repository, "rev-parse", "HEAD")
    tree = _git(repository, "rev-parse", "HEAD^{tree}")
    _git(repository, "remote", "add", "origin", remote)
    _git(repository, "checkout", "--quiet", "--detach", commit)
    return commit, tree, branch


def test_exact_source_readiness_requires_real_clean_detached_head(
    tmp_path: Path,
) -> None:
    script = _conversion_script()
    details = {}
    for name in ("webvowl", "owl2vowl"):
        remote = f"https://example.invalid/{name}.git"
        commit, tree, branch = _exact_checkout(tmp_path, name, remote)
        details[name] = {
            "commit": commit,
            "tree": tree,
            "branch": branch,
            "remote": remote,
        }
    policy = {
        name: {
            "commit_sha": details[name]["commit"],
            "repository": details[name]["remote"],
        }
        for name in ("webvowl", "owl2vowl")
    }
    policy["source_tree_hashes"] = {
        name: details[name]["tree"] for name in ("webvowl", "owl2vowl")
    }
    lock = {
        name: {
            "commit_sha": details[name]["commit"],
            "tree_sha": details[name]["tree"],
        }
        for name in ("webvowl", "owl2vowl")
    }
    lock_path = tmp_path / "upstream-source" / "upstream-lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")

    assert script._exact_sources_ready(policy, root=tmp_path) is True

    webvowl = tmp_path / "upstream-source" / "webvowl"
    untracked = webvowl / "untracked.txt"
    untracked.write_text("not audited", encoding="utf-8")
    assert script._exact_sources_ready(policy, root=tmp_path) is False
    untracked.unlink()

    ignored = webvowl / "ignored.tmp"
    ignored.write_text("also not audited", encoding="utf-8")
    assert script._exact_sources_ready(policy, root=tmp_path) is False
    ignored.unlink()

    _git(webvowl, "checkout", "--quiet", details["webvowl"]["branch"])
    assert script._exact_sources_ready(policy, root=tmp_path) is False


def _source_record(path: Path, root: Path, role: str) -> dict[str, str]:
    return {
        "role": role,
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_converter_mounts_only_verified_ontology_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_ontology = tmp_path / "ontology" / "root.ttl"
    dependency = tmp_path / "ontology" / "dependencies" / "module.ttl"
    dependency.parent.mkdir(parents=True)
    root_ontology.write_text("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
    dependency.write_text("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
    source = {
        "root": tmp_path,
        "files": [
            _source_record(root_ontology, tmp_path, "ROOT_ONTOLOGY"),
            _source_record(dependency, tmp_path, "RUNTIME_DEPENDENCY"),
        ],
    }
    captured: list[str] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        output = json.dumps({"classAttribute": [], "propertyAttribute": []})
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr(converter.subprocess, "run", run)
    assert convert_with_owl2vowl_docker(source, image="exact-image") == {
        "classAttribute": [],
        "propertyAttribute": [],
    }
    mounts = [
        captured[index + 1]
        for index, value in enumerate(captured)
        if value == "--mount"
    ]
    mount_sources = {
        item.split("source=", 1)[1].split(",target=", 1)[0] for item in mounts
    }
    assert mount_sources == {str(root_ontology.resolve()), str(dependency.resolve())}
    assert str(tmp_path.resolve()) not in mount_sources
    assert all("readonly" in item for item in mounts)
    assert captured[captured.index("--network") + 1] == "none"

    source["files"][1]["sha256"] = "0" * 64
    with pytest.raises(ConversionError, match="hash mismatch"):
        convert_with_owl2vowl_docker(source, image="exact-image")


def test_converter_rejects_unresolved_import_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_ontology = tmp_path / "ontology" / "root.ttl"
    root_ontology.parent.mkdir(parents=True)
    root_ontology.write_text(
        """@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://example.invalid/root> a owl:Ontology ;
    owl:imports <https://example.invalid/unlisted> .
""",
        encoding="utf-8",
    )
    source = {
        "root": tmp_path,
        "files": [_source_record(root_ontology, tmp_path, "ROOT_ONTOLOGY")],
    }

    def forbidden_run(*_: object, **__: object) -> None:
        raise AssertionError("converter process must not start")

    monkeypatch.setattr(converter.subprocess, "run", forbidden_run)
    with pytest.raises(ConversionError, match="not resolved"):
        convert_with_owl2vowl_docker(source, image="exact-image")


def test_fetched_upstream_lock_cannot_override_policy(tmp_path: Path) -> None:
    policy = load_webvowl_policy()
    lock_root = tmp_path / "upstream-source"
    lock_root.mkdir()
    forged = {
        "webvowl": {
            "commit_sha": policy["webvowl"]["commit_sha"],
            "tree_sha": "0" * 40,
        },
        "owl2vowl": {
            "commit_sha": policy["owl2vowl"]["commit_sha"],
            "tree_sha": policy["source_tree_hashes"]["owl2vowl"],
        },
        "license": policy["license"],
    }
    (lock_root / "upstream-lock.json").write_text(json.dumps(forged), encoding="utf-8")
    with pytest.raises(WebVOWLPackageError, match="does not match"):
        _validated_upstream_lock(tmp_path, policy)


@pytest.mark.parametrize(
    ("hidden_value", "review_provenance"),
    (
        (
            "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/" + "a" * 64,
            False,
        ),
        ("urn:kg-mnp:review-decision:" + "b" * 64, True),
        ("urn:kg-mnp:source-record:" + "c" * 64, True),
        ("kg-mnp-0123456789abcdefabcd", False),
    ),
)
def test_full_json_leakage_scan_finds_nested_runtime_content(
    hidden_value: str, review_provenance: bool
) -> None:
    payload = {
        "header": {"title": {"en": "Formal ontology"}},
        "class": [{"id": "1", "type": "owl:Class"}],
        "classAttribute": [
            {
                "id": "1",
                "iri": "https://example.invalid/ontology#Class",
                "annotations": {"innocentLookingField": [{"value": hidden_value}]},
            }
        ],
        "property": [],
        "propertyAttribute": [],
    }
    report = scan_vowl_leakage(payload)
    assert report["status"] == "FAILED"
    assert hidden_value in report["hits"]
    assert bool(report["review_provenance_hits"]) is review_provenance


def test_leakage_scan_rejects_nested_review_metadata_key() -> None:
    payload = {
        "classAttribute": [],
        "propertyAttribute": [],
        "header": {"annotations": {"reviewDecision": "hidden metadata"}},
    }
    report = scan_vowl_leakage(payload)
    assert report == {
        "status": "FAILED",
        "hits": ["reviewDecision"],
        "review_provenance_hits": ["reviewDecision"],
    }


def test_package_uses_full_leakage_report_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, visualization_package: dict
) -> None:
    package = visualization_package
    report = json.loads(package["files"]["verification/abox-leakage-scan.json"])
    assert report == scan_vowl_leakage(package["normalized_vowl"])

    malicious = {
        "status": "FAILED",
        "hits": ["urn:kg-mnp:review-decision:" + "d" * 64],
        "review_provenance_hits": ["urn:kg-mnp:review-decision:" + "d" * 64],
    }
    monkeypatch.setattr(package_builder, "scan_vowl_leakage", lambda _: malicious)
    with pytest.raises(WebVOWLPackageError, match="leakage scan failed"):
        build_webvowl_visualization_package()


def test_coverage_scans_beyond_node_iri_fields(visualization_package: dict) -> None:
    package = visualization_package
    attacked = copy.deepcopy(package["normalized_vowl"])
    leaked = "urn:kg-mnp:review-session:" + "e" * 64
    attacked["header"]["title"]["leaked"] = {"nested": leaked}
    coverage = build_coverage_report(attacked, source=package["source"])
    assert coverage["status"] == "FAILED"
    assert leaked in coverage["abox_leakage_hits"]


def test_coverage_binds_header_type_labels_and_relations(
    visualization_package: dict,
) -> None:
    package = visualization_package
    project_prefix = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"
    project_class = next(
        item
        for item in package["normalized_vowl"]["classAttribute"]
        if str(item.get("iri", "")).startswith(project_prefix)
    )
    attacks = []

    wrong_header = copy.deepcopy(package["normalized_vowl"])
    wrong_header["header"]["iri"] = "https://example.invalid/wrong"
    attacks.append(wrong_header)

    wrong_label = copy.deepcopy(package["normalized_vowl"])
    next(
        item
        for item in wrong_label["classAttribute"]
        if str(item.get("iri", "")) == str(project_class["iri"])
    )["label"]["en"] = "forged"
    attacks.append(wrong_label)

    wrong_type = copy.deepcopy(package["normalized_vowl"])
    class_id = str(project_class["id"])
    next(item for item in wrong_type["class"] if str(item["id"]) == class_id)[
        "type"
    ] = "rdfs:Datatype"
    attacks.append(wrong_type)

    wrong_relation = copy.deepcopy(package["normalized_vowl"])
    relation = next(
        item for item in wrong_relation["propertyAttribute"] if item.get("iri")
    )
    relation["domain"] = relation["range"]
    attacks.append(wrong_relation)

    for attacked in attacks:
        report = build_coverage_report(attacked, source=package["source"])
        assert report["status"] == "FAILED"
        assert report["semantic_mismatches"]


def test_vowl_semantic_hash_binds_class_and_property_declarations() -> None:
    value = {
        "header": {},
        "namespace": [],
        "class": [{"id": "1", "type": "owl:Class"}],
        "classAttribute": [{"id": "1", "iri": "urn:formal:Class"}],
        "property": [{"id": "1", "type": "owl:ObjectProperty"}],
        "propertyAttribute": [{"id": "1", "iri": "urn:formal:property"}],
    }
    baseline = normalized_vowl_semantic_hash(value)
    changed_class = copy.deepcopy(value)
    changed_class["class"][0]["type"] = "rdfs:Datatype"
    changed_property = copy.deepcopy(value)
    changed_property["property"][0]["type"] = "owl:DatatypeProperty"
    assert normalized_vowl_semantic_hash(changed_class) != baseline
    assert normalized_vowl_semantic_hash(changed_property) != baseline
