"""
AI Matching Engine
==================

This is the transparent scoring system described in the product spec.
It is NOT a black box and NOT randomly generated -- every factor is computed
from real fields on the two reports being compared, and the final score is a
weighted average of only the factors that actually have data on BOTH sides.

Factors & base weights (sum to 1.0):
    text similarity            0.30
    category similarity        0.15
    brand/model similarity     0.15
    color similarity           0.10
    distinguishing features    0.15
    location proximity         0.10
    date/time proximity        0.05

Missing-data handling
----------------------
If a factor can't be computed for a given pair (e.g. one report has no
brand filled in), that factor is EXCLUDED from the average and its weight is
redistributed proportionally across the remaining available factors, rather
than counting it as a mismatch (score 0). This matches the requirement:
"If some information is missing, dynamically adjust the weighting instead of
treating missing data as a mismatch."

The output is always labeled as an "AI Match Score" (not a scientific
probability), alongside a factor-by-factor breakdown and plain-English
"why this may match" reasons for the UI.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from math import radians, sin, cos, sqrt, atan2
from typing import Optional

from app.config import settings
from app.matching.text_similarity import get_text_similarity_engine

# Simple synonym groups so "laptop" and "notebook" etc. are recognized as the
# same category without needing an external taxonomy service.
CATEGORY_SYNONYMS = [
    {"laptop", "notebook", "macbook", "chromebook", "computer"},
    {"phone", "mobile", "smartphone", "cellphone", "iphone"},
    {"wallet", "purse", "billfold"},
    {"id card", "identity card", "id", "student id", "license", "driver's license"},
    {"bag", "backpack", "handbag", "rucksack", "bagpack", "satchel"},
    {"keys", "key", "keychain"},
    {"headphones", "earphones", "earbuds", "airpods"},
    {"watch", "smartwatch"},
    {"documents", "papers", "folder", "notebook (paper)"},
]


@dataclass
class ReportFields:
    """Minimal view of a report's fields needed for matching -- keeps the
    engine decoupled from the SQLAlchemy model so it's easy to unit test."""
    item_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    distinguishing_features: Optional[str] = None
    location_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_time: Optional[datetime] = None
    image_features: Optional[dict] = None


FACTOR_DEFS = [
    # (key, label, base_weight)
    ("text", "Description similarity", settings.WEIGHT_TEXT),
    ("category", "Item category", settings.WEIGHT_CATEGORY),
    ("brand", "Brand / model", settings.WEIGHT_BRAND),
    ("color", "Color", settings.WEIGHT_COLOR),
    ("features", "Distinguishing features", settings.WEIGHT_FEATURES),
    ("location", "Location proximity", settings.WEIGHT_LOCATION),
    ("date", "Date/time proximity", settings.WEIGHT_DATE),
]


def _normalize(text: Optional[str]) -> str:
    return (text or "").strip().lower()


def _fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _category_match_score(cat_a: str, cat_b: str) -> float:
    if not cat_a or not cat_b:
        return 0.0
    if cat_a == cat_b:
        return 1.0
    for group in CATEGORY_SYNONYMS:
        if cat_a in group and cat_b in group:
            return 0.95
    return _fuzzy_ratio(cat_a, cat_b)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def compute_match(lost: ReportFields, found: ReportFields) -> dict:
    """Returns {score: float(0-100), factors: [...], reasons: [...]}"""
    text_engine = get_text_similarity_engine()
    factors: list[dict] = []
    reasons: list[str] = []

    # --- 1. Text / description similarity -------------------------------
    text_a = " ".join(filter(None, [lost.item_name, lost.description]))
    text_b = " ".join(filter(None, [found.item_name, found.description]))
    if text_a.strip() and text_b.strip():
        score = text_engine.similarity(text_a, text_b)
        factors.append(_factor("text", score, f"Similarity engine: {text_engine.mode}"))
        if score >= 0.55:
            reasons.append("Descriptions are semantically similar")
    else:
        factors.append(_factor("text", None, "Not enough text on one or both reports"))

    # --- 2. Category similarity ------------------------------------------
    cat_a, cat_b = _normalize(lost.category or lost.item_name), _normalize(found.category or found.item_name)
    if cat_a and cat_b:
        score = _category_match_score(cat_a, cat_b)
        factors.append(_factor("category", score, f"'{cat_a}' vs '{cat_b}'"))
        if score >= 0.9:
            reasons.append(f"Same item category: {lost.category or lost.item_name}")
        elif score >= 0.6:
            reasons.append("Similar item category")
    else:
        factors.append(_factor("category", None, "Category missing on one or both reports"))

    # --- 3. Brand / model similarity --------------------------------------
    brand_a, brand_b = _normalize(lost.brand), _normalize(found.brand)
    model_a, model_b = _normalize(lost.model), _normalize(found.model)
    if brand_a or model_a or brand_b or model_b:
        sub_scores = []
        if brand_a and brand_b:
            sub_scores.append(1.0 if brand_a == brand_b else _fuzzy_ratio(brand_a, brand_b))
        if model_a and model_b:
            sub_scores.append(1.0 if model_a == model_b else _fuzzy_ratio(model_a, model_b))
        if sub_scores:
            score = sum(sub_scores) / len(sub_scores)
            factors.append(_factor("brand", score, f"Brand '{lost.brand}' vs '{found.brand}'"))
            if brand_a and brand_b and brand_a == brand_b:
                reasons.append(f"Same brand: {lost.brand}")
        else:
            factors.append(_factor("brand", None, "Brand/model missing on one side"))
    else:
        factors.append(_factor("brand", None, "No brand/model info provided"))

    # --- 4. Color similarity ----------------------------------------------
    color_a = _normalize(lost.color) or _normalize(
        (lost.image_features or {}).get("dominant_color") if lost.image_features else None
    )
    color_b = _normalize(found.color) or _normalize(
        (found.image_features or {}).get("dominant_color") if found.image_features else None
    )
    if color_a and color_b:
        score = 1.0 if color_a == color_b else _fuzzy_ratio(color_a, color_b)
        factors.append(_factor("color", score, f"'{color_a}' vs '{color_b}'"))
        if color_a == color_b:
            reasons.append(f"Same color: {color_a.title()}")
    else:
        factors.append(_factor("color", None, "Color not specified/detected on one or both"))

    # --- 5. Distinguishing features ----------------------------------------
    feat_a, feat_b = lost.distinguishing_features, found.distinguishing_features
    if feat_a and feat_b:
        score = text_engine.similarity(feat_a, feat_b)
        factors.append(_factor("features", score, "Compared free-text distinguishing features"))
        if score >= 0.5:
            reasons.append("Descriptions contain similar distinguishing features")
    else:
        factors.append(_factor("features", None, "Distinguishing features missing on one or both"))

    # --- 6. Location proximity ---------------------------------------------
    if lost.latitude is not None and lost.longitude is not None and \
       found.latitude is not None and found.longitude is not None:
        dist_km = _haversine_km(lost.latitude, lost.longitude, found.latitude, found.longitude)
        # Full score within 200m, linearly decaying to 0 by 5km
        score = max(0.0, min(1.0, 1 - (dist_km - 0.2) / 4.8)) if dist_km > 0.2 else 1.0
        factors.append(_factor("location", score, f"~{dist_km:.2f} km apart"))
        if score >= 0.8:
            reasons.append("Locations are very close")
        elif score >= 0.4:
            reasons.append("Locations are nearby")
    elif lost.location_text and found.location_text:
        score = _fuzzy_ratio(_normalize(lost.location_text), _normalize(found.location_text))
        factors.append(_factor("location", score, f"'{lost.location_text}' vs '{found.location_text}'"))
        if score >= 0.6:
            reasons.append("Locations are nearby")
    else:
        factors.append(_factor("location", None, "Location data missing on one or both"))

    # --- 7. Date/time proximity ---------------------------------------------
    if lost.event_time and found.event_time:
        hours_diff = abs((lost.event_time - found.event_time).total_seconds()) / 3600.0
        # Full score if within 2 hours, decaying to 0 by 72 hours (3 days)
        score = max(0.0, min(1.0, 1 - max(0.0, hours_diff - 2) / 70))
        factors.append(_factor("date", score, f"{hours_diff:.1f} hours apart"))
        if score >= 0.7:
            reasons.append("Reported at close to the same time")
    else:
        factors.append(_factor("date", None, "Date/time missing on one or both"))

    # --- Weighted aggregation with dynamic re-normalization ----------------
    available = [f for f in factors if f["available"]]
    total_base_weight = sum(f["weight_base"] for f in available)
    if total_base_weight <= 0 or not available:
        final_score = 0.0
    else:
        weighted_sum = 0.0
        for f in available:
            effective_weight = f["weight_base"] / total_base_weight
            f["weight_effective"] = round(effective_weight, 4)
            weighted_sum += effective_weight * (f["score"] or 0.0)
        final_score = round(weighted_sum * 100, 1)

    if not reasons:
        if final_score >= 50:
            reasons.append("Overall profile similarity across available fields")
        else:
            reasons.append("Limited overlapping information between the two reports")

    return {"score": final_score, "factors": factors, "reasons": reasons}


def _factor(key: str, score: Optional[float], detail: str) -> dict:
    label = next(l for k, l, _ in FACTOR_DEFS if k == key)
    base_weight = next(w for k, _, w in FACTOR_DEFS if k == key)
    return {
        "factor": key,
        "label": label,
        "available": score is not None,
        "weight_base": base_weight,
        "weight_effective": 0.0,  # filled in during aggregation
        "score": score,
        "detail": detail,
    }


def report_to_fields(report) -> ReportFields:
    """Adapts a SQLAlchemy Report row into the engine's plain dataclass."""
    return ReportFields(
        item_name=report.item_name,
        category=report.category,
        description=report.description,
        brand=report.brand,
        model=report.model,
        color=report.color,
        distinguishing_features=report.distinguishing_features,
        location_text=report.location_text,
        latitude=report.latitude,
        longitude=report.longitude,
        event_time=report.event_time,
        image_features=report.image_features,
    )
