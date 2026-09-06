from __future__ import annotations

from pathlib import Path

from kg_mnp.contracts.registry import get_contract_schema, load_contract_registry
from kg_mnp.semantic_kernel.packaging.verifier import verify_package

from .security import document


def inspect_compatibility(root, *, supported_contract_versions=None):
    root=Path(root); built=None
    try:
        manifest=document(root/"ontology-package.json"); document(root/"ontology-package.lock.json")
        # Existing Prompt 5 verifier is the authority for package bytes.
        verify_package(root)
        supported=supported_contract_versions or {(s.name,s.version) for s in load_contract_registry().specs}
        kinds={}
        for s in load_contract_registry().specs:
            kind=get_contract_schema(s.name).get("properties",{}).get("manifest_kind",{}).get("const")
            if kind: kinds.setdefault(kind,[]).append((s.name,s.version))
        unsupported=[]
        for path in sorted(root.rglob("*.json")):
            value=document(path); kind=value.get("manifest_kind");
            if kind is None or kind.startswith("KG_MNP_PACKAGE_"): continue
            version=value.get("schema_version"); choices=kinds.get(kind,[])
            if not any(pair in supported and pair[1]==version for pair in choices): unsupported.append({"kind":kind,"version":version})
        built=manifest.get("contract_catalog_digest")
        if unsupported: return {"compatibility_status":"VALID_BUT_UNSUPPORTED_CONTRACT_VERSION","built_under_catalog_digest":built,"unsupported_contracts":unsupported,"package_id":manifest.get("package_id")}
        return {"compatibility_status":"SUPPORTED_AND_VALID","built_under_catalog_digest":built,"unsupported_contracts":[],"package_id":manifest.get("package_id")}
    except Exception as exc:  # noqa: BLE001
        return {"compatibility_status":"INVALID_OR_TAMPERED","built_under_catalog_digest":built,"unsupported_contracts":[],"package_id":None,"failure_type":type(exc).__name__}
