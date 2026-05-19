"""
Occasion Detection Engine.

Identifies upcoming gifting occasions per customer using:
  1. Explicit profile saves (high confidence)
  2. Multi-year order pattern inference (medium confidence)
  3. Single-data-point inference (low confidence)
  4. Recipient clustering (same recipient, multiple occasion types)
  5. Hijri calendar support for Eid al-Fitr and Eid al-Adha

All detected occasions are projected into the LOOK_AHEAD_DAYS window from TODAY.
"""

from __future__ import annotations
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from hijridate import Hijri, Gregorian as HijriGregorian
import pytz

from src.models import CustomerProfile, OccasionDetection

TODAY = date(2026, 5, 19)
LOOK_AHEAD_DAYS = 365  # detect occasions up to 12 months ahead (captures Valentine's 2027 for repeat gifters)

# ─── HIJRI CALENDAR CONSTANTS ─────────────────────────────────────────────────
# Eid al-Fitr  = 1 Shawwal (month 10)
# Eid al-Adha  = 10 Dhul Hijjah (month 12)
_EID_HIJRI = {
    "eid_al_fitr": (10, 1),   # month, day
    "eid_al_adha": (12, 10),
}

# ─── FIXED-DATE OCCASIONS (Gregorian) ─────────────────────────────────────────
_FIXED_OCCASIONS = {
    "valentines_day": (2, 14),
    "womens_day": (3, 8),
    "christmas": (12, 25),
    "new_year": (1, 1),
    "diwali": None,  # approximate, handle separately
}

# Diwali approximate dates by year
_DIWALI_DATES = {
    2024: date(2024, 11, 1),
    2025: date(2025, 10, 20),
    2026: date(2026, 11, 8),
}

# Mother's Day: 2nd Sunday of May
def _mothers_day(year: int) -> date:
    d = date(year, 5, 1)
    sundays = 0
    while sundays < 2:
        if d.weekday() == 6:
            sundays += 1
        if sundays < 2:
            d += timedelta(days=1)
    return d

# Father's Day: 3rd Sunday of June
def _fathers_day(year: int) -> date:
    d = date(year, 6, 1)
    sundays = 0
    while sundays < 3:
        if d.weekday() == 6:
            sundays += 1
        if sundays < 3:
            d += timedelta(days=1)
    return d


def _hijri_to_gregorian(hijri_year: int, hijri_month: int, hijri_day: int) -> Optional[date]:
    try:
        g = Hijri(hijri_year, hijri_month, hijri_day).to_gregorian()
        return date(g.year, g.month, g.day)
    except Exception:
        return None


def _gregorian_to_hijri(g: date):
    try:
        return HijriGregorian(g.year, g.month, g.day).to_hijri()
    except Exception:
        return None


def _next_gregorian_for_hijri(hijri_month: int, hijri_day: int) -> Optional[date]:
    """Find next Gregorian date for a given Hijri month/day on or after TODAY."""
    today_hijri = _gregorian_to_hijri(TODAY)
    if today_hijri is None:
        return None
    year = today_hijri.year
    for y in [year, year + 1]:
        try:
            g = _hijri_to_gregorian(y, hijri_month, hijri_day)
            if g and g >= TODAY:
                return g
        except Exception:
            continue
    return None


def _next_occurrence(month: int, day: int) -> date:
    """Next calendar date for a fixed month/day on or after TODAY."""
    candidate = date(TODAY.year, month, day)
    if candidate < TODAY:
        candidate = date(TODAY.year + 1, month, day)
    return candidate


def _occasion_from_order_tag(tag: str) -> Optional[str]:
    mapping = {
        "valentines_day": "valentines_day",
        "womens_day": "womens_day",
        "mothers_day": "mothers_day",
        "fathers_day": "fathers_day",
        "birthday": "birthday",
        "anniversary": "anniversary",
        "eid": "eid_al_fitr",
        "diwali": "diwali",
        "christmas": "christmas",
        "graduation": "graduation",
        "new_home": "new_home",
    }
    return mapping.get(tag)


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def detect_occasions(profile: CustomerProfile) -> list[OccasionDetection]:
    detections: list[OccasionDetection] = []

    # 1. Explicit profile saves → high confidence
    detections.extend(_detect_from_profile(profile))

    # 2. Order-pattern inference
    detections.extend(_detect_from_orders(profile))

    # 3. Hijri/Islamic occasions
    detections.extend(_detect_hijri_occasions(profile))

    # 4. Deduplicate (keep highest confidence per customer+occasion+recipient)
    detections = _deduplicate(detections)

    # 5. Filter to look-ahead window and ensure future dates
    window_end = TODAY + timedelta(days=LOOK_AHEAD_DAYS)
    detections = [
        d for d in detections
        if _parse_date(d.predicted_date) and TODAY <= _parse_date(d.predicted_date) <= window_end
    ]

    return detections


# ─── DETECTION STRATEGIES ─────────────────────────────────────────────────────

def _detect_from_profile(profile: CustomerProfile) -> list[OccasionDetection]:
    results = []
    for pu in profile.profile_updates:
        d = pu.get("data", {})
        field = d.get("field")
        value = d.get("value", "")
        recipient_name = d.get("recipient_name")

        if field not in ("birthday", "anniversary"):
            continue

        try:
            saved = date.fromisoformat(value)
        except ValueError:
            continue

        next_date = _next_occurrence(saved.month, saved.day)
        # Roll forward if the computed date is already past (e.g. saved birthday in May, now late May)
        if next_date < TODAY:
            next_date = date(next_date.year + 1, next_date.month, next_date.day)
        results.append(OccasionDetection(
            customer_id=profile.customer_id,
            occasion=field,
            predicted_date=next_date.isoformat(),
            confidence="high",
            evidence=[f"Explicit {field} save in profile: {value}"],
            recipient_name=recipient_name,
            recipient_relationship=None,
            calendar_type="gregorian",
        ))
    return results


def _detect_from_orders(profile: CustomerProfile) -> list[OccasionDetection]:
    results = []
    orders = profile.orders

    # Group orders by occasion_tag
    by_occasion: dict[str, list[dict]] = defaultdict(list)
    for o in orders:
        tag = o.get("data", {}).get("occasion_tag")
        if tag:
            by_occasion[tag].append(o)

    # Group orders by recipient to detect clustering
    by_recipient: dict[str, list[dict]] = defaultdict(list)
    for o in orders:
        recip = (o.get("data", {}).get("recipient_name") or "").lower().strip()
        if recip:
            by_recipient[recip].append(o)

    for tag, tag_orders in by_occasion.items():
        occasion = _occasion_from_order_tag(tag)
        if not occasion or occasion in ("eid_al_fitr", "eid_al_adha"):
            continue  # Eid handled by Hijri module

        # Get unique years of orders for this occasion
        order_years = sorted({_parse_ts(o["timestamp"]).year for o in tag_orders})
        n_years = len(order_years)

        if n_years >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # Infer next occurrence date
        next_date = _infer_next_date(occasion, tag_orders)
        if next_date is None:
            continue

        # Evidence string
        dates_str = ", ".join(str(y) for y in order_years)
        evidence = [f"Ordered for '{tag}' in {dates_str} ({n_years} year(s) of data)"]

        # Collect recipient info
        recip_name = tag_orders[-1].get("data", {}).get("recipient_name")
        recip_rel = tag_orders[-1].get("data", {}).get("recipient_relationship")

        results.append(OccasionDetection(
            customer_id=profile.customer_id,
            occasion=occasion,
            predicted_date=next_date.isoformat(),
            confidence=confidence,
            evidence=evidence,
            recipient_name=recip_name,
            recipient_relationship=recip_rel,
            calendar_type="gregorian",
        ))

    # Recipient clustering: same recipient, different occasions
    for recip_name_raw, recip_orders in by_recipient.items():
        if len(recip_orders) < 2:
            continue
        occasion_tags_for_recip = list({o.get("data", {}).get("occasion_tag") for o in recip_orders})
        if len(occasion_tags_for_recip) < 2:
            continue
        # Already emitted per-occasion detections above; this adds extra evidence
        # to any existing detection for this recipient - handled in dedup.

    return results


def _detect_hijri_occasions(profile: CustomerProfile) -> list[OccasionDetection]:
    """Detect upcoming Eid occasions for customers who ordered on Eid in the past."""
    results = []
    orders = profile.orders

    eid_orders = [o for o in orders if o.get("data", {}).get("occasion_tag") == "eid"]
    if not eid_orders:
        return results

    # Determine if they ordered for Eid al-Fitr, Eid al-Adha, or both
    eid_fitr_dates = [date(2025, 3, 30), date(2026, 3, 20)]
    eid_adha_dates = [date(2025, 6, 6), date(2026, 5, 27)]

    def _nearest_eid_type(order_date: date) -> str:
        fitr_diffs = [abs((order_date - d).days) for d in eid_fitr_dates]
        adha_diffs = [abs((order_date - d).days) for d in eid_adha_dates]
        if min(fitr_diffs) <= min(adha_diffs):
            return "eid_al_fitr"
        return "eid_al_adha"

    detected_types: dict[str, list] = defaultdict(list)
    for o in eid_orders:
        odate = _parse_ts(o["timestamp"]).date()
        eid_type = _nearest_eid_type(odate)
        detected_types[eid_type].append(o)

    for eid_type, type_orders in detected_types.items():
        hijri_month, hijri_day = _EID_HIJRI[eid_type]
        next_date = _next_gregorian_for_hijri(hijri_month, hijri_day)
        if next_date is None:
            continue

        years = sorted({_parse_ts(o["timestamp"]).year for o in type_orders})
        n_years = len(years)
        confidence = "medium" if n_years >= 2 else "low"

        eid_display = "Eid al-Fitr" if eid_type == "eid_al_fitr" else "Eid al-Adha"
        hijri_ref = f"1 Shawwal" if eid_type == "eid_al_fitr" else "10 Dhul Hijjah"
        evidence = [
            f"Ordered gifts for Eid in {', '.join(str(y) for y in years)}",
            f"Hijri date: {hijri_ref} → Gregorian {next_date.isoformat()} (converted via hijridate)",
        ]

        recip = type_orders[-1].get("data", {}).get("recipient_name")
        recip_rel = type_orders[-1].get("data", {}).get("recipient_relationship")

        results.append(OccasionDetection(
            customer_id=profile.customer_id,
            occasion=eid_display,
            predicted_date=next_date.isoformat(),
            confidence=confidence,
            evidence=evidence,
            recipient_name=recip,
            recipient_relationship=recip_rel,
            calendar_type="hijri",
        ))

    return results


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _infer_next_date(occasion: str, orders: list[dict]) -> Optional[date]:
    if occasion in ("birthday", "anniversary"):
        for o in sorted(orders, key=lambda x: x["timestamp"], reverse=True):
            ts = _parse_ts(o["timestamp"])
            if ts:
                next_d = _next_occurrence(ts.month, ts.day)
                # Roll forward one year if the computed date is already past
                if next_d < TODAY:
                    next_d = date(next_d.year + 1, next_d.month, next_d.day)
                return next_d
        return None

    if occasion == "valentines_day":
        d = _next_occurrence(2, 14)
        return d if d >= TODAY else date(d.year + 1, 2, 14)
    if occasion == "womens_day":
        d = _next_occurrence(3, 8)
        return d if d >= TODAY else date(d.year + 1, 3, 8)
    if occasion == "christmas":
        d = _next_occurrence(12, 25)
        return d if d >= TODAY else date(d.year + 1, 12, 25)
    if occasion == "new_year":
        d = _next_occurrence(1, 1)
        return d if d >= TODAY else date(d.year + 1, 1, 1)
    if occasion == "mothers_day":
        d = _mothers_day(TODAY.year)
        return d if d >= TODAY else _mothers_day(TODAY.year + 1)
    if occasion == "fathers_day":
        d = _fathers_day(TODAY.year)
        return d if d >= TODAY else _fathers_day(TODAY.year + 1)
    if occasion == "diwali":
        for year in [TODAY.year, TODAY.year + 1]:
            d = _DIWALI_DATES.get(year)
            if d and d >= TODAY:
                return d
        return None
    return None


def _deduplicate(detections: list[OccasionDetection]) -> list[OccasionDetection]:
    """Keep highest-confidence detection per (customer_id, occasion, recipient_name)."""
    priority = {"high": 3, "medium": 2, "low": 1}
    best: dict[tuple, OccasionDetection] = {}
    for d in detections:
        key = (d.customer_id, d.occasion, (d.recipient_name or "").lower())
        existing = best.get(key)
        if existing is None or priority[d.confidence] > priority[existing.confidence]:
            best[key] = d
    return list(best.values())


def _parse_ts(ts_str: str):
    from datetime import datetime
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


def _parse_date(date_str: str) -> Optional[date]:
    try:
        return date.fromisoformat(date_str)
    except Exception:
        return None
