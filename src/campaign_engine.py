"""
Campaign Decision Engine.

Decides: which customers to target, on which channel, at what time — and which NOT to message.

Rules:
  1. Fatigue management: ≤ 2 promotional messages per customer per week (all channels combined).
  2. Confidence priority: if high + low confidence occasions in same week, only send for high.
  3. Channel preference: if email open rate = 0% and WA read rate > 60% → skip email.
  4. Consent: never send on a channel the customer hasn't opted into.
  5. For opted-out channels: re-allocate to best available consented channel.
"""

from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional
import uuid

from src.models import (
    CustomerProfile, OccasionDetection, ScheduledSend,
    MessageBundle, FatigueCheck, ConsentStatus,
)
from src.send_time_optimizer import optimal_send_time

TODAY = date(2026, 5, 19)
WEEKLY_MESSAGE_CAP = 2


def build_campaign_schedule(
    profiles: dict[str, CustomerProfile],
    detections: list[OccasionDetection],
    messages: dict[str, MessageBundle],  # keyed by detection key
) -> list[ScheduledSend]:
    """
    Given all profiles, detected occasions, and pre-generated messages,
    produce a list of ScheduledSend objects respecting all rules.
    """
    # Group detections by customer
    by_customer: dict[str, list[OccasionDetection]] = defaultdict(list)
    for det in detections:
        by_customer[det.customer_id].append(det)

    schedule: list[ScheduledSend] = []
    weekly_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # weekly_counts[customer_id][iso_week] = count

    for cid, customer_detections in by_customer.items():
        profile = profiles.get(cid)
        if profile is None:
            continue

        # Sort detections: high confidence first, then by date
        priority_order = {"high": 0, "medium": 1, "low": 2}
        customer_detections.sort(key=lambda d: (priority_order[d.confidence], d.predicted_date))

        # Within-week deduplication: if multiple occasions in same week, prefer highest confidence
        seen_weeks: dict[str, str] = {}  # iso_week → confidence of already-scheduled occasion
        occasion_index = 0  # increments per scheduled send to rotate channels

        for det in customer_detections:
            try:
                occ_date = date.fromisoformat(det.predicted_date)
            except ValueError:
                continue

            # Determine send date (3–7 days before occasion; or today if < 3 days)
            days_until = (occ_date - TODAY).days
            if days_until < 0:
                continue
            if days_until < 3:
                send_date = TODAY
            elif days_until < 7:
                send_date = occ_date - timedelta(days=3)
            else:
                send_date = occ_date - timedelta(days=7)

            iso_week = send_date.isocalendar()[:2]  # (year, week)
            week_key = f"{iso_week[0]}-W{iso_week[1]}"

            # Fatigue check
            current_count = weekly_counts[cid][week_key]
            if current_count >= WEEKLY_MESSAGE_CAP:
                continue

            # Confidence conflict: if week already has a higher-confidence send, skip lower
            existing_conf = seen_weeks.get(week_key)
            if existing_conf == "high" and det.confidence != "high":
                continue
            if existing_conf == "medium" and det.confidence == "low":
                continue

            # Select channel — rotates across occasions so same customer gets multi-channel sends
            channel, reason_suffix = _select_channel(profile, occasion_index)
            if channel is None:
                continue  # no consented channel available
            occasion_index += 1

            # Build consent status
            consent = ConsentStatus(
                email=profile.email_optin,
                whatsapp=profile.wa_optin,
                push=profile.push_optin,
            )

            # Compute send time
            send_dt = optimal_send_time(profile, channel, occ_date, send_date)

            # Retrieve message
            det_key = _detection_key(det)
            bundle = messages.get(det_key)
            if bundle is None:
                bundle = MessageBundle()

            reasoning = (
                f"Customer {cid} has a {det.confidence}-confidence {det.occasion} occasion on "
                f"{det.predicted_date} for recipient '{det.recipient_name or 'unknown'}'; "
                f"sending via {channel} {reason_suffix}"
            )

            send = ScheduledSend(
                send_id=str(uuid.uuid4()),
                customer_id=cid,
                channel=channel,
                scheduled_send_time=send_dt.isoformat(),
                occasion=det.occasion,
                confidence_score=det.confidence,
                message=bundle,
                reasoning=reasoning,
                consent_status=consent,
                fatigue_check=FatigueCheck(
                    messages_this_week=current_count,
                    within_limit=True,
                ),
            )

            schedule.append(send)
            weekly_counts[cid][week_key] += 1
            seen_weeks[week_key] = det.confidence

    return schedule


def _select_channel(
    profile: CustomerProfile,
    occasion_index: int = 0,
) -> tuple[Optional[str], str]:
    """
    Return (channel, reasoning_suffix) for best channel, respecting consent and preference.

    Channel preference logic:
      - If WA read rate > 60% and email open rate = 0% → prefer WA
      - Otherwise use channel priority: whatsapp > email > push
      - occasion_index rotates through consented channels so different occasions
        for the same customer are sent on different channels (multi-channel coverage).
    """
    wa_preferred = profile.wa_read_rate >= 0.6 and profile.email_open_rate == 0.0

    if wa_preferred:
        channel_priority = ["whatsapp", "push"]  # email excluded — 0% open rate
        preference_note = "due to high WA read rate and no email opens"
    else:
        channel_priority = ["whatsapp", "email", "push"]
        preference_note = "as default channel priority"

    consent_map = {
        "email": profile.email_optin,
        "whatsapp": profile.wa_optin,
        "push": profile.push_optin,
    }

    # Build ordered list of consented channels
    consented = [ch for ch in channel_priority if consent_map.get(ch, False)]
    if not consented:
        return None, ""

    # Rotate: nth occasion uses nth consented channel (cycling)
    channel = consented[occasion_index % len(consented)]
    return channel, preference_note


def _detection_key(det: OccasionDetection) -> str:
    return f"{det.customer_id}::{det.occasion}::{det.recipient_name or ''}::{det.predicted_date}"
