"""Convert normalized JSON case input into an RDF instance graph."""

from __future__ import annotations

import re

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from kg_mnp_demo.input_adapter import EvidenceInput, NormalizedCaseInput
from kg_mnp_demo.namespaces import DATA, DATA_BASE, MNP

SOURCE_SYSTEM_IRIS = {
    "CRM": DATA["SYS-CRM"],
    "HLR": DATA["SYS-HLR"],
    "BILLING": DATA["SYS-BILLING"],
    "CONTRACT": DATA["SYS-CONTRACT"],
    "MNP_HISTORY": DATA["SYS-MNP"],
}


def sanitize_iri_fragment(value: str) -> str:
    """Deterministic IRI-safe fragment (no random UUIDs)."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_")
    if not cleaned:
        raise ValueError(f"Cannot build IRI fragment from empty value: {value!r}")
    return cleaned


def case_iri(case_id: str) -> URIRef:
    return URIRef(f"{DATA_BASE}Case-{sanitize_iri_fragment(case_id)}")


def subscriber_iri(subscriber_id: str) -> URIRef:
    return URIRef(f"{DATA_BASE}Subscriber-{sanitize_iri_fragment(subscriber_id)}")


def phone_iri(case_id: str) -> URIRef:
    return URIRef(f"{DATA_BASE}Phone-{sanitize_iri_fragment(case_id)}")


def account_iri(account_id: str) -> URIRef:
    return URIRef(f"{DATA_BASE}Account-{sanitize_iri_fragment(account_id)}")


def subscription_iri(case_id: str) -> URIRef:
    return URIRef(f"{DATA_BASE}Subscription-{sanitize_iri_fragment(case_id)}")


def evidence_iri(case_id: str, kind: str) -> URIRef:
    return URIRef(
        f"{DATA_BASE}Evidence-{sanitize_iri_fragment(case_id)}-{sanitize_iri_fragment(kind)}"
    )


def source_system_iri(system_id: str) -> URIRef:
    if system_id in SOURCE_SYSTEM_IRIS:
        return SOURCE_SYSTEM_IRIS[system_id]
    return URIRef(f"{DATA_BASE}SYS-{sanitize_iri_fragment(system_id)}")


def _dt(literal_dt) -> Literal:
    return Literal(literal_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), datatype=XSD.dateTime)


def _add_evidence_base(
    g: Graph,
    ev_uri: URIRef,
    *,
    evidence_type: str,
    evidence: EvidenceInput,
) -> None:
    g.add((ev_uri, RDF.type, MNP.SystemObservation))
    g.add((ev_uri, MNP.evidenceType, Literal(evidence_type)))
    g.add((ev_uri, MNP.evidenceStatus, Literal(evidence.status)))
    g.add((ev_uri, MNP.evidenceGeneratedAt, _dt(evidence.generated_at)))
    g.add((ev_uri, MNP.evidenceValidUntil, _dt(evidence.valid_until)))
    sys_uri = source_system_iri(evidence.source_system)
    g.add((ev_uri, MNP.hasSourceSystem, sys_uri))
    # Ensure source system node exists even if reference data is later merged
    g.add((sys_uri, RDF.type, MNP.InformationSystem))
    g.add((sys_uri, MNP.systemIdentifier, Literal(evidence.source_system)))


def build_case_graph(
    normalized: NormalizedCaseInput,
    *,
    process: dict | None = None,
) -> Graph:
    """Build instance RDF only (no assessment, no eligibility conclusion)."""
    from typing import Any

    g = Graph()
    g.bind("mnp", MNP)

    case_id = normalized.case_id
    case = case_iri(case_id)
    subscriber = subscriber_iri(normalized.subscriber_id)
    phone = phone_iri(case_id)
    account = account_iri(normalized.account_id)

    g.add((subscriber, RDF.type, MNP.Subscriber))
    subscription = subscription_iri(case_id)
    g.add((subscriber, MNP.holdsSubscription, subscription))
    g.add((subscription, RDF.type, MNP.ServiceSubscription))
    g.add((subscription, MNP.billedThrough, account))
    g.add((phone, RDF.type, MNP.PhoneNumber))
    g.add((phone, MNP.assignedToSubscription, subscription))
    g.add((phone, MNP.maskedPhoneNumber, Literal(normalized.masked_number)))

    g.add((account, RDF.type, MNP.TelecomAccount))

    g.add((case, RDF.type, MNP.MNPCase))
    g.add((case, MNP.caseIdentifier, Literal(case_id)))
    g.add((case, MNP.requestedBy, subscriber))
    g.add((case, MNP.concernsNumber, phone))

    ev_id = evidence_iri(case_id, "IDENTITY")
    ev_num = evidence_iri(case_id, "NUMBER")
    ev_bill = evidence_iri(case_id, "BILLING")
    ev_ctr = evidence_iri(case_id, "CONTRACT")
    ev_port = evidence_iri(case_id, "PORTING")

    _add_evidence_base(
        g, ev_id, evidence_type="IDENTITY_MATCH", evidence=normalized.identity
    )
    g.add((ev_id, MNP.identityMatchFlag, Literal(normalized.identity.matched)))

    _add_evidence_base(
        g, ev_num, evidence_type="NUMBER_STATUS", evidence=normalized.number_status
    )
    g.add(
        (
            ev_num,
            MNP.numberStatusCode,
            Literal(normalized.number_status.status_code),
        )
    )

    _add_evidence_base(
        g, ev_bill, evidence_type="BILLING_BALANCE", evidence=normalized.billing
    )
    g.add(
        (
            ev_bill,
            MNP.observedAmount,
            Literal(normalized.billing.outstanding_amount, datatype=XSD.decimal),
        )
    )
    g.add((ev_bill, MNP.currencyCode, Literal(normalized.billing.currency)))
    g.add(
        (
            ev_bill,
            MNP.hasPaymentArrangement,
            Literal(normalized.billing.has_payment_arrangement),
        )
    )

    _add_evidence_base(
        g, ev_ctr, evidence_type="CONTRACT_STATUS", evidence=normalized.contract
    )
    g.add(
        (
            ev_ctr,
            MNP.contractStatusCode,
            Literal(normalized.contract.contract_status),
        )
    )
    if normalized.contract.contract_end_time is not None:
        g.add((ev_ctr, MNP.contractEndTime, _dt(normalized.contract.contract_end_time)))

    _add_evidence_base(
        g,
        ev_port,
        evidence_type="PORTING_HISTORY",
        evidence=normalized.porting_history,
    )
    g.add(
        (
            ev_port,
            MNP.daysSinceLastPort,
            Literal(normalized.porting_history.days_since_last_port),
        )
    )

    for ev in (ev_id, ev_num, ev_bill, ev_ctr, ev_port):
        g.add((case, MNP.hasCaseEvidence, ev))
        g.add((ev, MNP.evidenceForCase, case))

    _add_process_triples(g, case, case_id, process)
    return g


def _add_process_triples(
    g: Graph,
    case: URIRef,
    case_id: str,
    process: dict | None,
) -> None:
    if not process:
        return
    step_code = process.get("current_step")
    if step_code:
        step = URIRef(f"{DATA_BASE}Step-{sanitize_iri_fragment(case_id)}-{sanitize_iri_fragment(str(step_code))}")
        g.add((step, RDF.type, MNP.ProcessStep))
        g.add((step, MNP.stepCode, Literal(str(step_code))))
        g.add((case, MNP.hasProcessStep, step))
        g.add((case, MNP.currentProcessStep, step))

    auth = process.get("authorization_code")
    if isinstance(auth, dict):
        code = URIRef(f"{DATA_BASE}AuthCode-{sanitize_iri_fragment(case_id)}")
        g.add((code, RDF.type, MNP.AuthorizationCode))
        if auth.get("status"):
            g.add((code, MNP.authCodeStatus, Literal(str(auth["status"]))))
        if auth.get("issued_at"):
            g.add(
                (
                    code,
                    MNP.authCodeIssuedAt,
                    Literal(str(auth["issued_at"]).replace("+00:00", "Z"), datatype=XSD.dateTime),
                )
            )
        if auth.get("valid_until"):
            g.add(
                (
                    code,
                    MNP.authCodeValidUntil,
                    Literal(str(auth["valid_until"]).replace("+00:00", "Z"), datatype=XSD.dateTime),
                )
            )
        if auth.get("masked_value"):
            g.add((code, MNP.authCodeValueMasked, Literal(str(auth["masked_value"]))))
        g.add((case, MNP.hasAuthorizationCode, code))

        # Process event for expired/missing auth
        status = str(auth.get("status") or "").upper()
        if status in {"EXPIRED", "MISSING"}:
            ev = URIRef(f"{DATA_BASE}ProcessEvent-{sanitize_iri_fragment(case_id)}-AUTH")
            g.add((ev, RDF.type, MNP.ProcessEvent))
            g.add((ev, MNP.eventTypeCode, Literal(f"AUTHORIZATION_CODE_{status}")))
            when = auth.get("valid_until") or auth.get("issued_at") or "2026-07-01T00:00:00Z"
            g.add(
                (
                    ev,
                    MNP.eventTime,
                    Literal(str(when).replace("+00:00", "Z"), datatype=XSD.dateTime),
                )
            )
            g.add((case, MNP.hasProcessEvent, ev))

    term = process.get("termination_agreement")
    if isinstance(term, dict):
        agreement = URIRef(f"{DATA_BASE}Termination-{sanitize_iri_fragment(case_id)}")
        g.add((agreement, RDF.type, MNP.TerminationAgreement))
        if term.get("signed_at"):
            g.add(
                (
                    agreement,
                    MNP.terminationSignedAt,
                    Literal(str(term["signed_at"]).replace("+00:00", "Z"), datatype=XSD.dateTime),
                )
            )
        if term.get("effective_at"):
            g.add(
                (
                    agreement,
                    MNP.terminationEffectiveAt,
                    Literal(str(term["effective_at"]).replace("+00:00", "Z"), datatype=XSD.dateTime),
                )
            )
        if term.get("status"):
            g.add((agreement, MNP.terminationStatusCode, Literal(str(term["status"]))))
