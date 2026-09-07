from pathlib import Path

import yaml

from kg_mnp.contracts.canonical import semantic_hash


def test_mnp_original_query_registry_semantic_hash_is_preserved():
    root=Path(__file__).resolve().parents[2]
    document=yaml.safe_load((root/'domain_packs/mnp/queries/query-registry-1.0.0.yaml').read_text(encoding='utf-8'))
    assert semantic_hash(document)=='8971d445a26bf97b855bb0174edd446f4dd9204fd7dc4c48e734a0f9fce5c0e6'
