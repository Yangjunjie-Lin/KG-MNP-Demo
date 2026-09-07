from kg_mnp.semantic_kernel.validators.competency_questions import _execute


def test_isolated_query_can_return_one_thousand_bounded_rows_without_pipe_deadlock():
    data="".join(f'<urn:item:{i}> <urn:label> "'+("synthetic"*30)+f' {i}" <urn:graph> .\n' for i in range(1000)).encode()
    status,result=_execute(data,"SELECT ?item ?label WHERE { ?item <urn:label> ?label }","SELECT",10,1000)
    assert status=="OK",result
    assert len(result["rows"])==1000
