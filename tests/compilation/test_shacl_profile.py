from kg_mnp_demo.compilation.shacl_validation import load_shapes


def test_default_shacl_profile_is_frozen():
    _, manifest, files = load_shapes()
    assert manifest["profiles"][0]["profile_id"] == "foundation-instance"
    assert manifest["profiles"][0]["byte_sha256"]
    assert files["shapes/foundation-instance-shapes.ttl"].endswith(b"\n")
