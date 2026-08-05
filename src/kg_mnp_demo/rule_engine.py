"""Deterministic eligibility rule engine (amounts/dates in Python)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import yaml
from rdflib import Graph, URIRef

from kg_mnp_demo.loader import rules_path
from kg_mnp_demo.namespaces import DATA, MNP

ASSESSMENT_TIME = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)


class RuleConfigurationError(ValueError):
    """Raised when rule YAML validity windows or metadata are invalid."""


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _fmt_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_case_uri(graph: Graph, case_id: str) -> URIRef | None:
    """Resolve the MNPCase node by caseIdentifier (not by IRI local-name convention)."""
    from rdflib import Literal
    from rdflib.namespace import XSD

    q = """
    PREFIX mnp: <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>
    SELECT ?case WHERE {
      ?case a mnp:MNPCase ;
            mnp:caseIdentifier ?caseId .
      FILTER(STR(?caseId) = STR(?requestedCaseId))
    }
    """
    for row in graph.query(
        q, initBindings={"requestedCaseId": Literal(case_id, datatype=XSD.string)}
    ):
        return row.case
    return None


def _raw_rule_catalog() -> list[dict[str, Any]]:
    with open(rules_path(), encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return list(raw.get("rules", [])) + list(raw.get("rule_updates", []))


def load_all_rule_versions() -> list[dict[str, Any]]:
    return _raw_rule_catalog()


def load_rules(*, include_updates: bool = True) -> list[dict[str, Any]]:
    """Legacy loader kept for metadata/tests.

    Prefer ``load_applicable_rules(assessment_time)`` for evaluation.
    """
    with open(rules_path(), encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    rules = list(raw.get("rules", []))
    if include_updates:
        updates = {r["rule_id"]: r for r in raw.get("rule_updates", [])}
        merged: dict[str, dict] = {r["rule_id"]: r for r in rules}
        merged.update(updates)
        return [merged[k] for k in sorted(merged.keys())]
    return rules


def validate_rule_configuration(catalog: list[dict[str, Any]] | None = None) -> None:
    """Validate rule metadata and non-overlapping effective windows."""
    rules = catalog if catalog is not None else _raw_rule_catalog()
    by_id: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        for key in ("rule_id", "version", "effective_from", "reason_code", "action_code", "regulatory_clause"):
            if key not in rule or rule[key] in (None, ""):
                raise RuleConfigurationError(f"Rule missing required field '{key}': {rule}")
        start = _parse_dt(rule["effective_from"])
        if start is None:
            raise RuleConfigurationError(
                f"Invalid effective_from for {rule['rule_id']} v{rule['version']}"
            )
        end = _parse_dt(rule.get("effective_to"))
        if end is not None and end < start:
            raise RuleConfigurationError(
                f"effective_to < effective_from for {rule['rule_id']} v{rule['version']}"
            )
        by_id.setdefault(str(rule["rule_id"]), []).append(rule)

    for rule_id, versions in by_id.items():
        seen_versions: set[str] = set()
        intervals: list[tuple[datetime, datetime | None, str]] = []
        for rule in versions:
            ver = str(rule["version"])
            if ver in seen_versions:
                raise RuleConfigurationError(f"Duplicate version {rule_id} v{ver}")
            seen_versions.add(ver)
            start = _parse_dt(rule["effective_from"])
            assert start is not None
            end = _parse_dt(rule.get("effective_to"))
            intervals.append((start, end, ver))

        intervals.sort(key=lambda x: x[0])
        for i in range(len(intervals)):
            s1, e1, v1 = intervals[i]
            for j in range(i + 1, len(intervals)):
                s2, e2, v2 = intervals[j]
                # Closed intervals overlap if each starts before/at the other's end
                end1 = e1 or datetime.max.replace(tzinfo=timezone.utc)
                end2 = e2 or datetime.max.replace(tzinfo=timezone.utc)
                if s1 <= end2 and s2 <= end1:
                    raise RuleConfigurationError(
                        f"Overlapping validity for {rule_id}: v{v1} and v{v2}"
                    )


def _is_applicable(rule: dict[str, Any], assessment_time: datetime) -> bool:
    start = _parse_dt(rule["effective_from"])
    end = _parse_dt(rule.get("effective_to"))
    if start is None:
        return False
    if assessment_time < start:
        return False
    if end is not None and assessment_time > end:
        return False
    return True


def load_applicable_rules(
    assessment_time: datetime,
    *,
    rule_version_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Select exactly one applicable version per rule_id for assessment_time.

    Closed interval: effective_from <= assessment_time <= effective_to
    (or open-ended when effective_to is null).
    """
    validate_rule_configuration()
    as_of = assessment_time if assessment_time.tzinfo else assessment_time.replace(
        tzinfo=timezone.utc
    )
    catalog = _raw_rule_catalog()
    overrides = rule_version_overrides or {}

    by_id: dict[str, list[dict[str, Any]]] = {}
    for rule in catalog:
        by_id.setdefault(str(rule["rule_id"]), []).append(rule)

    selected: list[dict[str, Any]] = []
    for rule_id in sorted(by_id.keys()):
        if rule_id in overrides:
            wanted = str(overrides[rule_id])
            matches = [r for r in by_id[rule_id] if str(r["version"]) == wanted]
            if len(matches) != 1:
                raise RuleConfigurationError(
                    f"Override version {rule_id} v{wanted} not found uniquely"
                )
            selected.append(matches[0])
            continue

        applicable = [r for r in by_id[rule_id] if _is_applicable(r, as_of)]
        if not applicable:
            raise RuleConfigurationError(
                f"No applicable rule version for {rule_id} at {_fmt_dt(as_of)}"
            )
        if len(applicable) > 1:
            versions = ", ".join(sorted(str(r["version"]) for r in applicable))
            raise RuleConfigurationError(
                f"Multiple applicable versions for {rule_id} at {_fmt_dt(as_of)}: {versions}"
            )
        selected.append(applicable[0])
    return selected


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
    effective_to: str | None = None
    selected_for_assessment_time: str | None = None


def collect_evidence(graph: Graph, case_id: str) -> dict[str, list[EvidenceView]]:
    """Collect evidence via MNPCase hasCaseEvidence (not IRI naming conventions)."""
    q = """
    PREFIX mnp: <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>
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
    assessment_time: datetime | None = None,
    use_updated_rules: bool | None = None,
    rule_version_overrides: dict[str, str] | None = None,
) -> list[RuleOutcome]:
    """Evaluate eligibility rules as of assessment_time.

    ``use_updated_rules`` is retained for legacy callers:
    - True / None: select by assessment_time (normal path)
    - False: force base ``rules:`` entries only (test / replay override)
    """
    as_of = assessment_time or ASSESSMENT_TIME
    as_of_str = _fmt_dt(as_of)
    evidence = collect_evidence(graph, case_id)

    if use_updated_rules is False and not rule_version_overrides:
        rules = load_rules(include_updates=False)
    else:
        rules = load_applicable_rules(
            as_of, rule_version_overrides=rule_version_overrides
        )

    outcomes: list[RuleOutcome] = []
    for rule in rules:
        etype = rule["inputs"][0]["evidence_type"]
        candidates = evidence.get(etype, [])
        usable = [e for e in candidates if e.is_usable(as_of)]
        eff_to = _fmt_dt(_parse_dt(rule.get("effective_to")))
        common = dict(
            rule_id=rule["rule_id"],
            version=str(rule["version"]),
            effective_from=str(rule["effective_from"]),
            effective_to=eff_to,
            selected_for_assessment_time=as_of_str,
            regulatory_clause=rule.get("regulatory_clause"),
        )
        if not usable:
            outcomes.append(
                RuleOutcome(
                    **common,
                    status="MISSING",
                    reason_code="MISSING_OR_EXPIRED_EVIDENCE",
                    action_code="SUPPLY_MISSING_EVIDENCE",
                    evidence_iri=candidates[0].iri if candidates else None,
                    message=f"Critical evidence {etype} missing or expired",
                )
            )
            continue
        chosen = sorted(usable, key=lambda e: e.iri)[0]
        passed = _eval_check(rule["check"], chosen, assessment_time=as_of)
        if passed:
            outcomes.append(
                RuleOutcome(
                    **common,
                    status="PASS",
                    evidence_iri=chosen.iri,
                    message="passed",
                )
            )
        else:
            outcomes.append(
                RuleOutcome(
                    **common,
                    status="FAIL",
                    reason_code=rule["reason_code"],
                    action_code=rule["action_code"],
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
    suffix = clause_id.replace("REG-MNP-CLAUSE-", "")
    return DATA[f"Clause-{suffix}"]


def rule_iri(rule_id: str, version: str) -> URIRef:
    if rule_id == "MNP-ELIG-005" and version == "1.1":
        return DATA["Rule-MNP-ELIG-005-v1-1"]
    return DATA[f"Rule-{rule_id}"]


def rule_version_iri(rule_id: str, version: str) -> URIRef:
    return DATA[f"RuleVersion-{rule_id}-{version.replace('.', '-')}"]


def action_iri(action_code: str) -> URIRef:
    return DATA[f"Action-{action_code}"]
