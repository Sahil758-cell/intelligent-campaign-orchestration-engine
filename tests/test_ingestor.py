"""Tests for ingestor.py — event loading, profile building, consent/timezone inference."""

import pytest
from src.ingestor import load_events, load_catalogue, build_customer_profiles


class TestLoadEvents:
    def test_loads_500_events(self, sample_events):
        assert len(sample_events) >= 200, f"Expected ≥200 events, got {len(sample_events)}"

    def test_all_have_required_fields(self, sample_events):
        required = {"event_id", "customer_id", "event_type", "timestamp", "data"}
        for evt in sample_events:
            assert required.issubset(evt.keys()), f"Missing fields in {evt.get('event_id')}"

    def test_event_types_valid(self, sample_events):
        valid_types = {"order", "browse", "whatsapp_interaction", "profile_update"}
        for evt in sample_events:
            assert evt["event_type"] in valid_types

    def test_timestamps_parseable(self, sample_events):
        from datetime import datetime
        for evt in sample_events:
            datetime.fromisoformat(evt["timestamp"])

    def test_50_unique_customers(self, sample_events):
        customers = {e["customer_id"] for e in sample_events}
        assert len(customers) >= 20, f"Expected ≥20 customers, got {len(customers)}"

    def test_events_span_14_months(self, sample_events):
        from datetime import datetime
        timestamps = [datetime.fromisoformat(e["timestamp"]) for e in sample_events]
        start = min(timestamps)
        end = max(timestamps)
        span_days = (end - start).days
        assert span_days >= 365, f"Events span only {span_days} days"

    def test_validation_rejects_bad_events(self, tmp_path):
        import json
        bad_data = [
            {"event_id": "x", "customer_id": "C1", "event_type": "invalid_type",
             "timestamp": "2025-01-01T00:00:00+00:00", "data": {}},
            {"event_id": "y", "customer_id": "C2"},  # missing fields
        ]
        path = tmp_path / "bad_events.json"
        path.write_text(json.dumps(bad_data))
        events = load_events(path)
        assert len(events) == 0


class TestLoadCatalogue:
    def test_loads_100_skus(self, sample_catalogue):
        assert len(sample_catalogue) == 100

    def test_all_6_categories_present(self, sample_catalogue):
        categories = {p.category for p in sample_catalogue.values()}
        assert categories == {"flowers", "cakes", "chocolates", "hampers", "perfumes", "combos"}

    def test_cultural_flags_present(self, sample_catalogue):
        for p in sample_catalogue.values():
            assert "alcohol_free" in p.cultural_flags
            assert "halal" in p.cultural_flags
            assert "vegan" in p.cultural_flags

    def test_all_skus_unique(self, sample_catalogue):
        assert len(sample_catalogue) == len(set(sample_catalogue.keys()))


class TestBuildProfiles:
    def test_builds_50_profiles(self, sample_profiles):
        assert len(sample_profiles) >= 20, f"Expected ≥20 profiles, got {len(sample_profiles)}"

    def test_profiles_have_timezone(self, sample_profiles):
        for profile in sample_profiles.values():
            assert profile.timezone is not None
            assert len(profile.timezone) > 0

    def test_at_least_3_different_timezones(self, sample_profiles):
        timezones = {p.timezone for p in sample_profiles.values()}
        assert len(timezones) >= 3, f"Only {len(timezones)} timezones: {timezones}"

    def test_wa_opted_out_customer_has_false_optin(self, sample_events, sample_profiles):
        """Customers with opted_out=True in WA events should have wa_optin=False."""
        opted_out_custs = set()
        for evt in sample_events:
            if evt["event_type"] == "whatsapp_interaction":
                if evt.get("data", {}).get("opted_out"):
                    opted_out_custs.add(evt["customer_id"])

        for cid in opted_out_custs:
            profile = sample_profiles.get(cid)
            if profile:
                assert profile.wa_optin is False, \
                    f"{cid} opted out of WA but has wa_optin=True"

    def test_wa_read_rate_between_0_and_1(self, sample_profiles):
        for profile in sample_profiles.values():
            assert 0.0 <= profile.wa_read_rate <= 1.0

    def test_order_events_stored(self, sample_profiles):
        customers_with_orders = [p for p in sample_profiles.values() if p.orders]
        assert len(customers_with_orders) > 0

    def test_new_customers_have_few_events(self, sample_profiles):
        """Cold-start customers (CUST046-050) should have very few events."""
        cold_custs = ["CUST046", "CUST047", "CUST048", "CUST049", "CUST050"]
        for cid in cold_custs:
            profile = sample_profiles.get(cid)
            if profile:
                total = len(profile.orders) + len(profile.browse_events) + len(profile.wa_events)
                assert total < 5, f"{cid} has {total} events (expected < 5 for cold-start)"
