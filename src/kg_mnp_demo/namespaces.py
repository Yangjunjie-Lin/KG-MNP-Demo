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
    "CASE-07": "CASE-07-auth-expired.ttl",
    "CASE-08": "CASE-08-termination-pending.ttl",
    "CASE-09": "CASE-09-identity-conflict.ttl",
}

CASE_JSON_FILES = {
    "CASE-01": "case01.json",
    "CASE-03": "case03.json",
    "CASE-04": "case04.json",
    "CASE-07": "case07.json",
    "CASE-08": "case08.json",
    "CASE-09": "case09.json",
}
