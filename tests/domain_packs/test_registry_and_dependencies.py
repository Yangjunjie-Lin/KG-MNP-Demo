from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kg_mnp.domain_packs.locking import generate_pack_lock
from kg_mnp.domain_packs.registry import DomainPackRegistry, DomainPackRegistryError
from kg_mnp.domain_packs.resolver import resolve_dependency_closure
from kg_mnp.domain_packs.validation import load_domain_pack_manifest

from .conftest import ROOT, read_manifest, write_manifest


def _pack(root: Path, pack_id: str, dependencies: list[dict[str, object]]) -> Path:
    target = root / pack_id
    shutil.copytree(ROOT / "domain_packs" / "minimal", target)
    manifest = read_manifest(target)
    manifest["pack_id"] = pack_id
    manifest["display_name"] = f"Test {pack_id}"
    manifest["dependencies"] = dependencies
    write_manifest(target, manifest)
    generate_pack_lock(load_domain_pack_manifest(target))
    return target


def test_registry_lists_and_resolves_exact_repository_versions() -> None:
    registry = DomainPackRegistry(ROOT / "domain_packs")
    assert [(item[0], item[1]) for item in registry.list()] == [
        ("forestry", "0.2.0"),
        ("minimal", "0.1.0"),
        ("mnp", "1.0.0"),
    ]
    assert registry.resolve("minimal", "0.1.0").manifest.pack_id == "minimal"
    with pytest.raises(DomainPackRegistryError, match="not found"):
        registry.resolve("forestry", "0.1.0")
    with pytest.raises(DomainPackRegistryError, match="not found"):
        registry.resolve("minimal", "9.9.9")


def test_valid_exact_dependency_closure_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "packs"
    root.mkdir()
    base = _pack(root, "base", [])
    base_lock = generate_pack_lock(load_domain_pack_manifest(base)).document
    _pack(
        root,
        "consumer",
        [
            {
                "pack_id": "base",
                "pack_version": "0.1.0",
                "content_digest": base_lock["content_digest"],
                "required_capabilities": ["ontology"],
            }
        ],
    )
    closure = resolve_dependency_closure(DomainPackRegistry(root), (("consumer", "0.1.0"),))
    assert [(item.manifest.pack_id, item.dependency_depth) for item in closure] == [
        ("base", 1),
        ("consumer", 0),
    ]


def test_missing_dependency_cycle_digest_and_capability_conflicts_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "packs"
    root.mkdir()
    _pack(
        root,
        "missing-consumer",
        [{"pack_id": "ghost", "pack_version": "0.1.0", "content_digest": "0" * 64, "required_capabilities": []}],
    )
    with pytest.raises(DomainPackRegistryError, match="not found"):
        resolve_dependency_closure(DomainPackRegistry(root), (("missing-consumer", "0.1.0"),))

    _pack(root, "cycle-a", [{"pack_id": "cycle-b", "pack_version": "0.1.0", "content_digest": "1" * 64, "required_capabilities": []}])
    _pack(root, "cycle-b", [{"pack_id": "cycle-a", "pack_version": "0.1.0", "content_digest": "2" * 64, "required_capabilities": []}])
    with pytest.raises(DomainPackRegistryError, match="cycle"):
        resolve_dependency_closure(DomainPackRegistry(root), (("cycle-a", "0.1.0"),))

    base = _pack(root, "digest-base", [])
    _pack(root, "digest-consumer", [{"pack_id": "digest-base", "pack_version": "0.1.0", "content_digest": "f" * 64, "required_capabilities": []}])
    with pytest.raises(DomainPackRegistryError, match="digest mismatch"):
        resolve_dependency_closure(DomainPackRegistry(root), (("digest-consumer", "0.1.0"),))

    base_lock = generate_pack_lock(load_domain_pack_manifest(base)).document
    _pack(root, "cap-consumer", [{"pack_id": "digest-base", "pack_version": "0.1.0", "content_digest": base_lock["content_digest"], "required_capabilities": ["mappings"]}])
    with pytest.raises(DomainPackRegistryError, match="lacks required"):
        resolve_dependency_closure(DomainPackRegistry(root), (("cap-consumer", "0.1.0"),))


def test_dependency_version_conflict_is_detected_before_resolution() -> None:
    registry = DomainPackRegistry(ROOT / "domain_packs")
    with pytest.raises(DomainPackRegistryError, match="version conflict"):
        resolve_dependency_closure(
            registry,
            (("minimal", "0.1.0"), ("minimal", "9.9.9")),
        )
