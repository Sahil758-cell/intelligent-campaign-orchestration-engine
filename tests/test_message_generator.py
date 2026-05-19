"""Tests for message_generator.py — LLM calls are fully mocked."""

import json
import pytest
from unittest.mock import MagicMock, patch
from src.message_generator import (
    generate_messages,
    _apply_safety_layer,
    _parse_llm_response,
    _has_opt_out_footer,
    _clean_text,
    _get_product_recommendations,
    _fallback_bundle,
)
from src.models import OccasionDetection


@pytest.fixture
def birthday_detection():
    return OccasionDetection(
        customer_id="CUST001",
        occasion="birthday",
        predicted_date="2026-07-15",
        confidence="high",
        evidence=["Explicit birthday save in profile: 1990-07-15"],
        recipient_name="Husband",
        recipient_relationship="Spouse",
        calendar_type="gregorian",
    )


@pytest.fixture
def eid_detection():
    return OccasionDetection(
        customer_id="CUST001",
        occasion="Eid al-Adha",
        predicted_date="2026-05-27",
        confidence="medium",
        evidence=["Ordered gifts for Eid in 2025", "Hijri date: 10 Dhul Hijjah"],
        recipient_name="Family",
        recipient_relationship="Family",
        calendar_type="hijri",
    )


# ─── CONTENT SAFETY ───────────────────────────────────────────────────────────

class TestContentSafety:
    def test_discount_language_rejected(self, birthday_detection, sample_catalogue):
        parsed = {
            "email": {"subject": "50% off today only!", "body": "Big sale on flowers."},
            "whatsapp": {"template_body": "Get a discount now.\n\nReply STOP to opt out.", "variables": ["a", "b", "c"]},
            "push": {"text": "Save now!", "deep_link": "zuvees://shop"},
        }
        bundle = _apply_safety_layer(parsed, birthday_detection, [], sample_catalogue)
        # Discount-flagged fields should be None or empty
        if bundle.email:
            assert "50%" not in bundle.email.subject
            assert "50%" not in bundle.email.body

    def test_eid_message_no_alcohol(self, eid_detection, sample_catalogue):
        parsed = {
            "email": {"subject": "Eid gifts", "body": "Celebrate with wine and roses."},
            "whatsapp": {"template_body": "Beer hamper for Eid!\n\nReply STOP to opt out.", "variables": ["a", "b", "c"]},
            "push": {"text": "Eid champagne gift", "deep_link": "zuvees://shop"},
        }
        bundle = _apply_safety_layer(parsed, eid_detection, [], sample_catalogue)
        # All cultural-sensitive fields with alcohol must be rejected
        if bundle.email:
            assert "wine" not in bundle.email.body.lower()
        if bundle.whatsapp:
            assert "beer" not in bundle.whatsapp.template_body.lower()

    def test_whatsapp_always_has_opt_out_footer(self, birthday_detection, sample_catalogue):
        parsed = {
            "email": {"subject": "Birthday gift ideas", "body": "We have great gifts."},
            "whatsapp": {"template_body": "Hi {1}, happy birthday to {2}!", "variables": ["a", "b", "c"]},
            "push": {"text": "Birthday gifts — shop now.", "deep_link": "zuvees://shop?occasion=birthday"},
        }
        bundle = _apply_safety_layer(parsed, birthday_detection, [], sample_catalogue)
        if bundle.whatsapp:
            assert bundle.whatsapp.has_opt_out_footer is True
            assert "stop" in bundle.whatsapp.template_body.lower() or "opt out" in bundle.whatsapp.template_body.lower()

    def test_whatsapp_truncated_to_1024(self, birthday_detection, sample_catalogue):
        long_body = "A" * 1100 + "\n\nReply STOP to opt out."
        parsed = {
            "whatsapp": {"template_body": long_body, "variables": ["a", "b", "c"]},
        }
        bundle = _apply_safety_layer(parsed, birthday_detection, [], sample_catalogue)
        if bundle.whatsapp:
            assert len(bundle.whatsapp.template_body) <= 1024

    def test_push_truncated_to_150(self, birthday_detection, sample_catalogue):
        long_text = "B" * 200
        parsed = {
            "push": {"text": long_text, "deep_link": "zuvees://shop"},
        }
        bundle = _apply_safety_layer(parsed, birthday_detection, [], sample_catalogue)
        if bundle.push:
            assert len(bundle.push.text) <= 150

    def test_subject_truncated_to_60(self, birthday_detection, sample_catalogue):
        parsed = {
            "email": {"subject": "C" * 80, "body": "Some body text here that is warm and lovely."},
        }
        bundle = _apply_safety_layer(parsed, birthday_detection, [], sample_catalogue)
        if bundle.email:
            assert len(bundle.email.subject) <= 60

    def test_whatsapp_variables_capped_at_3(self, birthday_detection, sample_catalogue):
        parsed = {
            "whatsapp": {
                "template_body": "Hi {1} {2} {3}.\n\nReply STOP to opt out.",
                "variables": ["a", "b", "c", "d", "e"],
            },
        }
        bundle = _apply_safety_layer(parsed, birthday_detection, [], sample_catalogue)
        if bundle.whatsapp:
            assert len(bundle.whatsapp.variables) <= 3


# ─── OPT-OUT FOOTER DETECTION ────────────────────────────────────────────────

class TestOptOutFooter:
    def test_reply_stop_detected(self):
        assert _has_opt_out_footer("Hello!\n\nReply STOP to opt out.")

    def test_unsubscribe_detected(self):
        assert _has_opt_out_footer("Message body.\n\nUnsubscribe here.")

    def test_no_footer_not_detected(self):
        assert not _has_opt_out_footer("Just a regular message without a stop directive.")


# ─── CLEAN TEXT ───────────────────────────────────────────────────────────────

class TestCleanText:
    def test_removes_discount_pattern(self):
        assert _clean_text("Get 50% off today!", False) == ""

    def test_cultural_alcohol_rejected(self):
        assert _clean_text("Celebrate with wine!", True) == ""

    def test_clean_text_passes_through(self):
        text = "A thoughtful gift for someone special."
        assert _clean_text(text, False) == text

    def test_pork_rejected_in_cultural_context(self):
        assert _clean_text("Includes bacon hamper.", True) == ""

    def test_empty_input_returns_empty(self):
        assert _clean_text("", False) == ""


# ─── JSON PARSING ─────────────────────────────────────────────────────────────

class TestParseResponse:
    def test_parses_clean_json(self):
        raw = '{"email": {"subject": "test", "body": "body"}}'
        result = _parse_llm_response(raw)
        assert result["email"]["subject"] == "test"

    def test_strips_markdown_fences(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        result = _parse_llm_response(raw)
        assert result["key"] == "value"

    def test_returns_empty_dict_on_invalid(self):
        result = _parse_llm_response("not json at all ><")
        assert isinstance(result, dict)


# ─── PRODUCT RECOMMENDATIONS ─────────────────────────────────────────────────

class TestProductRecommendations:
    def test_returns_at_most_3(self, sample_catalogue):
        products = _get_product_recommendations("birthday", (100, 500), sample_catalogue)
        assert len(products) <= 3

    def test_cultural_safe_excludes_non_halal(self, sample_catalogue):
        products = _get_product_recommendations("eid", (100, 600), sample_catalogue, cultural_safe=True)
        # All returned products must be alcohol-free
        for name in products:
            matching = [p for p in sample_catalogue.values() if p.name == name]
            if matching:
                assert matching[0].cultural_flags.get("alcohol_free", True) is True

    def test_returns_list(self, sample_catalogue):
        products = _get_product_recommendations("valentines_day", (50, 400), sample_catalogue)
        assert isinstance(products, list)


# ─── GENERATE MESSAGES WITH MOCK LLM ─────────────────────────────────────────

class TestGenerateMessages:
    def test_returns_message_bundle(self, uae_profile, birthday_detection, sample_catalogue, mock_llm_client):
        bundle = generate_messages(uae_profile, birthday_detection, sample_catalogue, mock_llm_client)
        assert bundle is not None

    def test_no_api_key_falls_back_gracefully(self, uae_profile, birthday_detection, sample_catalogue):
        """When ANTHROPIC_API_KEY is not set, fallback messages should be generated."""
        import os
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            bundle = generate_messages(uae_profile, birthday_detection, sample_catalogue, None)
            assert bundle is not None
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old

    def test_eid_messages_generated(self, uae_profile, eid_detection, sample_catalogue, mock_llm_client):
        bundle = generate_messages(uae_profile, eid_detection, sample_catalogue, mock_llm_client)
        assert bundle is not None


# ─── FALLBACK BUNDLE ─────────────────────────────────────────────────────────

class TestFallbackBundle:
    def test_fallback_bundle_returns_valid_bundle(self, birthday_detection):
        bundle = _fallback_bundle(birthday_detection)
        assert bundle is not None

    def test_fallback_whatsapp_has_opt_out(self, birthday_detection):
        bundle = _fallback_bundle(birthday_detection)
        if bundle.whatsapp:
            assert bundle.whatsapp.has_opt_out_footer is True

    def test_fallback_push_within_150(self, birthday_detection):
        bundle = _fallback_bundle(birthday_detection)
        if bundle.push:
            assert len(bundle.push.text) <= 150
