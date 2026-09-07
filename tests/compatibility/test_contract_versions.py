import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from kg_mnp.contracts.catalog import ContractCatalog, package_resource_bytes
from kg_mnp.contracts.registry import get_contract_schema
from kg_mnp.semantic_kernel.contracts import verify_artifact
from kg_mnp.semantic_kernel.policy import load_compiler_policy
from kg_mnp.semantic_kernel.snapshot import build_compiler_snapshot


def test_all_original_contract_bytes_and_ids_survive_new_versions():
    original=json.loads((Path(__file__).with_name('fixtures')/'original-contracts.json').read_bytes())
    assert len(original['contracts'])==115
    catalog=ContractCatalog.load()
    for contract in original['contracts']:
        spec=catalog.by_name(contract['name'])
        assert spec.schema_id==contract['schema_id']
        assert hashlib.sha256(package_resource_bytes(spec.resource_path)).hexdigest()==contract['sha256']


def test_new_compiler_has_new_policy_and_snapshot_contract_without_weakening_old():
    policy=load_compiler_policy()
    snapshot=build_compiler_snapshot(policy)
    assert policy['schema_version']==snapshot['schema_version']=='1.1.0'
    assert policy['compiler_version']==snapshot['compiler_version']=='0.5.1'
    assert get_contract_schema('semantic-compiler-snapshot')['properties']['compiler_version']=={'const':'0.5.0'}
    verify_artifact(snapshot,id_field='snapshot_id',urn_kind='semantic-compiler-snapshot',contract='semantic-compiler-snapshot')
    invalid={**snapshot,'schema_version':'9.9.9'}
    with pytest.raises(ValidationError):
        verify_artifact(invalid,id_field='snapshot_id',urn_kind='semantic-compiler-snapshot',contract='semantic-compiler-snapshot')
