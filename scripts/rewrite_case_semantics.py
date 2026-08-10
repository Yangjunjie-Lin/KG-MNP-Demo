#!/usr/bin/env python3
"""Rewrite legacy case TTL for Stage 03 semantic model + formal IRIs."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERM = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"
DATA = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/"

HEADER = f"""@prefix mnp: <{TERM}> .
@prefix data: <{DATA}> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""


def rewrite_case(text: str) -> str:
    # Strip old prefixes
    text = re.sub(r"^@prefix[^\n]+\n", "", text, flags=re.M)
    text = text.strip() + "\n"

    # Individual IRIs: mnp:Name -> data:Name for non-type local names used as subjects
    # Keep property/class refs as mnp:
    # Convert common instance locals
    instance_locals = set(re.findall(r"\bmnp:((?:Sub|Phone|Acct|Subscr|Contract|CASE|Ev|Svc|Auth|Term)-[A-Za-z0-9_-]+)", text))
    instance_locals |= set(re.findall(r"\bmnp:((?:SYS|RULE|CLAUSE|DOC|ACTION|RV)-[A-Za-z0-9_-]+)", text))
    # Also plain CASE-0N, Sub-0N patterns already covered

    for loc in sorted(instance_locals, key=len, reverse=True):
        text = re.sub(rf"\bmnp:{re.escape(loc)}\b", f"data:{loc}", text)

    # Semantic property migrations on subscriber blocks
    text = text.replace("mnp:ownsPhoneNumber", "mnp:_REMOVED_ownsPhoneNumber")
    text = text.replace("mnp:hasSubscription", "mnp:holdsSubscription")
    text = text.replace("mnp:relatedAccount", "mnp:_REMOVED_relatedAccount")

    # Remove deprecated triples
    text = re.sub(r"^\s*mnp:_REMOVED_ownsPhoneNumber[^\n]*\n", "", text, flags=re.M)
    text = re.sub(r"^\s*mnp:_REMOVED_relatedAccount[^\n]*\n", "", text, flags=re.M)

    # Move billedThrough from Subscriber to ServiceSubscription:
    # Pattern: subscriber has billedThrough X and holdsSubscription Y -> add Y billedThrough X, remove from subscriber
    # Simpler approach: if subscriber still has billedThrough, relocate.
    def relocate_billing(block: str) -> str:
        m_bill = re.search(r"mnp:billedThrough\s+(data:\S+)\s*;", block)
        m_sub = re.search(r"mnp:holdsSubscription\s+(data:\S+)\s*;", block)
        if m_bill and m_sub and "a mnp:Subscriber" in block:
            bill_t = m_bill.group(0)
            block = block.replace(bill_t, "")
            # store for later
            block = block.replace(
                "___BILLING_HINT___",
                "",
            )
            block += f"\n#BILLING:{m_sub.group(1)}->{m_bill.group(1)}\n"
        return block

    # Split by blank-line-ish turtle subjects is hard; do line-based pass
    billing_moves: list[tuple[str, str]] = []
    lines = text.splitlines()
    is_subscriber = False
    subscr = None
    bill = None
    out_lines: list[str] = []
    for line in lines:
        subj_m = re.match(r"^(data:\S+)\s+a\s+mnp:(\w+)", line)
        if subj_m:
            # flush previous subscriber billing
            if is_subscriber and subscr and bill:
                billing_moves.append((subscr, bill))
            is_subscriber = subj_m.group(2) == "Subscriber"
            subscr = None
            bill = None
        if is_subscriber:
            m = re.search(r"mnp:holdsSubscription\s+(data:\S+)", line)
            if m:
                subscr = m.group(1)
            m = re.search(r"mnp:billedThrough\s+(data:\S+)", line)
            if m:
                bill = m.group(1)
                # skip this line (remove from subscriber)
                continue
        out_lines.append(line)
    if is_subscriber and subscr and bill:
        billing_moves.append((subscr, bill))
    text = "\n".join(out_lines) + "\n"

    # Add billedThrough and assignedToSubscription on subscriptions / phones
    for subscr_iri, bill_iri in billing_moves:
        # Find subscription block and inject billedThrough if missing
        if f"{subscr_iri} a mnp:ServiceSubscription" in text and f"{subscr_iri}" in text:
            text = re.sub(
                rf"({re.escape(subscr_iri)} a mnp:ServiceSubscription\s*;)",
                rf"\1\n    mnp:billedThrough {bill_iri} ;",
                text,
                count=1,
            )

    # assignedToSubscription: PhoneNumber <- from subscriber holdsSubscription + phone via case concerns
    # For each Subscriber with holdsSubscription S, find owns-removed phone via concernsNumber on case requestedBy same subscriber
    # Simpler: for each ServiceSubscription Subscr-NN and Phone-NN with same suffix, link phone assignedToSubscription
    for m in re.finditer(r"data:Subscr-(\d+)", text):
        n = m.group(1)
        phone = f"data:Phone-{n}"
        subscr = f"data:Subscr-{n}"
        if phone in text and f"{phone} a mnp:PhoneNumber" in text:
            if "mnp:assignedToSubscription" not in text.split(f"{phone} a mnp:PhoneNumber")[1][:400]:
                text = re.sub(
                    rf"({re.escape(phone)} a mnp:PhoneNumber\s*;)",
                    rf"\1\n    mnp:assignedToSubscription {subscr} ;",
                    text,
                    count=1,
                )

    # Clean double spaces / empty property lines
    text = re.sub(r";\s*;", ";", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return HEADER + "\n" + text.lstrip()


def main() -> int:
    data_dir = ROOT / "data"
    for path in sorted(data_dir.glob("*.ttl")):
        original = path.read_text(encoding="utf-8")
        # First do simple namespace replace if still old
        text = original.replace("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#", TERM)
        updated = rewrite_case(text)
        path.write_text(updated, encoding="utf-8", newline="\n")
        print(f"rewrote {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
