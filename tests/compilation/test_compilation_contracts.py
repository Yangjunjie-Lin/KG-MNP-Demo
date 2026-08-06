from kg_mnp_demo.compilation.contracts import COMPILATION_CONTRACT_SPECS, load_compilation_schema


def test_compilation_contracts_have_unique_stable_ids():
    ids = [spec.schema_id for spec in COMPILATION_CONTRACT_SPECS]
    assert len(ids) == len(set(ids))
    assert all(load_compilation_schema(spec.name)["$id"] == spec.schema_id for spec in COMPILATION_CONTRACT_SPECS)
