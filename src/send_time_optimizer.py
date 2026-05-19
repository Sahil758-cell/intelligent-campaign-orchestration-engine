"""
Send-Time Optimisation.

Per-customer, per-channel optimal send time based on:
  - Historical interaction timestamps (email opens, WA reads, order placement times)
  - Timezone awareness (never 11 PM – 6 AM in local time)
  - Cold-start: segment-level defaults when < 3 events
  - Urgency: occasions < 3 days away → earlier in the day

All times are returned as timezone-aware datetimes.
"""

from __future__ import annotations
from datetime import datetime, timedelta, date
from collections import defaultdict
import pytz

from src.models import CustomerProfile

TODAY = date(2026, 5, 19)

# ─── SEGMENT DEFAULTS ─────────────────────────────────────────────────────────
# Format: (whatsapp_hour, email_hour, push_hour) in local time

_SEGMENT_DEFAULTS: dict[str, tuple[int, int, int]] = {
    "uae_female_25_35": (10, 20, 9),
    "uae_male_25_35": (11, 19, 10),
    "uae_female_35_45": (9, 20, 9),
    "uae_male_35_45": (11, 21, 10),
    "uae_mixed_25_35": (10, 20, 9),
    "india_female_25_35": (10, 20, 9),
    "india_male_25_35": (11, 20, 9),
    "india_mixed_25_35": (10, 20, 9),
    "uk_female_25_35": (11, 19, 10),
    "uk_male_25_35": (12, 20, 10),
    "uk_mixed_25_35": (11, 19, 10),
    "canada_female_25_35": (10, 20, 10),
    "canada_male_25_35": (11, 20, 10),
    "canada_mixed_25_35": (10, 20, 10),
    "egypt_female_25_35": (10, 20, 9),
    "egypt_male_25_35": (11, 19, 10),
    "egypt_mixed_25_35": (10, 20, 9),
    "usa_female_25_35": (10, 19, 9),
    "usa_male_25_35": (11, 20, 10),
    "usa_mixed_25_35": (10, 20, 9),
}

_DEFAULT_HOURS = (10, 20, 9)  # fallback if segment not found

# Quiet hours in local time: do not schedule between 23:00 and 06:00
_QUIET_START = 23
_QUIET_END = 6


def optimal_send_time(
    profile: CustomerProfile,
    channel: str,
    occasion_date: date,
    send_date: date | None = None,
) -> datetime:
    """
    Return an optimal timezone-aware datetime for sending to this customer on this channel.

    Args:
        profile: CustomerProfile with interaction history.
        channel: 'email', 'whatsapp', or 'push'.
        occasion_date: The actual gifting occasion date (used for urgency).
        send_date: The calendar date to schedule on (defaults to today).
    """
    if send_date is None:
        send_date = TODAY

    tz = pytz.timezone(profile.timezone)
    total_events = len(profile.orders) + len(profile.browse_events) + len(profile.wa_events)

    if total_events < 3:
        # Cold-start: use segment defaults
        hour = _cold_start_hour(profile.segment, channel)
    else:
        # Use interaction history
        hour = _historical_hour(profile, channel)

    # Urgency adjustment
    days_until = (occasion_date - send_date).days
    hour = _apply_urgency(hour, days_until, channel)

    # Clamp to quiet-hours-free window [6, 22]
    hour = _clamp_hour(hour)

    dt_local = datetime(send_date.year, send_date.month, send_date.day, hour, 0, 0)
    dt_aware = tz.localize(dt_local)
    return dt_aware


# ─── PRIVATE ─────────────────────────────────────────────────────────────────

def _cold_start_hour(segment: str, channel: str) -> int:
    defaults = _SEGMENT_DEFAULTS.get(segment, _DEFAULT_HOURS)
    wa_h, email_h, push_h = defaults
    if channel == "whatsapp":
        return wa_h
    if channel == "email":
        return email_h
    return push_h


def _historical_hour(profile: CustomerProfile, channel: str) -> int:
    hours: list[int] = []

    if channel == "whatsapp":
        for evt in profile.wa_events:
            if evt.get("data", {}).get("read"):
                h = _extract_local_hour(evt["timestamp"], profile.timezone)
                if h is not None:
                    hours.append(h)

    elif channel == "email":
        # Proxy email open time using order placement hours (customer is active at the screen)
        for evt in profile.orders:
            h = _extract_local_hour(evt["timestamp"], profile.timezone)
            if h is not None:
                hours.append(h)

    else:  # push
        for evt in profile.browse_events:
            h = _extract_local_hour(evt["timestamp"], profile.timezone)
            if h is not None:
                hours.append(h)

    if not hours:
        return _cold_start_hour(profile.segment, channel)

    return int(round(sum(hours) / len(hours)))


def _extract_local_hour(ts_str: str, tz_name: str) -> int | None:
    try:
        dt = datetime.fromisoformat(ts_str)
        tz = pytz.timezone(tz_name)
        local_dt = dt.astimezone(tz)
        return local_dt.hour
    except Exception:
        return None


def _apply_urgency(hour: int, days_until: int, channel: str) -> int:
    """
    Occasion < 3 days: shift 2 hours earlier (morning delivery = more time to shop).
    Occasion 3–7 days: shift 1 hour earlier.
    Occasion 7+ days: no adjustment.
    """
    if days_until < 3:
        return hour - 2
    if days_until <= 7:
        return hour - 1
    return hour


def _clamp_hour(hour: int) -> int:
    """Keep hour within 6–22 range."""
    if hour < _QUIET_END:
        return _QUIET_END
    if hour >= _QUIET_START:
        return _QUIET_START - 1
    return hour
