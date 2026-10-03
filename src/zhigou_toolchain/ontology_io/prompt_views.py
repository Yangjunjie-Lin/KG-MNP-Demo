"""Lossless research prompt views; no truncation, new IRIs, or score access."""
from __future__ import annotations

from copy import deepcopy

from zhigou_toolchain.contracts.canonical import semantic_hash

GUIDE = (" Context encoding: cards with COLUMNAR_CARDS_V1 represent complete cards: combine shared_fields with columns/rows for each card. "
    "card_index and existing_card_index are zero-based references to those card rows. "
    "Apply shared_row_fields to each retrieval row and shared_candidate_fields to each exact hit. "
    "An existing_card_index represents cards[index].iri; all original terms, scores and reasons remain supplied.")


def compact_cards(cards):
    if not cards or any(set(card) != set(cards[0]) for card in cards):
        return deepcopy(cards)
    common = {key: deepcopy(cards[0][key]) for key in cards[0] if all(card[key] == cards[0][key] for card in cards)}
    columns = sorted(set(cards[0]) - set(common))
    return {"encoding": "COLUMNAR_CARDS_V1", "shared_fields": common, "columns": columns,
        "rows": [[deepcopy(card[key]) for key in columns] for card in cards]}


def expand_cards(packed):
    if isinstance(packed, list):
        return deepcopy(packed)
    if (packed.get("encoding") != "COLUMNAR_CARDS_V1" or len(packed["columns"]) != len(set(packed["columns"]))
            or set(packed["columns"]) & set(packed["shared_fields"])):
        raise ValueError("INVALID_CARD_CATALOG_ENCODING")
    if any(len(row) != len(packed["columns"]) for row in packed["rows"]):
        raise ValueError("INVALID_CARD_CATALOG_ROW")
    return [{**deepcopy(packed["shared_fields"]), **dict(zip(packed["columns"], deepcopy(row), strict=True))} for row in packed["rows"]]


def compact_retrieval(cards, retrieval):
    if not retrieval:
        return []
    indexes = {semantic_hash(card): i for i, card in enumerate(cards)}
    common_rows = {}
    if all(row.get("method") == retrieval[0].get("method") and "method" in row for row in retrieval):
        common_rows["method"] = deepcopy(retrieval[0]["method"])
    hits = [hit for row in retrieval for hit in row["exact"]]
    common_hits = {key: deepcopy(hits[0][key]) for key in ("sources", "vector_score")
        if hits and key in hits[0] and all(key in hit and hit[key] == hits[0][key] for hit in hits)}
    rows = []
    for row in retrieval:
        packed = {key: deepcopy(value) for key, value in row.items() if key not in common_rows and key != "exact"}
        packed["exact"] = []
        for hit in row["exact"]:
            digest = semantic_hash(hit["card"])
            if digest not in indexes or "card_index" in hit:
                raise ValueError("RETRIEVAL_CARD_NOT_IN_FROZEN_CATALOG_OR_REFERENCE_COLLISION")
            packed["exact"].append({**{key: deepcopy(value) for key, value in hit.items() if key not in common_hits and key != "card"},
                "card_index": indexes[digest]})
        rows.append(packed)
    return {"encoding": "LOSSLESS_CARD_INDEX_V1", "index_base": 0,
        "shared_row_fields": common_rows, "shared_candidate_fields": common_hits, "rows": rows}


def expand_retrieval(cards, packed):
    """Offline integrity check; never queries a model or a reference answer."""
    if packed == []:
        return []
    cards = expand_cards(cards)
    if packed.get("encoding") != "LOSSLESS_CARD_INDEX_V1" or packed.get("index_base") != 0:
        raise ValueError("UNKNOWN_RETRIEVAL_ENCODING")
    rows = []
    for row in packed["rows"]:
        decoded = {**deepcopy(packed["shared_row_fields"]), **{key: deepcopy(value) for key, value in row.items() if key != "exact"}}
        decoded["exact"] = []
        for hit in row["exact"]:
            index = hit["card_index"]
            if type(index) is not int or not 0 <= index < len(cards):
                raise ValueError("INVALID_RETRIEVAL_CARD_INDEX")
            decoded["exact"].append({**deepcopy(packed["shared_candidate_fields"]),
                **{key: deepcopy(value) for key, value in hit.items() if key != "card_index"}, "card": deepcopy(cards[index])})
        rows.append(decoded)
    return rows


def context_view(cards, content):
    if "cards" in content and content["cards"] != cards:
        raise ValueError("CONTEXT_CARD_CATALOG_CHANGED")
    result = deepcopy(content)
    changed = False
    for field in ("retrieval", "retrieval_context"):
        if content.get(field):
            result[field] = compact_retrieval(cards, content[field])
            if expand_retrieval(cards, result[field]) != content[field]:
                raise ValueError("LOSSLESS_RETRIEVAL_ROUNDTRIP_FAILED")
            result["cards"] = deepcopy(cards)
            changed = True
    if changed and isinstance(result.get("reuse"), dict):
        by_iri = {card["iri"]: index for index, card in enumerate(cards)}
        for row in result["reuse"].get("decisions", []):
            if row.get("existing_iri") is not None:
                if row["existing_iri"] not in by_iri or "existing_card_index" in row:
                    raise ValueError("REUSE_REFERENCE_NOT_IN_FROZEN_CATALOG")
                row["existing_card_index"] = by_iri[row.pop("existing_iri")]
    if changed:
        result["cards"] = compact_cards(cards)
        if expand_cards(result["cards"]) != cards:
            raise ValueError("LOSSLESS_CARD_CATALOG_ROUNDTRIP_FAILED")
    return result, changed
