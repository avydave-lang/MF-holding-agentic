"""
Confidence Scorer — Phase 1 implementation.

Scoring dimensions (Phase 1):
  1. Schema completeness  — required fields present          (weight: 0.50)
  2. Type validity        — values match expected types      (weight: 0.30)
  3. Non-empty values     — no blank strings / null values   (weight: 0.20)

Phase 2 will add: outlier detection, selector coverage ratio.
"""
from __future__ import annotations

from typing import Any

from app.schemas import ConfidenceResult
from config import settings

# Fields every scrape result must contain.
REQUIRED_FIELDS: list[str] = ["product_name", "price", "url"]

# Expected Python types per field (None means any non-null value is fine).
FIELD_TYPES: dict[str, type | None] = {
    "product_name": str,
    "price": (str, int, float),
    "url": str,
}


def score(data: dict[str, Any]) -> ConfidenceResult:
    flags: list[str] = []
    dimension_scores: list[float] = []

    # --- 1. Schema completeness (0.50 weight) ---
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    completeness = 1.0 - len(missing) / len(REQUIRED_FIELDS)
    if missing:
        flags.append(f"MISSING_FIELDS:{','.join(missing)}")
    dimension_scores.append(completeness * 0.50)

    # --- 2. Type validity (0.30 weight) ---
    type_hits = 0
    type_checks = 0
    for field, expected_type in FIELD_TYPES.items():
        if field not in data:
            continue
        type_checks += 1
        if expected_type is None or isinstance(data[field], expected_type):
            type_hits += 1
        else:
            flags.append(f"TYPE_MISMATCH:{field}")
    type_score = (type_hits / type_checks) if type_checks else 1.0
    dimension_scores.append(type_score * 0.30)

    # --- 3. Non-empty values (0.20 weight) ---
    nonempty_hits = 0
    nonempty_checks = 0
    for field in REQUIRED_FIELDS:
        if field not in data:
            continue
        nonempty_checks += 1
        val = data[field]
        if val is not None and str(val).strip() != "":
            nonempty_hits += 1
        else:
            flags.append(f"EMPTY_VALUE:{field}")
    nonempty_score = (nonempty_hits / nonempty_checks) if nonempty_checks else 1.0
    dimension_scores.append(nonempty_score * 0.20)

    total = sum(dimension_scores)

    if total >= settings.confidence_accept:
        routing = "accept"
    elif total >= settings.confidence_flag:
        routing = "flag"
    else:
        routing = "reject"

    return ConfidenceResult(score=round(total, 4), routing=routing, flags=flags)
