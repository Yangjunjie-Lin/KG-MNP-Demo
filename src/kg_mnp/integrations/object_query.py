"""Isolated, bounded local object primitives over explicitly verified packages."""
import json
import re
from pathlib import Path

from rdflib import URIRef
from rdflib.util import from_n3

from kg_mnp.semantic_kernel.packaging.verifier import verify_package
from kg_mnp.semantic_kernel.validators.competency_questions import _execute

from .local_rdf import LocalRDFQueryAdapter


def _iri(value: str) -> str:
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value) or re.search(r'[<>"{}|^`\\\x00-\x20]', value):
        raise ValueError("invalid absolute object IRI")
    return URIRef(value).n3()


def query_objects(package_root: Path, *, class_iri: str | None = None, instance_iri: str | None = None,
                  offset: int = 0, limit: int = 100, timeout_seconds: int = 30) -> dict:
    if bool(class_iri) == bool(instance_iri) or not 0 <= offset <= 1000000 or not 1 <= limit <= 1000 or not 1 <= timeout_seconds <= 60:
        raise ValueError("object query requires one selector and bounded limits")
    selected = _iri(class_iri or instance_iri)
    verified = verify_package(package_root)
    manifest = json.loads((package_root / "dataset/rdf-dataset-manifest.json").read_bytes())
    graphs = " ".join(_iri(g["graph_iri"]) for g in manifest["graphs"] if g["role"] in {"effective-tbox", "abox", "effective-shapes"})
    if class_iri:
        variables, pattern, order = "?iri", f"?iri a {selected} . FILTER(isIRI(?iri))", "?iri"
        sort_keys = ["iri"]
    else:
        expressions = ["STR(?predicate)", "STR(?object)", 'COALESCE(STR(DATATYPE(?object)), "")',
                       'COALESCE(LANG(?object), "")', 'IF(isIRI(?object), "IRI", "LITERAL")']
        sort_keys = [f"sort{i}" for i in range(len(expressions))]
        variables = "?predicate ?object " + " ".join(f"({expression} AS ?{key})" for expression, key in zip(expressions, sort_keys, strict=True))
        pattern, order = f"{selected} ?predicate ?object", " ".join("?" + key for key in sort_keys)
    query = f"SELECT DISTINCT {variables} WHERE {{ VALUES ?graph {{ {graphs} }} GRAPH ?graph {{ {pattern} }} }} ORDER BY {order} OFFSET {offset} LIMIT {limit+1}"
    status, result = _execute((package_root / "dataset/dataset.nq").read_bytes(), query, "SELECT", timeout_seconds, limit+1)
    if status == "TIMEOUT":
        raise TimeoutError("local object query exceeded its isolated time limit")
    if status != "OK":
        raise ValueError("local object query execution failed")
    # CQ transport canonicalizes rows for hashes. Restore the explicit query
    # order before dropping the look-ahead row so page boundaries remain stable.
    rows = sorted(result["rows"], key=lambda row: tuple(str(from_n3(row[key])) if row[key] else "" for key in sort_keys))
    values = ([{"iri": str(from_n3(row["iri"]))} for row in rows[:limit]] if class_iri else
              [{"predicate": str(from_n3(row["predicate"])), "object": LocalRDFQueryAdapter._term(from_n3(row["object"]))} for row in rows[:limit]])
    return {"package_id":verified["package_id"], "rows":values,
            "page":{"offset":offset,"limit":limit,"truncated":len(rows)>limit},
            "execution":{"isolated":True,"timeout_seconds":timeout_seconds,"result_limit":limit}}
