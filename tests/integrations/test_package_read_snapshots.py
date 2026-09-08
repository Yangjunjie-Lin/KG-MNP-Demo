"""All local projections consume the bytes whose package verification passed."""
import json

import pytest
from rdflib import OWL, RDF

from kg_mnp.integrations import local_rdf, oms, webvowl
from kg_mnp.semantic_kernel.packaging import archive
from tests.package_archive.test_snapshot_export import package


@pytest.mark.parametrize("module", [local_rdf, oms, webvowl], ids=["local-rdf", "metadata", "visualization"])
def test_projection_does_not_reread_mutated_package_after_verification(tmp_path, monkeypatch, module):
    source = package(tmp_path)
    tbox = source / "ontology/effective-tbox.nt"
    manifest = source / "ontology-package.json"
    before_tbox, before_manifest = tbox.read_bytes(), manifest.read_bytes()
    original_verify = archive.verify_package
    calls = []

    def verify_then_mutate(snapshot):
        verified = original_verify(snapshot)
        calls.append(snapshot)
        tbox.write_bytes(before_tbox + f'<urn:unverified:class> <{RDF.type}> <{OWL.Class}> .\n'.encode())
        value = json.loads(before_manifest)
        value["package_id"] = "urn:unverified:package"
        manifest.write_text(json.dumps(value), encoding="utf-8")
        return verified

    monkeypatch.setattr(module, "verify_package", verify_then_mutate, raising=False)
    monkeypatch.setattr(archive, "verify_package", verify_then_mutate)
    try:
        if module is local_rdf:
            result = module.LocalRDFQueryAdapter(source).instances_by_class(str(OWL.Class), limit=1000)
        elif module is oms:
            result = module.OMSMetadataService(source).metadata(limit=1000)
        else:
            result = module.WebVOWLConverter().convert(source)
        assert len(calls) == 1
        assert "urn:unverified:" not in json.dumps(result)
    finally:
        tbox.write_bytes(before_tbox)
        manifest.write_bytes(before_manifest)
