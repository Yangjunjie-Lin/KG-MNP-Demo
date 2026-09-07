from pathlib import Path

import pytest

from kg_mnp.semantic_kernel.errors import SemanticKernelError
from kg_mnp.semantic_kernel.security import assert_read_only_query


def test_locked_mnp_query_fragments_are_iris_not_comments():
    query=(Path(__file__).parents[2]/"domain_packs/mnp/queries/source_alignment.rq").read_text(encoding="utf8")
    assert assert_read_only_query(query,max_path_depth=8)=="SELECT"


@pytest.mark.parametrize("query",[
    'SELECT * WHERE { SERVICE <https://attacker.invalid/#x> {?s ?p ?o} }',
    'SELECT * FROM <https://attacker.invalid/#x> WHERE {?s ?p ?o}',
    'SELECT * WHERE {?s ?p ?o} # comment\n; DELETE WHERE {?s ?p ?o}',
])
def test_lexical_handling_does_not_hide_external_or_write_operations(query):
    with pytest.raises(SemanticKernelError):assert_read_only_query(query)
