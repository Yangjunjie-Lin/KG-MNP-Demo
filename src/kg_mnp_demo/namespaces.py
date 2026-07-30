"""Shared RDF namespaces for KG-MNP."""

from rdflib import Namespace

MNP = Namespace("http://example.org/kg-mnp#")
BASE = "http://example.org/kg-mnp#"

CASE_FILES = {
    "CASE-01": "CASE-01-eligible.ttl",
    "CASE-02": "CASE-02-billing-block.ttl",
    "CASE-03": "CASE-03-contract-block.ttl",
    "CASE-04": "CASE-04-multiple-blocks.ttl",
    "CASE-05": "CASE-05-missing-evidence.ttl",
    "CASE-06": "CASE-06-rule-update.ttl",
}
