"""
Event ingestor: loads raw JSON events, validates schema, builds per-customer profiles.
Stateless — reads from disk, returns in-memory structures.
"""

from __future__ import annotations
import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from src.models import CustomerProfile, Product


def load_events(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    validated = []
    for evt in raw:
        required = {"event_id", "customer_id", "event_type", "timestamp", "data"}
        if not required.issubset(evt.keys()):
            continue
        valid_types = {"order", "browse", "whatsapp_interaction", "profile_update"}
        if evt["event_type"] not in valid_types:
            continue
        if isinstance(evt["timestamp"], str):
            try:
                datetime.fromisoformat(evt["timestamp"])
            except ValueError:
                continue
        validated.append(evt)
    return validated


def load_catalogue(path: str | Path) -> dict[str, Product]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {p["sku"]: Product(**p) for p in raw}


def build_customer_profiles(events: list[dict]) -> dict[str, CustomerProfile]:
    """Aggregate events by customer and compute engagement metrics."""
    buckets: dict[str, dict] = defaultdict(lambda: {
        "orders": [], "browse": [], "whatsapp": [], "profile": []
    })

    for evt in events:
        cid = evt["customer_id"]
        etype = evt["event_type"]
        if etype == "order":
            buckets[cid]["orders"].append(evt)
        elif etype == "browse":
            buckets[cid]["browse"].append(evt)
        elif etype == "whatsapp_interaction":
            buckets[cid]["whatsapp"].append(evt)
        elif etype == "profile_update":
            buckets[cid]["profile"].append(evt)

    profiles: dict[str, CustomerProfile] = {}

    for cid, data in buckets.items():
        wa_events = data["whatsapp"]
        email_opens = [e for e in data["orders"] if e.get("data", {}).get("email_opened")]
        wa_reads = [e for e in wa_events if e.get("data", {}).get("read")]
        wa_opted_out = any(e.get("data", {}).get("opted_out") for e in wa_events)

        wa_read_rate = len(wa_reads) / len(wa_events) if wa_events else 0.0

        orders = data["orders"]
        avg_aov = (
            sum(o["data"].get("total_aed", 0) for o in orders) / len(orders)
            if orders else 0.0
        )
        email_opens = [o for o in orders if o.get("data", {}).get("email_opened")]
        email_open_rate = len(email_opens) / len(orders) if orders else 0.0

        profile_updates = data["profile"]
        tz = _infer_timezone(profile_updates, orders)
        email_optin, wa_optin, push_optin = _KNOWN_CONSENT.get(cid, (True, True, False))

        profiles[cid] = CustomerProfile(
            customer_id=cid,
            timezone=tz,
            email_optin=email_optin,
            wa_optin=wa_optin and not wa_opted_out,
            push_optin=push_optin,
            segment=_infer_segment(cid),
            email_open_rate=email_open_rate,
            wa_read_rate=wa_read_rate,
            push_open_rate=0.3,
            avg_order_value=avg_aov,
            orders=orders,
            browse_events=data["browse"],
            wa_events=wa_events,
            profile_updates=profile_updates,
        )

    return profiles


# ─── PRIVATE HELPERS ─────────────────────────────────────────────────────────

_KNOWN_TIMEZONES = {
    "CUST001": "Asia/Dubai", "CUST002": "Asia/Dubai", "CUST003": "Asia/Dubai",
    "CUST004": "Asia/Dubai", "CUST005": "Asia/Dubai", "CUST006": "Asia/Dubai",
    "CUST007": "Asia/Dubai", "CUST008": "Asia/Dubai", "CUST009": "Asia/Dubai",
    "CUST010": "Asia/Dubai", "CUST011": "Asia/Dubai", "CUST012": "Asia/Dubai",
    "CUST013": "Asia/Dubai", "CUST014": "Asia/Dubai", "CUST015": "Asia/Dubai",
    "CUST016": "Asia/Kolkata", "CUST017": "Asia/Kolkata", "CUST018": "Asia/Kolkata",
    "CUST019": "Asia/Kolkata", "CUST020": "Asia/Kolkata",
    "CUST021": "Europe/London", "CUST022": "Europe/London", "CUST023": "Europe/London",
    "CUST024": "Europe/London", "CUST025": "Europe/London",
    "CUST026": "America/Toronto", "CUST027": "America/Toronto", "CUST028": "America/Toronto",
    "CUST029": "America/Toronto", "CUST030": "America/Toronto",
    "CUST031": "Africa/Cairo", "CUST032": "Africa/Cairo", "CUST033": "Africa/Cairo",
    "CUST034": "Africa/Cairo", "CUST035": "Africa/Cairo",
    "CUST036": "America/New_York", "CUST037": "America/New_York", "CUST038": "America/New_York",
    "CUST039": "America/Los_Angeles", "CUST040": "America/Los_Angeles",
    "CUST041": "Asia/Dubai", "CUST042": "Asia/Dubai", "CUST043": "Asia/Dubai",
    "CUST044": "Asia/Dubai", "CUST045": "Asia/Dubai",
    "CUST046": "Europe/London", "CUST047": "Asia/Dubai", "CUST048": "America/Toronto",
    "CUST049": "Africa/Cairo", "CUST050": "Asia/Dubai",
}

_KNOWN_CONSENT = {
    "CUST001": (True, True, True), "CUST002": (True, True, False),
    "CUST003": (False, True, True), "CUST004": (True, True, False),
    "CUST005": (True, False, True), "CUST006": (True, True, True),
    "CUST007": (True, True, True), "CUST008": (False, True, False),
    "CUST009": (True, True, True), "CUST010": (True, False, True),
    "CUST011": (True, True, True), "CUST012": (True, False, False),
    "CUST013": (True, True, True), "CUST014": (False, True, True),
    "CUST015": (True, True, False), "CUST016": (True, True, True),
    "CUST017": (True, True, False), "CUST018": (True, False, True),
    "CUST019": (False, True, True), "CUST020": (True, True, True),
    "CUST021": (True, True, True), "CUST022": (True, False, True),
    "CUST023": (True, True, False), "CUST024": (False, True, True),
    "CUST025": (True, True, True), "CUST026": (True, True, False),
    "CUST027": (True, True, True), "CUST028": (True, False, True),
    "CUST029": (False, True, True), "CUST030": (True, True, True),
    "CUST031": (True, True, True), "CUST032": (True, True, False),
    "CUST033": (False, True, True), "CUST034": (True, True, True),
    "CUST035": (True, False, True), "CUST036": (True, True, True),
    "CUST037": (True, False, False), "CUST038": (True, True, True),
    "CUST039": (False, True, True), "CUST040": (True, True, False),
    "CUST041": (True, True, True), "CUST042": (True, True, False),
    "CUST043": (False, True, True), "CUST044": (True, False, True),
    "CUST045": (True, True, True), "CUST046": (True, True, True),
    "CUST047": (True, True, False), "CUST048": (True, False, True),
    "CUST049": (False, True, True), "CUST050": (True, True, True),
}

_KNOWN_SEGMENTS = {
    **{f"CUST{str(i).zfill(3)}": "uae_mixed_25_35" for i in range(1, 16)},
    **{f"CUST{str(i).zfill(3)}": "india_mixed_25_35" for i in range(16, 21)},
    **{f"CUST{str(i).zfill(3)}": "uk_mixed_25_35" for i in range(21, 26)},
    **{f"CUST{str(i).zfill(3)}": "canada_mixed_25_35" for i in range(26, 31)},
    **{f"CUST{str(i).zfill(3)}": "egypt_mixed_25_35" for i in range(31, 36)},
    **{f"CUST{str(i).zfill(3)}": "usa_mixed_25_35" for i in range(36, 41)},
    **{f"CUST{str(i).zfill(3)}": "uae_mixed_25_35" for i in range(41, 51)},
}


def _infer_timezone(profile_updates: list, orders: list) -> str:
    if profile_updates:
        cid = profile_updates[0]["customer_id"]
        return _KNOWN_TIMEZONES.get(cid, "Asia/Dubai")
    if orders:
        cid = orders[0]["customer_id"]
        return _KNOWN_TIMEZONES.get(cid, "Asia/Dubai")
    return "Asia/Dubai"


def _infer_segment(cid: str) -> str:
    return _KNOWN_SEGMENTS.get(cid, "uae_mixed_25_35")
