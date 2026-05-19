"""Shared fixtures for all test modules."""

import json
import pytest
from datetime import datetime, date
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).parent.parent


@pytest.fixture
def sample_catalogue():
    path = ROOT / "data" / "product_catalogue.json"
    with open(path, "r") as f:
        raw = json.load(f)
    from src.models import Product
    return {p["sku"]: Product(**p) for p in raw}


@pytest.fixture
def sample_events():
    path = ROOT / "data" / "synthetic_events.json"
    with open(path, "r") as f:
        return json.load(f)


@pytest.fixture
def sample_profiles(sample_events):
    from src.ingestor import build_customer_profiles
    return build_customer_profiles(sample_events)


@pytest.fixture
def mock_llm_client():
    """A mock Anthropic client that returns a valid JSON message."""
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps({
            "email": {
                "subject": "A gift they will treasure",
                "body": (
                    "A special occasion is almost here. "
                    "Our curated collection has been handpicked for moments just like this. "
                    "With 60-minute delivery, we'll make it unforgettable."
                ),
            },
            "whatsapp": {
                "template_body": (
                    "Hi {1}, a special occasion is almost here \U0001f381 "
                    "We've handpicked {2} just for you — delivered in 60 minutes to {3}. "
                    "Explore now: zuvees.ae\n\nReply STOP to opt out."
                ),
                "variables": ["there", "something beautiful", "your door"],
            },
            "push": {
                "text": "A special occasion is near — shop curated gifts on Zuvees. 60-min delivery.",
                "deep_link": "zuvees://shop?occasion=birthday&utm_source=push",
            },
        }))]
    )
    return client


@pytest.fixture
def uae_profile():
    from src.models import CustomerProfile
    return CustomerProfile(
        customer_id="CUST001",
        timezone="Asia/Dubai",
        email_optin=True,
        wa_optin=True,
        push_optin=True,
        segment="uae_female_25_35",
        email_open_rate=0.25,
        wa_read_rate=0.75,
        avg_order_value=280.0,
        orders=[
            {
                "customer_id": "CUST001",
                "event_type": "order",
                "timestamp": "2025-03-30T14:00:00+04:00",
                "data": {
                    "order_id": "ORD-ABC1",
                    "line_items": [{"sku": "ZUV-1000", "name": "Red Rose Bouquet", "price": 149.0, "category": "flowers"}],
                    "occasion_tag": "eid",
                    "recipient_name": "Mom",
                    "recipient_relationship": "Mother",
                    "total_aed": 149.0,
                    "delivery_area": "Al Quoz",
                }
            }
        ],
        browse_events=[],
        wa_events=[
            {
                "customer_id": "CUST001",
                "event_type": "whatsapp_interaction",
                "timestamp": "2025-04-01T10:00:00+04:00",
                "data": {"direction": "outbound", "template_name": "order_confirmation", "read": True, "opted_out": False},
            }
        ],
        profile_updates=[
            {
                "customer_id": "CUST001",
                "event_type": "profile_update",
                "timestamp": "2025-03-05T10:00:00+04:00",
                "data": {"field": "birthday", "value": "1990-07-15", "recipient_name": "Husband"},
            }
        ],
    )


@pytest.fixture
def cold_start_profile():
    from src.models import CustomerProfile
    return CustomerProfile(
        customer_id="CUST046",
        timezone="Europe/London",
        email_optin=True,
        wa_optin=True,
        push_optin=True,
        segment="uk_mixed_25_35",
        email_open_rate=0.0,
        wa_read_rate=0.0,
        avg_order_value=0.0,
        orders=[],
        browse_events=[
            {
                "customer_id": "CUST046",
                "event_type": "browse",
                "timestamp": "2026-05-15T14:00:00+01:00",
                "data": {"page_url": "https://zuvees.ae/products/zuv-1000", "product_sku": "ZUV-1000", "category": "flowers", "time_spent_seconds": 120},
            }
        ],
        wa_events=[],
        profile_updates=[],
    )
