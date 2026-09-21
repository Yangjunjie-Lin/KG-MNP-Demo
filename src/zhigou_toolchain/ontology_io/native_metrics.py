"""Audited native metric functions, pinned to upstream bytes, without imports.

LLMs4OL's top-level import downloads a remote-code embedding model even for
exact scoring. This adapter executes the original exact function AST verbatim,
not the unrelated eager loader. Semantic scoring remains blocked until that
model's code/weights and execution sandbox are separately audited and pinned.
"""
from __future__ import annotations

import ast
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import networkx as nx

LLMS4OL_COMMIT = "315a9a5d883eada26e00fef1356a05802936c584"
LLMS4OL_SCORER_SHA256 = "4eb22bfb304a0239269951c3ac65ff8fa39a8fd69fe1159ee40bbeba676159c9"
EXACT_FUNCTIONS = {"edge_f1", "get_neighborhood", "neighborhood_similarity", "normalize", "normalize_triples",
    "build_taxonomy_graph", "taxonomy_similarity", "exact_match"}


def verified_source(directory: Path, relative: str) -> bytes:
    lock = json.loads((directory / "asset-lock.json").read_bytes())
    if lock["commit"] != LLMS4OL_COMMIT:
        raise ValueError("SCORER_REVISION_MISMATCH")
    entry = next(row for row in lock["files"] if row["path"] == relative)
    raw = (directory / relative).read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"] or entry["sha256"] != LLMS4OL_SCORER_SHA256:
        raise ValueError("SCORER_SOURCE_CHANGED")
    return raw


def llms4ol_functions(directory, *, fuzzy=False):
    raw = verified_source(Path(directory), "2026/metrics/graph_similarity.py")
    tree = ast.parse(raw)
    names = EXACT_FUNCTIONS | ({"triple_similarity_fuzzy", "align_triples_fuzzy", "fuzzy_match"} if fuzzy else set())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in selected} != names:
        raise ValueError("UPSTREAM_METRIC_INTERFACE_CHANGED")
    namespace = {"nx": nx, "defaultdict": defaultdict, "TAXONOMY_RELATIONS": {"is-a"}}
    if fuzzy:
        from importlib.metadata import version

        import numpy as np
        from rapidfuzz import fuzz
        from scipy.optimize import linear_sum_assignment

        if any(version(k) != v for k, v in FUZZY_DEPENDENCIES.items()):
            raise ValueError("FUZZY_DEPENDENCY_LOCK_MISMATCH")
        namespace.update(np=np, fuzz=fuzz, linear_sum_assignment=linear_sum_assignment)
    # Only these reviewed functions are compiled; no import, file access,
    # module initialization, network, or model execution is copied into the AST.
    exec(compile(ast.Module(body=list(selected), type_ignores=[]), "locked_llms4ol_exact", "exec"), namespace)  # noqa: S102
    return namespace


FUZZY_DEPENDENCIES = {"rapidfuzz": "3.14.3", "numpy": "2.4.6", "scipy": "1.15.2"}


def llms4ol_exact(directory, gold, prediction):
    return llms4ol_functions(directory)["exact_match"](gold, prediction)


def llms4ol_fuzzy(directory, gold, prediction):
    # Fixed upstream public default; never tune against target scores.
    return llms4ol_functions(directory, fuzzy=True)["fuzzy_match"](gold, prediction, threshold=.90)


def native_status(matching):
    if matching == "exact":
        return "READY"
    if matching == "fuzzy":
        from importlib.metadata import PackageNotFoundError, version
        try:
            if all(version(k) == v for k, v in FUZZY_DEPENDENCIES.items()):
                return "READY"
        except PackageNotFoundError:
            pass
        return "BLOCKED_FUZZY_DEPENDENCY_LOCK"
    return "BLOCKED_NATIVE_MATCHER_MODEL_OR_CONFIG_NOT_LOCKED"
