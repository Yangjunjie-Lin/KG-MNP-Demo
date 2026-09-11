from pathlib import Path

from ..errors import LifecycleError
from ._common import read
from .snapshot import rebuild_snapshot


def rebuild_indexes(root):
    root=Path(root); snap=rebuild_snapshot(root); indexes={"packages-by-id.json":snap["package_records"],"packages-by-name-version.json":snap["package_records"],"releases-by-id.json":snap["releases"],"releases-by-package.json":snap["releases"],"ontology-lineages.json":snap["releases"],"consumers.json":snap["consumer_manifests"],"environments.json":snap["environments"]}
    from ._common import write
    for name,value in indexes.items(): write(root,"indexes/"+name,{"index_name":name,"records":value})
    return indexes


def verify_indexes(root):
    """Check derived indexes against the current immutable snapshot."""
    root=Path(root); snap=read(root,"state/registry-snapshot.json")
    expected={"packages-by-id.json":snap["package_records"],"packages-by-name-version.json":snap["package_records"],"releases-by-id.json":snap["releases"],"releases-by-package.json":snap["releases"],"ontology-lineages.json":snap["releases"],"consumers.json":snap["consumer_manifests"],"environments.json":snap["environments"]}
    for name, records in expected.items():
        path=root/"indexes"/name
        if not path.is_file():
            continue
        value=read(root,f"indexes/{name}")
        if value.get("index_name") != name or value.get("records") != records:
            raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", f"derived index mismatch: {name}")
    return {"status":"VALID","index_count":len(list((root/"indexes").glob("*.json")))}
