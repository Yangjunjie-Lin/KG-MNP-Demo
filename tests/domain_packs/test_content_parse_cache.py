import shutil
from pathlib import Path

from kg_mnp.domain_packs.validation import _rdf_syntax_facts, validate_domain_pack


def test_parse_cache_uses_current_bytes_and_does_not_cache_pack_or_lock_verdict(tmp_path):
    source=Path(__file__).parents[2]/"domain_packs/minimal";target=tmp_path/"minimal"
    shutil.copytree(source,target)
    assert validate_domain_pack(target).valid
    before=_rdf_syntax_facts.cache_info().hits
    assert validate_domain_pack(target).valid
    assert _rdf_syntax_facts.cache_info().hits>before
    ontology=target/"ontology/minimal.ttl"
    ontology.write_text("not valid turtle",encoding="utf8")
    assert not validate_domain_pack(target).valid
    assert "ASSET_PARSE_FAILED" in {c["code"] for c in validate_domain_pack(target,verify_lock=False).report["checks"]}
