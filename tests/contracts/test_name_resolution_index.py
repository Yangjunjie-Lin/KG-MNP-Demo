from dataclasses import replace

import pytest

from kg_mnp.contracts.catalog import (
    ContractCatalog,
    _name_aliases,
    normalize_contract_name,
)
from kg_mnp.contracts.errors import UnknownContractError


def test_name_index_is_bound_to_complete_immutable_catalog_metadata():
    spec = ContractCatalog.load().specs[0]
    assert normalize_contract_name(spec.schema_id, (spec,)) == spec.name
    altered = replace(spec, name="replacement-contract", sha256="a" * 64)
    assert normalize_contract_name(altered.schema_id, (altered,)) == altered.name
    with pytest.raises(UnknownContractError):
        normalize_contract_name(spec.name, (altered,))
    by_id, _, _ = _name_aliases((spec,))
    with pytest.raises(TypeError):
        by_id[spec.schema_id] = "mutated"
