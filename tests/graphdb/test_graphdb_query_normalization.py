from kg_mnp_demo.graphdb.verifier import normalize_ask_result, normalize_select_result


def test_select_rows_are_normalized_independently_of_server_order():
    value = {"head": {"vars": ["x"]}, "results": {"bindings": [{"x": {"type": "uri", "value": "urn:z"}}, {"x": {"type": "uri", "value": "urn:a"}}]}}
    assert [row["x"] for row in normalize_select_result(value)["results"]["bindings"]] == [
        {"type": "uri", "value": "urn:a"},
        {"type": "uri", "value": "urn:z"},
    ]
    assert normalize_ask_result(True) == {"boolean": True}
