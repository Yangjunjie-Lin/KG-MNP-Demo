"""Deterministic eligibility rule engine (amounts/dates in Python)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import yaml
from rdflib import Graph, URIRef

from kg_mnp_demo.loader import rules_path
from kg_mnp_demo.namespaces import MNP

ASSESSMENT_TIME = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def resolve_case_uri(graph: Graph, case_id: str) -> URIRef | None:
    """Resolve the MNPCase node by caseIdentifier (not by IRI local-name convention)."""
    q = """
    PREFIX mnp: <http://example.org/kg-mnp#>
    SELECT ?case WHERE {
      ?case a mnp:MNPCase ;
            mnp:caseIdentifier ?caseId .
      FILTER(STR(?caseId) = %s)
    }
    """ % f'"{case_id}"'
    for row in graph.query(q):
        return row.case
    return None


def load_rules(*, include_updates: bool = True) -> list[dict[str, Any]]:
    with open(rules_path(), encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    rules = list(raw.get("rules", []))
    if include_updates:
        # Prefer updated versions by replacing same rule_id
        updates = {r["rule_id"]: r for r in raw.get("rule_updates", [])}
        merged: dict[str, dict] = {r["rule_id"]: r for r in rules}
        merged.update(updates)
        # Keep stable order by rule_id
        return [merged[k] for k in sorted(merged.keys())]
    return rules


def load_all_rule_versions() -> list[dict[str, Any]]:
    with open(rules_path(), encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return list(raw.get("rules", [])) + list(raw.get("rule_updates", []))


@dataclass
class EvidenceView:
    iri: str
    evidence_type: str
    status: str
    generated_at: datetime | None
    valid_until: datetime | None
    fields: dict[str, Any] = field(default_factory=dict)

    def is_usable(self, as_of: datetime = ASSESSMENT_TIME) -> bool:
        if self.status != "VALID":
            return False
        if self.valid_until and self.valid_until < as_of:
            return False
        return True


@dataclass
class RuleOutcome:
    rule_id: str
    version: str
    effective_from: str
    status: str  # PASS | FAIL | MISSING
    reason_code: str | None = None
    action_code: str | None = None
    regulatory_clause: str | None = None
    evidence_iri: str | None = None
    message: str = ""


def collect_evidence(graph: Graph, case_id: str) -> dict[str, list[EvidenceView]]:
    """Collect evidence via MNPCase hasCaseEvidence (not IRI naming conventions)."""
    q = """
    PREFIX mnp: <http://example.org/kg-mnp#>
    SELECT ?ev ?type ?status ?gen ?until ?idMatch ?numStatus ?amount ?currency
           ?arrangement ?ctrStatus ?ctrEnd ?days ?sys ?sysId
    WHERE {
      ?case a mnp:MNPCase ;
            mnp:caseIdentifier ?caseId ;
            mnp:hasCaseEvidence ?ev .
      FILTER(STR(?caseId) = %s)

      ?ev a ?evidenceClass .
      VALUES ?evidenceClass { mnp:EvidenceRecord mnp:SystemObservation }
      ?ev mnp:evidenceType ?type ;
          mnp:evidenceStatus ?status ;
          mnp:evidenceGeneratedAt ?gen ;
          mnp:hasSourceSystem ?sys .
      OPTIONAL { ?ev mnp:evidenceValidUntil ?until }
      OPTIONAL { ?ev mnp:identityMatchFlag ?idMatch }
      OPTIONAL { ?ev mnp:numberStatusCode ?numStatus }
      OPTIONAL { ?ev mnp:observedAmount ?amount }
      OPTIONAL { ?ev mnp:currencyCode ?currency }
      OPTIONAL { ?ev mnp:hasPaymentArrangement ?arrangement }
      OPTIONAL { ?ev mnp:contractStatusCode ?ctrStatus }
      OPTIONAL { ?ev mnp:contractEndTime ?ctrEnd }
      OPTIONAL { ?ev mnp:daysSinceLastPort ?days }
      OPTIONAL { ?sys mnp:systemIdentifier ?sysId }
    }
    """ % f'"{case_id}"'
    by_type: dict[str, list[EvidenceView]] = {}
    seen: set[str] = set()
    for row in graph.query(q):
        iri = str(row.ev)
        if iri in seen:
            continue
        seen.add(iri)
        fields = {
            "identityMatchFlag": (
                bool(row.idMatch) if row.idMatch is not None else None
            ),
            "numberStatusCode": str(row.numStatus) if row.numStatus else None,
            "observedAmount": (
                Decimal(str(row.amount)) if row.amount is not None else None
            ),
            "currencyCode": str(row.currency) if row.currency else None,
            "hasPaymentArrangement": (
                bool(row.arrangement) if row.arrangement is not None else None
            ),
            "contractStatusCode": str(row.ctrStatus) if row.ctrStatus else None,
            "contractEndTime": _parse_dt(row.ctrEnd) if row.ctrEnd else None,
            "daysSinceLastPort": int(row.days) if row.days is not None else None,
            "source_system": str(row.sysId) if row.sysId else str(row.sys),
            "source_system_iri": str(row.sys),
        }
        view = EvidenceView(
            iri=iri,
            evidence_type=str(row.type),
            status=str(row.status),
            generated_at=_parse_dt(row.gen),
            valid_until=_parse_dt(row.until),
            fields=fields,
        )
        by_type.setdefault(view.evidence_type, []).append(view)
    return by_type


def _eval_check(
    check: dict[str, Any],
    evidence: EvidenceView,
    *,
    assessment_time: datetime,
) -> bool:
    ctype = check["type"]
    fields = evidence.fields
    if ctype == "boolean_equals":
        return fields.get(check["field"]) is True and check["expected"] is True
    if ctype == "string_in":
        return fields.get(check["field"]) in check["expected"]
    if ctype == "billing_cleared":
        amount = fields.get(check["amount_field"])
        arrangement = fields.get(check["arrangement_field"])
        if amount is None:
            return False
        if Decimal(amount) <= Decimal(check.get("max_outstanding", 0)):
            return True
        return bool(arrangement)
    if ctype == "contract_not_blocking":
        status = fields.get(check["status_field"])
        end_time = fields.get(check["end_time_field"])
        as_of = assessment_time
        if status in (None, "EXPIRED", "TERMINATED", "NONE"):
            return True
        if status == "ACTIVE":
            if end_time is None:
                return False
            return end_time <= as_of
        return True
    if ctype == "min_integer":
        value = fields.get(check["field"])
        if value is None:
            return False
        return int(value) >= int(check["minimum"])
    raise ValueError(f"Unknown check type: {ctype}")


def evaluate_rules(
    graph: Graph,
    case_id: str,
    *,
    use_updated_rules: bool = True,
    assessment_time: datetime | None = None,
) -> list[RuleOutcome]:
    as_of = assessment_time or ASSESSMENT_TIME
    evidence = collect_evidence(graph, case_id)
    rules = load_rules(include_updates=use_updated_rules)
    outcomes: list[RuleOutcome] = []
    for rule in rules:
        etype = rule["inputs"][0]["evidence_type"]
        candidates = evidence.get(etype, [])
        usable = [e for e in candidates if e.is_usable(as_of)]
        if not usable:
            outcomes.append(
                RuleOutcome(
                    rule_id=rule["rule_id"],
                    version=str(rule["version"]),
                    effective_from=str(rule["effective_from"]),
                    status="MISSING",
                    reason_code="MISSING_OR_EXPIRED_EVIDENCE",
                    action_code="SUPPLY_MISSING_EVIDENCE",
                    regulatory_clause=rule.get("regulatory_clause"),
                    evidence_iri=candidates[0].iri if candidates else None,
                    message=f"Critical evidence {etype} missing or expired",
                )
            )
            continue
        # Deterministic: pick lexicographically smallest IRI
        chosen = sorted(usable, key=lambda e: e.iri)[0]
        passed = _eval_check(rule["check"], chosen, assessment_time=as_of)
        if passed:
            outcomes.append(
                RuleOutcome(
                    rule_id=rule["rule_id"],
                    version=str(rule["version"]),
                    effective_from=str(rule["effective_from"]),
                    status="PASS",
                    regulatory_clause=rule.get("regulatory_clause"),
                    evidence_iri=chosen.iri,
                    message="passed",
                )
            )
        else:
            outcomes.append(
                RuleOutcome(
                    rule_id=rule["rule_id"],
                    version=str(rule["version"]),
                    effective_from=str(rule["effective_from"]),
                    status="FAIL",
                    reason_code=rule["reason_code"],
                    action_code=rule["action_code"],
                    regulatory_clause=rule.get("regulatory_clause"),
                    evidence_iri=chosen.iri,
                    message=f"failed check for {etype}",
                )
            )
    return outcomes


def summarize_decision(outcomes: list[RuleOutcome]) -> str:
    if any(o.status == "MISSING" for o in outcomes):
        return "MANUAL_REVIEW"
    fails = [o for o in outcomes if o.status == "FAIL"]
    if fails:
        return "BLOCKED"
    return "ELIGIBLE"


def clause_iri(clause_id: str) -> URIRef:
    # REG-MNP-CLAUSE-01 → Clause-01
    suffix = clause_id.replace("REG-MNP-CLAUSE-", "")
    return MNP[f"Clause-{suffix}"]


def rule_iri(rule_id: str, version: str) -> URIRef:
    if rule_id == "MNP-ELIG-005" and version == "1.1":
        return MNP["Rule-MNP-ELIG-005-v1-1"]
    return MNP[f"Rule-{rule_id}"]


def rule_version_iri(rule_id: str, version: str) -> URIRef:
    return MNP[f"RuleVersion-{rule_id}-{version.replace('.', '-')}"]


def action_iri(action_code: str) -> URIRef:
    return MNP[f"Action-{action_code}"]
