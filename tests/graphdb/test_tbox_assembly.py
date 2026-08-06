from kg_mnp_demo.graphdb.tbox_assembler import assemble_runtime_tbox


def test_runtime_tbox_has_root_and_runtime_modules_only():
    result = assemble_runtime_tbox()
    assert result["module_count"] == 10
    assert "ALIGNMENTS" not in {item["code"] for item in result["modules"]}
    assert all(item["graph_iri"].startswith("urn:kg-mnp:graph:tbox:") for item in result["modules"])
    assert b"_:" not in result["data"]
