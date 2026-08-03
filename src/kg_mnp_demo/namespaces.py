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
    "CASE-02": "case02.json",
    "CASE-03": "case03.json",
    "CASE-04": "case04.json",
    "CASE-05": "case05.json",
    "CASE-06": "case06.json",
    "CASE-07": "case07.json",
    "CASE-08": "case08.json",
    "CASE-09": "case09.json",
}

EXAMPLE_META = {
    "CASE-01": {"expected_decision": "ELIGIBLE", "scenario": "全部条件满足，可携转"},
    "CASE-02": {"expected_decision": "BLOCKED", "scenario": "存在未结清费用"},
    "CASE-03": {"expected_decision": "BLOCKED", "scenario": "合约仍有效"},
    "CASE-04": {"expected_decision": "BLOCKED", "scenario": "多阻塞原因并存"},
    "CASE-05": {"expected_decision": "MANUAL_REVIEW", "scenario": "关键证据缺失或过期"},
    "CASE-06": {"expected_decision": "BLOCKED", "scenario": "规则版本更新后携转间隔不足"},
    "CASE-07": {"expected_decision": "ELIGIBLE", "scenario": "资格通过但授权码过期"},
    "CASE-08": {"expected_decision": "BLOCKED", "scenario": "解除协议已签未生效"},
    "CASE-09": {"expected_decision": "BLOCKED", "scenario": "实名信息不一致"},
}
