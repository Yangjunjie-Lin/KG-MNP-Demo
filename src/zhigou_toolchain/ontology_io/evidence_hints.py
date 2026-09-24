"""Source-only locator diagnostics for repair; never alters model predictions."""
from __future__ import annotations

import re

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.tools import bind_quote


def quote_location_hints(text, evidence, chunks, issues, *, max_hints=8, max_matches=4):
    """Exact Unicode offsets from the same frozen source, not expected facts.

    Bounded optional diagnostics leave every original issue and raw response
    intact. Ambiguous and absent quotes stay ambiguous/absent. Hints do not
    grant a binding: the next model proposal must pass the original validator.
    """
    if not 1 <= max_hints <= 8 or not 1 <= max_matches <= 4:
        raise ValueError("LOCATOR_DIAGNOSTIC_BOUND_INVALID")
    targets = {row["triple_index"] for row in issues if row["code"] == "EVIDENCE_QUOTE_UNBOUND"}
    eligible = [(index, row) for index, row in enumerate(evidence) if row["triple_index"] in targets]
    hints = []
    for index, row in eligible[:max_hints]:
        quote = row["quote"]
        starts = [match.start() for match in re.finditer(re.escape(quote), text)] if quote else []
        positions = []
        for start in starts:
            if len(positions) >= max_matches:
                break
            for chunk in chunks:
                if chunk["start"] <= start and start + len(quote) <= chunk["end"]:
                    bound = bind_quote(text, chunk, quote, expected_start=start)
                    positions.append({"start": bound["start"], "end": bound["end"]})
                    break
        hints.append({"triple_index": row["triple_index"], "evidence_index": index, "proposed_start": row.get("start"),
            "quote_preview": quote[:160], "preview_is_complete_quote": len(quote) <= 160,
            "exact_source_match_count": len(starts), "verified_position_candidates": positions,
            "candidates_limited_or_outside_chunks": len(positions) < len(starts)})
    return {"authority": "SOURCE_LOCATION_ONLY_NOT_GOLD_OR_ENTAILMENT", "position_unit": "UNICODE_CODE_POINT_HALF_OPEN",
        "text_hash": semantic_hash(text), "hints": hints, "omitted_diagnostic_count": max(0, len(eligible) - len(hints)),
        "raw_prediction_and_evidence_unchanged": True}
