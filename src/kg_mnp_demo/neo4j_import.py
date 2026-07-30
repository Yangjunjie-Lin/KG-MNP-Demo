"""Import RDF graphs into Neo4j via n10s, with explicit assessment overlay."""

from __future__ import annotations

from typing import Any

from rdflib import Graph

from kg_mnp_demo.neo4j_client import Neo4jConfig, run_read, run_write, session_scope
from kg_mnp_demo.neo4j_store import upsert_evaluation_result


N10S_INIT = """
CALL n10s.graphconfig.init({
  handleVocabUris: 'IGNORE',
  handleMultival: 'ARRAY',
  keepLangTag: false,
  keepCustomDataTypes: true,
  applyNeo4jNaming: true
})
"""

N10S_CONSTRAINT = """
CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS
FOR (r:Resource) REQUIRE r.uri IS UNIQUE
"""


def ensure_n10s(session) -> dict[str, Any]:
    """Initialize n10s graph config (idempotent-ish)."""
    info: dict[str, Any] = {"constraint": False, "graphconfig": False, "n10s": True}
    try:
        run_write(session, N10S_CONSTRAINT)
        info["constraint"] = True
    except Exception as exc:  # noqa: BLE001
        info["constraint_error"] = str(exc)
    try:
        # Re-init may error if already configured; treat as ok
        run_write(session, N10S_INIT)
        info["graphconfig"] = True
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "already" in msg or "graphconfig" in msg or "exists" in msg:
            info["graphconfig"] = True
            info["graphconfig_note"] = str(exc)
        else:
            info["graphconfig_error"] = str(exc)
            # Probe whether n10s procedures exist at all
            procs = run_read(
                session,
                "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'n10s' RETURN count(*) AS c",
            )
            info["n10s_procedure_count"] = procs[0]["c"] if procs else 0
            if not info["n10s_procedure_count"]:
                info["n10s"] = False
    return info


def clear_graph(session) -> None:
    run_write(session, "MATCH (n) DETACH DELETE n")


def import_rdf_turtle(session, turtle: str) -> dict[str, Any]:
    """Import Turtle via n10s inline. Falls back gracefully if n10s missing."""
    try:
        rows = run_write(
            session,
            "CALL n10s.rdf.import.inline($payload, 'Turtle') "
            "YIELD terminationStatus, triplesLoaded, triplesParsed, namespaces "
            "RETURN terminationStatus, triplesLoaded, triplesParsed, namespaces",
            payload=turtle,
        )
        return {"ok": True, "mode": "n10s", "result": rows[0] if rows else {}}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "mode": "n10s", "error": str(exc)}


def load_case_into_neo4j(
    graph: Graph,
    case_id: str,
    evaluation_result: dict[str, Any],
    *,
    config: Neo4jConfig | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    """
    Persist a case graph + evaluation result into Neo4j.

    1) Optional full reset
    2) n10s init + RDF import
    3) Explicit Cypher MERGE of assessment trace layer (authoritative for queries)
    """
    turtle = graph.serialize(format="turtle")
    if isinstance(turtle, bytes):
        turtle = turtle.decode("utf-8")

    with session_scope(config) as session:
        n10s_info = ensure_n10s(session)
        if reset:
            clear_graph(session)
            n10s_info = ensure_n10s(session)

        # Drop previous assessment overlay for this case only (keep other cases)
        run_write(
            session,
            """
            MATCH (a:EligibilityAssessment {assessmentIdentifier: $assessment_id})
            OPTIONAL MATCH (a)-[:producesBlockingReason]->(br)
            OPTIONAL MATCH (a)-[:producesDecision]->(d)
            OPTIONAL MATCH (a)-[:dependsOn]->(dep)
            DETACH DELETE br, d, dep, a
            """,
            assessment_id=f"ASSESS-{case_id}",
        )

        rdf_result = import_rdf_turtle(session, turtle)
        store_result = upsert_evaluation_result(session, case_id, evaluation_result)

    return {
        "case_id": case_id,
        "n10s": n10s_info,
        "rdf_import": rdf_result,
        "assessment_store": store_result,
        "decision": evaluation_result.get("decision"),
    }
