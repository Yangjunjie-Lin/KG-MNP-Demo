from kg_mnp_demo.compilation.policy import compiler_policy_hash, load_compiler_policy, validate_compiler_policy


def test_frozen_policy_is_closed_and_hashed():
    policy = load_compiler_policy()
    validate_compiler_policy(policy)
    assert policy["compiler_policy_id"] == "kg-mnp-stage06-formal-compiler"
    assert policy["candidate_compilation"]["MAPPING_ASSERTION"].startswith("FORBIDDEN")
    assert len(compiler_policy_hash(policy)) == 64
