import pytest

from kg_mnp.domain_packs.registry import DomainPackRegistry,DomainPackRegistryError


def test_forestry_experimental_pack_has_locked_synthetic_assets():
    pack=DomainPackRegistry().resolve("forestry","0.2.0")
    assert pack.manifest.document["lifecycle"]=="EXPERIMENTAL"
    assert "合成数据" in pack.manifest.document["display_name"]
    assert {"ontology","shacl","queries","mappings","terminology"} <= set(pack.manifest.document["entrypoints"])
    assert pack.lock.document["assets"]
    with pytest.raises(DomainPackRegistryError):
        DomainPackRegistry().resolve("forestry","0.1.0")
