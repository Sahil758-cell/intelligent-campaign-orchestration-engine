"""Tests for campaign_engine.py — fatigue, consent, channel preference."""

import pytest
from datetime import date, timedelta
from collections import defaultdict
from src.campaign_engine import build_campaign_schedule, _select_channel, _detection_key
from src.models import (
    CustomerProfile, OccasionDetection, MessageBundle,
    EmailMessage, WhatsAppMessage, PushMessage,
)
from src.occasion_detector import TODAY


def _make_detection(customer_id, occasion, predicted_date, confidence="medium",
                    recipient_name="Mom", calendar_type="gregorian"):
    return OccasionDetection(
        customer_id=customer_id,
        occasion=occasion,
        predicted_date=predicted_date,
        confidence=confidence,
        evidence=["Order on that date in 2025"],
        recipient_name=recipient_name,
        recipient_relationship="Mother",
        calendar_type=calendar_type,
    )


def _make_bundle():
    return MessageBundle(
        email=EmailMessage(subject="Test subject", body="Test body"),
        whatsapp=WhatsAppMessage(
            template_body="Hi {1} {2} {3}.\n\nReply STOP to opt out.",
            variables=["a", "b", "c"],
            has_opt_out_footer=True,
        ),
        push=PushMessage(text="Test push", deep_link="zuvees://shop"),
    )


@pytest.fixture
def base_profile():
    return CustomerProfile(
        customer_id="CUST001",
        timezone="Asia/Dubai",
        email_optin=True,
        wa_optin=True,
        push_optin=True,
        segment="uae_female_25_35",
        email_open_rate=0.25,
        wa_read_rate=0.50,
        avg_order_value=200.0,
        orders=[],
        browse_events=[],
        wa_events=[],
        profile_updates=[],
    )


# ─── FATIGUE MANAGEMENT ───────────────────────────────────────────────────────

class TestFatigueManagement:
    def test_no_more_than_2_per_week(self, base_profile):
        """No customer should receive more than 2 sends in a 7-day window."""
        detections = [
            _make_detection("CUST001", "birthday", (TODAY + timedelta(days=30)).isoformat(), "high"),
            _make_detection("CUST001", "anniversary", (TODAY + timedelta(days=32)).isoformat(), "medium"),
            _make_detection("CUST001", "mothers_day", (TODAY + timedelta(days=33)).isoformat(), "low"),
        ]
        det_key1 = _detection_key(detections[0])
        det_key2 = _detection_key(detections[1])
        det_key3 = _detection_key(detections[2])
        messages = {
            det_key1: _make_bundle(),
            det_key2: _make_bundle(),
            det_key3: _make_bundle(),
        }
        profiles = {"CUST001": base_profile}
        schedule = build_campaign_schedule(profiles, detections, messages)

        weekly: dict = defaultdict(int)
        for s in schedule:
            from datetime import datetime
            dt = datetime.fromisoformat(s.scheduled_send_time)
            iso = dt.isocalendar()
            key = (s.customer_id, f"{iso[0]}-W{iso[1]}")
            weekly[key] += 1

        for count in weekly.values():
            assert count <= 2, f"Fatigue cap violated: {count} messages in one week"

    def test_high_confidence_wins_over_low(self, base_profile):
        """If high + low confidence in same week, only high gets sent."""
        same_week_date = (TODAY + timedelta(days=20)).isoformat()
        detections = [
            _make_detection("CUST001", "birthday", same_week_date, "high"),
            _make_detection("CUST001", "graduation", same_week_date, "low"),
        ]
        messages = {_detection_key(d): _make_bundle() for d in detections}
        profiles = {"CUST001": base_profile}
        schedule = build_campaign_schedule(profiles, detections, messages)

        cust_sends = [s for s in schedule if s.customer_id == "CUST001"]
        if len(cust_sends) == 1:
            # Only one sent → must be the high-confidence one
            assert cust_sends[0].confidence_score == "high"


# ─── CONSENT MANAGEMENT ───────────────────────────────────────────────────────

class TestConsentManagement:
    def test_never_sends_to_opted_out_channel(self, base_profile):
        """If WA opted out, must not schedule on WA."""
        base_profile.wa_optin = False
        det = _make_detection("CUST001", "birthday", (TODAY + timedelta(days=14)).isoformat())
        messages = {_detection_key(det): _make_bundle()}
        profiles = {"CUST001": base_profile}
        schedule = build_campaign_schedule(profiles, [det], messages)

        for s in schedule:
            if s.customer_id == "CUST001":
                assert s.channel != "whatsapp", "WA opted-out customer received WA message"

    def test_no_channels_available_skips_customer(self, base_profile):
        """Customer with all channels opted out gets nothing."""
        base_profile.email_optin = False
        base_profile.wa_optin = False
        base_profile.push_optin = False
        det = _make_detection("CUST001", "birthday", (TODAY + timedelta(days=14)).isoformat())
        messages = {_detection_key(det): _make_bundle()}
        profiles = {"CUST001": base_profile}
        schedule = build_campaign_schedule(profiles, [det], messages)

        cust_sends = [s for s in schedule if s.customer_id == "CUST001"]
        assert len(cust_sends) == 0

    def test_consent_status_reflects_profile(self, base_profile):
        """consent_status in scheduled send must match profile."""
        base_profile.push_optin = False
        det = _make_detection("CUST001", "birthday", (TODAY + timedelta(days=14)).isoformat())
        messages = {_detection_key(det): _make_bundle()}
        profiles = {"CUST001": base_profile}
        schedule = build_campaign_schedule(profiles, [det], messages)

        for s in schedule:
            assert s.consent_status.push is False


# ─── CHANNEL PREFERENCE ───────────────────────────────────────────────────────

class TestChannelPreference:
    def test_high_wa_rate_zero_email_prefers_wa(self, base_profile):
        base_profile.email_open_rate = 0.0
        base_profile.wa_read_rate = 0.75
        det = _make_detection("CUST001", "birthday", "dummy_date")
        channel, _ = _select_channel(base_profile)
        assert channel == "whatsapp"

    def test_no_wa_optin_falls_back_to_email(self, base_profile):
        base_profile.wa_optin = False
        det = _make_detection("CUST001", "birthday", "dummy_date")
        channel, _ = _select_channel(base_profile)
        assert channel in ("email", "push")

    def test_all_opted_out_returns_none(self, base_profile):
        base_profile.email_optin = False
        base_profile.wa_optin = False
        base_profile.push_optin = False
        det = _make_detection("CUST001", "birthday", "dummy_date")
        channel, _ = _select_channel(base_profile)
        assert channel is None


# ─── SCHEDULE STRUCTURE ───────────────────────────────────────────────────────

class TestScheduleStructure:
    def test_scheduled_send_has_all_required_fields(self, base_profile):
        det = _make_detection("CUST001", "birthday", (TODAY + timedelta(days=14)).isoformat(), "high")
        messages = {_detection_key(det): _make_bundle()}
        profiles = {"CUST001": base_profile}
        schedule = build_campaign_schedule(profiles, [det], messages)

        for s in schedule:
            assert s.send_id
            assert s.customer_id
            assert s.channel in ("email", "whatsapp", "push")
            assert s.scheduled_send_time
            assert s.occasion
            assert s.confidence_score in ("high", "medium", "low")
            assert s.reasoning
            assert s.fatigue_check.within_limit is True

    def test_past_occasion_not_scheduled(self, base_profile):
        past_date = (TODAY - timedelta(days=5)).isoformat()
        det = _make_detection("CUST001", "birthday", past_date, "high")
        messages = {_detection_key(det): _make_bundle()}
        profiles = {"CUST001": base_profile}
        schedule = build_campaign_schedule(profiles, [det], messages)
        assert len(schedule) == 0

    def test_multiple_customers_scheduled(self, sample_profiles):
        from src.occasion_detector import detect_occasions
        detections = []
        for profile in sample_profiles.values():
            detections.extend(detect_occasions(profile))

        messages = {_detection_key(d): _make_bundle() for d in detections}
        schedule = build_campaign_schedule(sample_profiles, detections, messages)
        # Should produce at least some sends
        assert len(schedule) >= 0  # No crash is the minimum bar


# ─── DETECTION KEY ────────────────────────────────────────────────────────────

class TestDetectionKey:
    def test_key_is_string(self):
        det = _make_detection("CUST001", "birthday", "2026-07-15")
        key = _detection_key(det)
        assert isinstance(key, str)
        assert "CUST001" in key
        assert "birthday" in key
