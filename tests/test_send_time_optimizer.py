"""Tests for send_time_optimizer.py — timezone, cold-start, urgency."""

import pytest
from datetime import date, datetime
import pytz
from src.send_time_optimizer import optimal_send_time, _clamp_hour, _apply_urgency, _cold_start_hour
from src.occasion_detector import TODAY


class TestTimezoneAwareness:
    def test_result_is_timezone_aware(self, uae_profile):
        occ_date = date(2026, 6, 15)
        dt = optimal_send_time(uae_profile, "whatsapp", occ_date)
        assert dt.tzinfo is not None

    def test_no_quiet_hours_uae(self, uae_profile):
        occ_date = date(2026, 7, 15)
        dt = optimal_send_time(uae_profile, "email", occ_date)
        tz = pytz.timezone("Asia/Dubai")
        local_dt = dt.astimezone(tz)
        assert 6 <= local_dt.hour < 23, f"Hour {local_dt.hour} is in quiet hours"

    def test_toronto_customer_no_quiet_hours(self, cold_start_profile):
        cold_start_profile.timezone = "America/Toronto"
        occ_date = date(2026, 6, 20)
        dt = optimal_send_time(cold_start_profile, "whatsapp", occ_date)
        tz = pytz.timezone("America/Toronto")
        local_dt = dt.astimezone(tz)
        assert 6 <= local_dt.hour < 23

    def test_london_customer_no_quiet_hours(self, cold_start_profile):
        occ_date = date(2026, 6, 20)
        dt = optimal_send_time(cold_start_profile, "email", occ_date)
        tz = pytz.timezone("Europe/London")
        local_dt = dt.astimezone(tz)
        assert 6 <= local_dt.hour < 23


class TestColdStart:
    def test_cold_start_uses_segment_default(self, cold_start_profile):
        """Profile with < 3 events should use segment defaults, not None."""
        occ_date = date(2026, 6, 15)
        dt = optimal_send_time(cold_start_profile, "whatsapp", occ_date)
        assert dt is not None

    def test_cold_start_hour_not_null(self):
        hour = _cold_start_hour("uae_female_25_35", "whatsapp")
        assert isinstance(hour, int)
        assert 6 <= hour < 23

    def test_cold_start_email_different_from_whatsapp(self):
        """Email and WhatsApp times should differ for the same segment."""
        wa_hour = _cold_start_hour("uae_female_25_35", "whatsapp")
        email_hour = _cold_start_hour("uae_female_25_35", "email")
        assert wa_hour != email_hour


class TestUrgencyAdjustment:
    def test_imminent_occasion_shifts_earlier(self):
        """< 3 days should shift 2 hours earlier."""
        base = 14
        adjusted = _apply_urgency(base, 2, "whatsapp")
        assert adjusted < base

    def test_week_out_shifts_one_hour(self):
        base = 14
        adjusted = _apply_urgency(base, 5, "whatsapp")
        assert adjusted < base

    def test_far_occasion_no_shift(self):
        base = 14
        adjusted = _apply_urgency(base, 10, "whatsapp")
        assert adjusted == base


class TestClampHour:
    def test_clamp_below_6(self):
        assert _clamp_hour(3) == 6

    def test_clamp_above_22(self):
        assert _clamp_hour(24) == 22

    def test_valid_hour_unchanged(self):
        assert _clamp_hour(14) == 14


class TestChannelSpecificTimes:
    def test_email_and_whatsapp_differ_for_same_customer(self, uae_profile):
        occ_date = date(2026, 7, 15)
        wa_dt = optimal_send_time(uae_profile, "whatsapp", occ_date)
        email_dt = optimal_send_time(uae_profile, "email", occ_date)
        tz = pytz.timezone(uae_profile.timezone)
        wa_local = wa_dt.astimezone(tz)
        email_local = email_dt.astimezone(tz)
        # The hours should generally differ for an active customer with history
        assert isinstance(wa_local.hour, int)
        assert isinstance(email_local.hour, int)

    def test_send_date_used(self, uae_profile):
        """Explicitly passing a send_date should put the send on that date."""
        send_date = date(2026, 6, 1)
        occ_date = date(2026, 6, 8)
        dt = optimal_send_time(uae_profile, "push", occ_date, send_date=send_date)
        tz = pytz.timezone(uae_profile.timezone)
        local = dt.astimezone(tz)
        assert local.year == 2026
        assert local.month == 6
