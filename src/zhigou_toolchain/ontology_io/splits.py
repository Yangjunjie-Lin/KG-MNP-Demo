"""Public-only cross-task source/near-duplicate grouping before any scoring.

This is a local preregistered split, not the shared task's hidden test split.
All related records are retained; grouping never discards a difficult sample.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from zhigou_toolchain.contracts.canonical import semantic_hash


def normalize_document(text):
    return " ".join(text.casefold().split())


def group_public_documents(records, *, threshold=.85):
    """records contain only id/text/source; no ontology or reference answers.

    Connected components of identical public source IDs/text and >=.85 token
    5-shingle Jaccard. Exhaustive candidate recall via a shared-shingle index;
    this detects lexical near duplicates, NOT semantic paraphrases.
    """
    if not 0 < threshold <= 1:
        raise ValueError("INVALID_NEAR_DUPLICATE_THRESHOLD")
    if len({r["key"] for r in records}) != len(records):
        raise ValueError("DUPLICATE_PUBLIC_RECORD_KEY")
    parent = list(range(len(records)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[root(i)] = root(j)

    texts, sources, index, shingles, links = {}, {}, defaultdict(set), [], []
    for i, row in enumerate(records):
        text = normalize_document(row["text"])
        digest = hashlib.sha256(text.encode()).hexdigest()
        source = row.get("source")
        for kind, key, lookup in (("EXACT_TEXT", digest, texts), ("PUBLIC_SOURCE_ID", source, sources)):
            if key and key in lookup:
                j = lookup[key]
                union(i, j)
                links.append({"left": records[j]["key"], "right": row["key"], "reason": kind})
            elif key:
                lookup[key] = i
        tokens = re.findall(r"\w+", text)
        pieces = {tuple(tokens[n:n + 5]) for n in range(max(0, len(tokens) - 4))}
        candidates = set().union(*(index[s] for s in pieces)) if pieces else set()
        for j in sorted(candidates):
            other = shingles[j]
            if root(i) == root(j) or min(len(other), len(pieces)) < threshold * max(len(other), len(pieces)):
                continue
            score = len(pieces & other) / len(pieces | other)
            if score >= threshold:
                union(i, j)
                links.append({"left": records[j]["key"], "right": row["key"], "reason": "TOKEN_5_SHINGLE_JACCARD", "similarity": score})
        shingles.append(pieces)
        for piece in pieces:
            index[piece].add(i)
    components = defaultdict(list)
    for i, row in enumerate(records):
        components[root(i)].append(row["key"])
    groups = {key: semantic_hash(sorted(keys)) for keys in components.values() for key in keys}
    return {"groups": groups, "links": links, "independent_groups": len(components),
        "policy": "PUBLIC_SOURCE_OR_EXACT_TEXT_OR_TOKEN5_JACCARD_CONNECTED_COMPONENT_V1", "threshold": threshold,
        "limitation": "Lexical near duplicates only; missing source metadata and semantic paraphrases remain unverified"}


def phase_for_group(group):
    # Frozen BEFORE scores: 10% smoke, 10% independent pilot, 80% full local
    # holdout. No development on full; seed replicates never create new groups.
    fold = int(group[:16], 16) % 10
    return "smoke" if fold == 0 else "pilot" if fold == 1 else "full"
