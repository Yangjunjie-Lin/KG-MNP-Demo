from __future__ import annotations

from importlib import resources

from kg_mnp.contracts import ContractCatalog, get_contract_schema, validate_contract
from kg_mnp.contracts.canonical import bytes_sha256

PROMPT02_SCHEMA_HASHES = {
    "schemas/toolchain/artifact_manifest.schema.json": "052ddeb56d9bb57f6774669699fc41d30c7a7a435d5a4d20e462400eca4c2fed",
    "schemas/toolchain/artifact_reference.schema.json": "7c4905674ce71d049371cbc6a78b02c5d42ec6b589a64ce059b396f0ce30be74",
    "schemas/modeling/cleaned_partial_data.schema.json": "7fafb0921bd0f6f28fc0f879e0eec4ec8a426c0b49c30991421e28ef1cf531b7",
    "schemas/modeling/common.schema.json": "7c50453e35e0a3b3868d9480e35c75cb126b04355c96b5ff887995ae41c61e7c",
    "schemas/modeling/confirmed_modeling_package.schema.json": "e8dfd1ce630f6c7e93a7e49691de7fac100895d143dc500afe1903a3e0107146",
    "schemas/toolchain/contract_catalog.schema.json": "a08301069e73efb6b763ab925bd86169c269d4bbd5a878c8c5770ff8b169c065",
    "schemas/toolchain/domain_pack_lock.schema.json": "44748143bd9edecc72f2a07a06537fd3f0374c72eeaa474b0808a2257fba2038",
    "schemas/toolchain/domain_pack_manifest.schema.json": "1659bf5f43cde32a255d66946cd5e7e0eb2ccdbf712e939b4260bbef01e5a0d2",
    "schemas/modeling/mapping_rules.schema.json": "57b5de7e6f2f9a2eb4735ef6b386016934186f29843f9dd9e21647b08f387137",
    "schemas/modeling/modeling_proposal.schema.json": "e7139bfd7402d6ba362134c3fa5537b478c0a42805b971ed54e701b513cdcd3b",
    "schemas/modeling/ontology_baseline_manifest.schema.json": "54adc74ba2bfd638ef2d8de805ea3c2ae6da114129396b9bb385f576a5de2781",
    "schemas/toolchain/project_lock.schema.json": "987475fdd410b6f5ee2a0f4445486c3ce2712f6ac604b1bf778f3fe647387399",
    "schemas/toolchain/project_manifest.schema.json": "91c400c463a018f66da4ed85a395b4a4ab767a5e987d1bea655d3e20eaf2e161",
    "schemas/modeling/review_action.schema.json": "b2c041c9f1a6cb33b67fdf34b317b780112ca677b2e3f5013f15355a4ab939d3",
    "schemas/modeling/review_common.schema.json": "69b3af6bd9c70f17524d311d29aa5abcc7d066a01f992ca45885fba3448a3b7c",
    "schemas/modeling/review_decision_log.schema.json": "ef24e251d4bbb4cbc12b081f6f371ec0e294c240a76151bada870b7f66c21ada",
    "schemas/modeling/review_policy.schema.json": "5b252e1f0b558ad2fc9592a975c6ce9003a8152077ce631101418f5a1828ae54",
    "schemas/modeling/terminology_profile.schema.json": "49841b8bc0089a562a314edfcd8740b41742a1d4a5278825075ed3a444cd1b69",
    "schemas/toolchain/toolchain_common.schema.json": "26ab63f196d0bfa47a35fc3577e27123d594932537c96bee0de18a17301f0200",
    "schemas/toolchain/validation_report.schema.json": "7ff6c26195db212b5bad45f344953cb5eeea3fefcab50291754bef8b53947d93",
}

PROMPT03_CONTRACTS = {
    "plugin-common",
    "plugin-manifest",
    "plugin-snapshot",
    "source-locator",
    "source-asset",
    "source-batch",
    "transformation-record",
    "evidence-record",
    "kg-ir-item",
    "kg-ir-dataset",
    "ingestion-plan",
    "quality-report",
    "ingestion-run",
}


def test_original_twenty_contract_schema_bytes_are_unchanged() -> None:
    package = resources.files("kg_mnp.contracts")
    assert len(PROMPT02_SCHEMA_HASHES) == 20
    for path, expected in PROMPT02_SCHEMA_HASHES.items():
        assert bytes_sha256(package.joinpath(path).read_bytes()) == expected


def test_prompt03_contracts_are_single_catalog_ingestion_scope_and_packaged() -> None:
    catalog = ContractCatalog.load()
    ingestion = {spec.name for spec in catalog.filtered(scope="ingestion")}
    assert PROMPT03_CONTRACTS.issubset(ingestion)
    assert len(catalog.specs) == 34
    package = resources.files("kg_mnp.contracts")
    for name in PROMPT03_CONTRACTS:
        spec = catalog.by_name(name)
        assert spec.version == "1.0.0"
        assert spec.scope == "ingestion"
        assert package.joinpath(spec.resource_path).is_file()
        assert get_contract_schema(name)["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_catalog_1_1_adds_ingestion_without_mutating_frozen_1_0() -> None:
    catalog = ContractCatalog.load()
    assert catalog.document["schema_version"] == "1.1.0"
    validate_contract("contract-catalog-v1-1", catalog.document)
    frozen = get_contract_schema("contract-catalog")
    migration = get_contract_schema("contract-catalog-v1-1")
    assert frozen["$id"].endswith("/contract-catalog/1.0")
    assert frozen["properties"]["schema_version"]["$ref"].endswith(
        "/toolchain-common/1.0#/$defs/schemaVersion"
    )
    assert frozen["properties"]["contracts"]["items"]["properties"]["scope"]["enum"] == [
        "toolchain",
        "modeling",
    ]
    assert migration["properties"]["schema_version"]["const"] == "1.1.0"
    assert "ingestion" in migration["properties"]["contracts"]["items"]["properties"]["scope"]["enum"]
