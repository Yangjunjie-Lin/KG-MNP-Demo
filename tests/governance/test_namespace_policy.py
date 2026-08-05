"""Namespace policy tests for Stage 02 governance config."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "namespaces.yaml"


def _load() -> dict:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _http_iris(data: dict) -> list[str]:
    values: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            if node.startswith("http://") or node.startswith("https://"):
                values.append(node)

    walk(data)
    return values


def test_namespaces_config_parses():
    data = _load()
    assert data["policy_version"] == "1.0"
    assert data["project_base"].endswith("/")


def test_http_iris_use_https_and_are_absolute():
    for iri in _http_iris(_load()):
        parsed = urlparse(iri)
        assert parsed.scheme == "https", iri
        assert parsed.netloc, iri
        assert "example.org" not in iri
        assert "localhost" not in iri
        assert "\\" not in iri
        assert not re_is_local_path(iri)


def re_is_local_path(value: str) -> bool:
    return value.startswith("/") or (len(value) > 2 and value[1] == ":")


def test_term_and_base_suffix_rules():
    data = _load()
    assert data["ontology"]["base"].endswith("/")
    assert data["ontology"]["terms"].endswith("#")
    assert data["shapes"]["namespace"].endswith("#")
    assert data["instances"]["base"].endswith("/")
    assert data["evidence"]["base"].endswith("/")
    assert data["mappings"]["base"].endswith("/")
    assert data["review"]["base"].endswith("/")


def test_named_graphs_use_stable_urns():
    graphs = _load()["named_graphs"]
    expected = {
        "ontology": "urn:kg-mnp:ontology",
        "shapes": "urn:kg-mnp:shapes",
        "instances": "urn:kg-mnp:instances",
        "evidence": "urn:kg-mnp:evidence",
        "mappings": "urn:kg-mnp:mappings",
        "review": "urn:kg-mnp:review",
    }
    assert graphs == expected
    for value in graphs.values():
        assert value.startswith("urn:kg-mnp:")


def test_namespaces_do_not_collide():
    data = _load()
    values = [
        data["project_base"],
        data["ontology"]["base"],
        data["ontology"]["terms"],
        data["shapes"]["namespace"],
        data["instances"]["base"],
        data["evidence"]["base"],
        data["mappings"]["base"],
        data["review"]["base"],
        *data["named_graphs"].values(),
    ]
    assert len(values) == len(set(values))
