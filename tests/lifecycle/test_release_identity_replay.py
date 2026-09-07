from kg_mnp.lifecycle.contracts import verify
from kg_mnp.lifecycle.registry.replay import verify_registry


def test_published_release_identity_replays_without_rewriting_bytes(prompt05_case,tmp_path):
    from kg_mnp.lifecycle.registry.head import read_head
    from kg_mnp.lifecycle.registry.import_package import import_package
    from kg_mnp.lifecycle.registry.manifest import init_registry
    from kg_mnp.lifecycle.release import (
        create_release_candidate,
        publish_release,
        record_review,
    )
    root=tmp_path/"registry"
    init_registry(root)
    package=prompt05_case["result"].package_directory
    imported=import_package(root,package,source_project_lock=prompt05_case["workspace"]/"project.lock.json")
    candidate=create_release_candidate(root,candidate_package_id=imported["package_id"])
    review=record_review(root,candidate["release_candidate_id"],reviewer_id="human",reviewer_roles=["RELEASE_MANAGER"])
    release=publish_release(root,candidate,review,expected_registry_head_hash=read_head(root)["head_hash"])
    assert verify(release,contract="release-manifest")["release_id"]==release["release_id"]
    assert verify_registry(root)["status"]=="VALID"
