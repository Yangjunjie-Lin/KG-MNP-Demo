from __future__ import annotations

import copy

from kg_mnp_demo.modeling.review_identifiers import confirmed_package_id, package_semantic_hash

from ._helpers import load_expected_package


def test_package_hash_and_id_are_self_validating():
    package = load_expected_package("full-confirmation")
    assert package["package_semantic_hash"] == package_semantic_hash(package)
    assert package["package_id"] == confirmed_package_id(package)
    tampered = copy.deepcopy(package)
    tampered["rejected_items"] = list(tampered["rejected_items"]) + []
    tampered["publication_manifest"] = dict(tampered["publication_manifest"])
    tampered["publication_manifest"]["confirmed_abox_count"] = 0
    assert package_semantic_hash(tampered) != package["package_semantic_hash"]
