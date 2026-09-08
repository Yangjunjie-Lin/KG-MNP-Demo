from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract
from kg_mnp.semantic_kernel.packaging.archive import archive_bytes, verify_kgop
from kg_mnp.semantic_kernel.packaging.verifier import verify_package

from ..compatibility import inspect_compatibility
from ..errors import LifecycleError
from ..security import assert_no_links, storage_key
from ._common import read, write
from .events import append_event


def _source_lock(package: Path, explicit=None):
    if explicit is not None: return explicit
    candidate=package.parent.parent/"project.lock.json"
    return json.loads(candidate.read_bytes()) if candidate.is_file() else None


def _assert_tree_no_links(root: Path) -> None:
    assert_no_links(root)
    for path in root.rglob("*"):
        assert_no_links(path)


def import_package(registry, package, *, source_project_lock=None):
    requested_root=Path(registry); assert_no_links(requested_root); requested_source=Path(package); assert_no_links(requested_source); root=requested_root.resolve(); source=requested_source.resolve(strict=True); _assert_tree_no_links(source)
    manifest=read(root,"registry-manifest.json")
    temporary = None
    try:
        if source.is_file() and source.suffix==".kgop":
            verify_kgop(source)
            temporary = tempfile.TemporaryDirectory(prefix="kg-mnp-lifecycle-import-")
            source = Path(temporary.name)
            with zipfile.ZipFile(package) as archive:
                for info in archive.infolist():
                    target = source / info.filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(info))
        verify_package(source); compatibility=inspect_compatibility(source)
    except LifecycleError: raise
    except Exception as exc: raise LifecycleError("PACKAGE_IMPORT_INVALID","package verification failed") from exc
    package_manifest=json.loads((source/"ontology-package.json").read_bytes()); package_lock=json.loads((source/"ontology-package.lock.json").read_bytes())
    source_lock_bytes = None
    if source_project_lock is not None:
        lock_source = Path(source_project_lock)
        assert_no_links(lock_source)
        source_lock_bytes = lock_source.read_bytes()
        source_lock = json.loads(source_lock_bytes)
        validate_contract("project-lock", source_lock)
        if source_lock["lock_id"] != package_manifest["project_lock_id"]:
            raise LifecycleError("PACKAGE_IMPORT_INVALID", "source ProjectLock does not match package")
    if package_manifest.get("package_name") not in manifest["accepted_package_names"] and manifest["accepted_package_names"]: raise LifecycleError("PACKAGE_IMPORT_INVALID","package name not accepted by registry")
    if package_manifest.get("ontology_identity",{}).get("ontology_iri") not in manifest["accepted_ontology_iris"] and manifest["accepted_ontology_iris"]: raise LifecycleError("PACKAGE_IMPORT_INVALID","ontology IRI not accepted by registry")
    if compatibility["compatibility_status"]!="SUPPORTED_AND_VALID": raise LifecycleError("HISTORICAL_PACKAGE_UNSUPPORTED","package uses unsupported historical contract versions")
    pid=package_manifest["package_id"]
    snap=read(root,"state/registry-snapshot.json")
    for row in snap.get("package_records",[]):
        if row.get("package_id")==pid:
            if row.get("package_lock_id")==package_lock["lock_id"] and row.get("archive_sha256")==hashlib.sha256(archive_bytes(source)).hexdigest(): return {"status":"ALREADY_IMPORTED","package_id":pid}
            raise LifecycleError("PACKAGE_ID_CONTENT_CONFLICT","package ID has different content")
        if row.get("package_name")==package_manifest["package_name"] and row.get("package_version")==package_manifest["package_version"] and row.get("package_content_digest")!=package_manifest["content_digest"]: raise LifecycleError("PACKAGE_VERSION_CONTENT_CONFLICT","package name/version has different content")
        if row.get("version_iri")==package_manifest["ontology_identity"]["version_iri"] and row.get("package_content_digest")!=package_manifest["content_digest"]: raise LifecycleError("VERSION_IRI_CONTENT_CONFLICT","version IRI has different content")
    data=archive_bytes(source); archive_sha=hashlib.sha256(data).hexdigest(); key=storage_key(pid); destination=root/"packages"/key
    if destination.exists(): raise LifecycleError("PACKAGE_ID_CONTENT_CONFLICT","package storage collision")
    object_path=root/"objects"/"sha256"/archive_sha[:2]/(archive_sha+".kgop")
    record_path=root/"records/packages"/(key+".json")
    destination_created = object_created = record_created = False
    try:
        destination.parent.mkdir(parents=True,exist_ok=True); destination_created = True; shutil.copytree(source,destination,symlinks=False)
        object_path.parent.mkdir(parents=True,exist_ok=True); object_path.write_bytes(data); object_created = True
        record_core={"manifest_kind":"KG_MNP_REGISTERED_PACKAGE_RECORD","schema_version":"1.0.0","registry_id":manifest["registry_id"],"package_id":pid,"package_name":package_manifest["package_name"],"package_version":package_manifest["package_version"],"package_status":"VALIDATED_UNPUBLISHED","ontology_iri":package_manifest["ontology_identity"]["ontology_iri"],"version_iri":package_manifest["ontology_identity"]["version_iri"],"package_content_digest":package_manifest["content_digest"],"semantic_dataset_digest":package_manifest["semantic_summary"]["semantic_dataset_digest"],"package_lock_id":package_lock["lock_id"],"package_lock_content_digest":package_lock["content_digest"],"archive_sha256":archive_sha,"archive_size_bytes":len(data),"archive_object_ref":("objects/sha256/"+archive_sha[:2]+"/"+archive_sha+".kgop"),"package_storage_ref":"packages/"+key,"built_under_catalog_digest":package_manifest["contract_catalog_digest"],"source_project_lock_id":package_manifest["project_lock_id"],"source_project_lock_ref":None,"source_project_lock_file_sha256":"0"*64,"source_domain_pack_lock_ids":package_manifest["domain_pack_locks"],"source_confirmed_package_id":package_manifest["source_confirmed_package"],"compatibility_status":compatibility["compatibility_status"],"import_status":"IMPORTED_VERIFIED"}
        if source_lock_bytes is None:
            # Frozen 1.0 schema has an overlapping nullable oneOf. Represent
            # absent source-lock bytes explicitly, without inventing a path,
            # changing that public schema, or claiming a verified source lock.
            record_core["source_project_lock_ref"] = {"availability": "NOT_PROVIDED"}
        if source_lock_bytes is not None:
            source_lock_sha = hashlib.sha256(source_lock_bytes).hexdigest()
            source_lock_ref = f"objects/sha256/{source_lock_sha[:2]}/{source_lock_sha}.json"
            source_lock_path = root / source_lock_ref
            source_lock_path.parent.mkdir(parents=True, exist_ok=True)
            if source_lock_path.exists() and source_lock_path.read_bytes() != source_lock_bytes:
                raise LifecycleError("PACKAGE_IMPORT_INVALID", "source lock object collision")
            source_lock_path.write_bytes(source_lock_bytes)
            record_core["source_project_lock_ref"] = source_lock_ref
            record_core["source_project_lock_file_sha256"] = source_lock_sha
        record={**record_core,"content_digest":semantic_hash(record_core),"record_id":stable_urn("registered-package-record",{"content_digest":semantic_hash(record_core)})}
        validate_contract("registered-package-record", record)
        write(root,"records/packages/"+key+".json",record); record_created = True
        event=append_event(root,"PackageImported",{"subject_id":record["record_id"],"related_ids":[pid],"artifact_refs":[],"transition":"IMPORTED_VERIFIED"})
    except LifecycleError:
        if record_created and record_path.is_file(): record_path.unlink()
        if object_created and object_path.is_file(): object_path.unlink()
        if destination_created and destination.is_dir(): shutil.rmtree(destination)
        raise
    except OSError as exc:
        if record_created and record_path.is_file(): record_path.unlink()
        if object_created and object_path.is_file(): object_path.unlink()
        if destination_created and destination.is_dir(): shutil.rmtree(destination)
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "package import transaction failed") from exc
    result={"status":"IMPORTED_VERIFIED","package_id":pid,"record_id":record["record_id"],"event_id":event["event_id"]}
    if temporary is not None: temporary.cleanup()
    return result
