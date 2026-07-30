"""Neo4j Bolt client helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

try:
    from neo4j import GraphDatabase, Driver, Session
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore
    Driver = Any  # type: ignore
    Session = Any  # type: ignore


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        return cls(
            uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            user=os.environ.get("NEO4J_USER", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", "kgmnp-demo-pass"),
        )


def require_neo4j_driver() -> None:
    if GraphDatabase is None:
        raise RuntimeError(
            "Package 'neo4j' is not installed. Run: pip install -e '.[neo4j]'"
        )


def get_driver(config: Neo4jConfig | None = None) -> Driver:
    require_neo4j_driver()
    cfg = config or Neo4jConfig.from_env()
    return GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))


def ping(config: Neo4jConfig | None = None, timeout_s: float = 5.0) -> dict[str, Any]:
    """Return connectivity status without raising on connection failure."""
    try:
        require_neo4j_driver()
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    cfg = config or Neo4jConfig.from_env()
    driver = None
    try:
        driver = get_driver(cfg)
        driver.verify_connectivity()
        with driver.session() as session:
            value = session.run("RETURN 1 AS n").single()["n"]
        return {"ok": True, "uri": cfg.uri, "user": cfg.user, "probe": value}
    except Exception as exc:  # noqa: BLE001 — surface any driver/network error
        return {"ok": False, "uri": cfg.uri, "error": str(exc)}
    finally:
        if driver is not None:
            driver.close()


@contextmanager
def session_scope(config: Neo4jConfig | None = None) -> Iterator[Session]:
    driver = get_driver(config)
    try:
        with driver.session() as session:
            yield session
    finally:
        driver.close()


def run_write(session: Session, query: str, **params: Any) -> list[dict[str, Any]]:
    result = session.run(query, **params)
    return [dict(record) for record in result]


def run_read(session: Session, query: str, **params: Any) -> list[dict[str, Any]]:
    result = session.run(query, **params)
    return [_normalize(dict(record)) for record in result]


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if value is None:
            out[key] = None
        elif hasattr(value, "iso_format"):
            out[key] = value.iso_format()
        else:
            out[key] = value
    return out
