"""Bounded v3 SHACL worker; no imports fetching, JS, or advanced rules."""
from __future__ import annotations

import multiprocessing
from importlib.metadata import version
from queue import Empty


def _worker(payload, output):
    try:
        from pyshacl import validate
        from rdflib import Graph
        graphs = {role: Graph().parse(data=raw, format="turtle") for role, raw in payload.items()}
        conforms, _report, _text = validate(graphs["instances"], shacl_graph=graphs["shapes"], ont_graph=graphs["ontology"],
            inference="none", advanced=False, js=False, do_owl_imports=False, meta_shacl=True)
        output.put({"status": "PASS" if conforms else "FAIL", "pyshacl_version": version("pyshacl"), "inference": "NONE"})
    except Exception as exc:  # noqa: BLE001 - bounded public diagnostics only
        output.put({"status": "ENGINE_ERROR", "error_type": type(exc).__name__})


def shacl_check(graphs, *, timeout_seconds=30):
    payload = {role: graph.serialize(format="turtle", encoding="utf-8") for role, graph in graphs.items()}
    context = multiprocessing.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(target=_worker, args=(payload, output))
    process.start()
    try:
        return {**output.get(timeout=timeout_seconds), "timeout_seconds": timeout_seconds}
    except Empty:
        return {"status": "TIMEOUT" if process.is_alive() else "ENGINE_ERROR", "timeout_seconds": timeout_seconds}
    finally:
        process.join(.2)
        if process.is_alive():
            process.terminate()
        process.join(5)
        output.close()
        output.join_thread()
