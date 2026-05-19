"""Pydantic models for all data structures in the campaign engine."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class LineItem(BaseModel):
    sku: str
    name: str
    price: float
    category: str


class OrderData(BaseModel):
    order_id: str
    line_items: list[LineItem]
    occasion_tag: str
    recipient_name: str
    recipient_relationship: str
    total_aed: float
    delivery_area: str


class BrowseData(BaseModel):
    page_url: str
    product_sku: str
    category: str
    time_spent_seconds: int


class WhatsAppData(BaseModel):
    direction: str  # inbound | outbound
    template_name: str
    read: bool
    opted_out: bool


class ProfileUpdateData(BaseModel):
    field: str  # birthday | anniversary | ...
    value: str  # date string
    recipient_name: Optional[str] = None


class CustomerEvent(BaseModel):
    event_id: str
    customer_id: str
    event_type: str  # order | browse | whatsapp_interaction | profile_update
    timestamp: datetime
    data: dict


class Product(BaseModel):
    sku: str
    name: str
    category: str
    price_aed: float
    occasion_tags: list[str]
    cultural_flags: dict
    available: bool


class OccasionDetection(BaseModel):
    customer_id: str
    occasion: str
    predicted_date: str  # ISO 8601 date
    confidence: str  # high | medium | low
    evidence: list[str]
    recipient_name: Optional[str] = None
    recipient_relationship: Optional[str] = None
    calendar_type: str  # gregorian | hijri


class EmailMessage(BaseModel):
    subject: str
    body: str


class WhatsAppMessage(BaseModel):
    template_body: str
    variables: list[str]
    has_opt_out_footer: bool


class PushMessage(BaseModel):
    text: str
    deep_link: str


class MessageBundle(BaseModel):
    email: Optional[EmailMessage] = None
    whatsapp: Optional[WhatsAppMessage] = None
    push: Optional[PushMessage] = None


class FatigueCheck(BaseModel):
    messages_this_week: int
    within_limit: bool


class ConsentStatus(BaseModel):
    email: bool
    whatsapp: bool
    push: bool


class ScheduledSend(BaseModel):
    send_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    channel: str  # email | whatsapp | push
    scheduled_send_time: str  # ISO 8601 with timezone
    occasion: str
    confidence_score: str  # high | medium | low
    message: MessageBundle
    reasoning: str
    consent_status: ConsentStatus
    fatigue_check: FatigueCheck


class CustomerProfile(BaseModel):
    customer_id: str
    timezone: str
    email_optin: bool
    wa_optin: bool
    push_optin: bool
    segment: str
    email_open_rate: float = 0.0
    wa_read_rate: float = 0.0
    push_open_rate: float = 0.0
    avg_order_value: float = 0.0
    orders: list[dict] = Field(default_factory=list)
    browse_events: list[dict] = Field(default_factory=list)
    wa_events: list[dict] = Field(default_factory=list)
    profile_updates: list[dict] = Field(default_factory=list)
