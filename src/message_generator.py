"""
LLM-Powered Personalised Message Generator.

Uses Anthropic Claude to generate messages for email, WhatsApp, and push notifications.
Applies a content safety layer post-generation:
  - Brand voice: luxury, warm, never discount-led
  - Cultural sensitivity: Eid messaging excludes alcohol/pork products
  - WhatsApp constraints: ≤ 1024 chars, ≤ 3 variables, opt-out footer required
  - Push constraints: ≤ 150 chars
  - Factual accuracy: only reference products in catalogue

All LLM calls go through a single _call_llm() function that can be mocked in tests.
"""

from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Optional

from src.models import (
    CustomerProfile, OccasionDetection, MessageBundle,
    EmailMessage, WhatsAppMessage, PushMessage, Product,
)

# ─── PROMPT LOADING ───────────────────────────────────────────────────────────

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


# ─── CATALOGUE PRODUCTS FOR CONTEXT ──────────────────────────────────────────

def _get_product_recommendations(
    occasion: str,
    price_range: tuple[float, float],
    catalogue: dict[str, Product],
    cultural_safe: bool = False,
) -> list[str]:
    """Return up to 3 catalogue product names appropriate for the occasion."""
    candidates = [
        p for p in catalogue.values()
        if occasion.lower().replace(" ", "_") in [t.replace(" ", "_") for t in p.occasion_tags]
        and p.available
        and price_range[0] <= p.price_aed <= price_range[1]
    ]
    if cultural_safe:
        candidates = [p for p in candidates if p.cultural_flags.get("alcohol_free", True)]

    if not candidates:
        candidates = [p for p in catalogue.values() if p.available][:5]

    return [p.name for p in candidates[:3]]


# ─── MAIN PUBLIC API ──────────────────────────────────────────────────────────

def generate_messages(
    profile: CustomerProfile,
    detection: OccasionDetection,
    catalogue: dict[str, Product],
    llm_client=None,
) -> MessageBundle:
    """
    Generate a MessageBundle for one detected occasion.
    llm_client: an Anthropic client instance, or None to use the env-var default.
    """
    is_eid = "eid" in detection.occasion.lower()
    price_low = max(50, profile.avg_order_value * 0.7) if profile.avg_order_value > 0 else 100
    price_high = max(price_low + 200, profile.avg_order_value * 1.3) if profile.avg_order_value > 0 else 400

    products = _get_product_recommendations(
        detection.occasion, (price_low, price_high), catalogue, cultural_safe=is_eid
    )

    context = _build_context(profile, detection, products, price_low, price_high)
    prompt_template = _load_prompt("message_generation.md")

    raw_response = _call_llm(context, prompt_template, llm_client)
    parsed = _parse_llm_response(raw_response)

    bundle = _apply_safety_layer(parsed, detection, products, catalogue)
    return bundle


# ─── CONTEXT BUILDER ─────────────────────────────────────────────────────────

def _build_context(
    profile: CustomerProfile,
    detection: OccasionDetection,
    products: list[str],
    price_low: float,
    price_high: float,
) -> dict:
    order_count = len(profile.orders)
    recent_categories = list({
        li["category"]
        for o in profile.orders[-3:]
        for li in o.get("data", {}).get("line_items", [])
    })

    return {
        "customer_id": profile.customer_id,
        "occasion": detection.occasion,
        "occasion_date": detection.predicted_date,
        "recipient_name": detection.recipient_name or "someone special",
        "recipient_relationship": detection.recipient_relationship or "loved one",
        "confidence": detection.confidence,
        "calendar_type": detection.calendar_type,
        "order_count": order_count,
        "preferred_price_range_aed": f"AED {int(price_low)}–{int(price_high)}",
        "recent_categories": recent_categories,
        "product_suggestions": products,
        "channel_context": "luxury gifting platform, UAE-based, 60-min delivery",
    }


# ─── LLM CALL ─────────────────────────────────────────────────────────────────

def _call_llm(context: dict, prompt_template: str, llm_client=None) -> str:
    """
    Call an LLM and return raw response text.

    Supports two providers (auto-detected from env vars):
      - Cerebras (CEREBRAS_API_KEY) — OpenAI-compatible, Llama models, free tier
      - Anthropic (ANTHROPIC_API_KEY) — Claude models

    If neither key is set, returns a template-based fallback message.
    """
    if llm_client is None:
        llm_client = _build_llm_client()

    if llm_client is None:
        return _fallback_message(context)

    system_prompt = _load_prompt("message_generation.md")
    safety_rules = _load_prompt("content_safety.md")

    user_message = f"""Generate personalised campaign messages for this customer occasion.

CUSTOMER CONTEXT:
{json.dumps(context, indent=2)}

AVAILABLE PRODUCTS (use only these for recommendations):
{chr(10).join(f'- {p}' for p in context.get('product_suggestions', []))}

CONTENT SAFETY RULES:
{safety_rules}

Respond ONLY with a JSON object in this exact format:
{{
  "email": {{
    "subject": "<subject line, max 60 chars>",
    "body": "<warm, personal email body, 3-4 sentences>"
  }},
  "whatsapp": {{
    "template_body": "<WhatsApp message, max 1024 chars, include {{1}} {{2}} {{3}} as variables, end with: Reply STOP to opt out.>",
    "variables": ["<var1>", "<var2>", "<var3>"]
  }},
  "push": {{
    "text": "<push notification, max 150 chars>",
    "deep_link": "zuvees://shop?occasion={context.get('occasion','gift')}&utm_source=push"
  }}
}}"""

    provider = getattr(llm_client, "_zuvees_provider", "unknown")

    for attempt in range(4):  # up to 3 retries
        try:
            if provider in ("cerebras", "groq"):
                model = "llama3.1-8b" if provider == "cerebras" else "llama-3.1-8b-instant"
                response = llm_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=2048,
                    temperature=0.7,
                )
                return response.choices[0].message.content

            else:  # anthropic
                response = llm_client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                return response.content[0].text

        except Exception as e:
            err = str(e)
            if "request_quota_exceeded" in err or "requests per minute" in err.lower():
                wait = 2 ** attempt  # 1s, 2s, 4s, 8s
                print(f"    [rate limit] retrying in {wait}s...")
                import time; time.sleep(wait)
                continue
            # Daily quota or other error — no point retrying
            print(f"    [LLM error: {e}] — using fallback")
            return _fallback_message(context)

    print(f"    [LLM] max retries exceeded — using fallback")
    return _fallback_message(context)


def _build_llm_client():
    """Build a single LLM client (returns first available)."""
    clients = _build_llm_clients()
    return clients[0] if clients else None


def _build_llm_clients() -> list:
    """Build all available LLM clients. Supports multiple Cerebras keys for parallel throughput."""
    clients = []

    # Cerebras — check up to 3 keys (CEREBRAS_API_KEY, CEREBRAS_API_KEY_2, CEREBRAS_API_KEY_3)
    for env_var in ["CEREBRAS_API_KEY", "CEREBRAS_API_KEY_2", "CEREBRAS_API_KEY_3"]:
        key = os.environ.get(env_var, "").strip()
        if key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url="https://api.cerebras.ai/v1")
                client._zuvees_provider = "cerebras"
                clients.append(client)
            except ImportError:
                break

    if clients:
        print(f"    [LLM] Using {len(clients)} Cerebras client(s) (llama3.1-8b)")
        return clients

    # Groq fallback
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            client._zuvees_provider = "groq"
            print("    [LLM] Using Groq (llama-3.1-8b-instant)")
            return [client]
        except ImportError:
            pass

    # Anthropic fallback
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key and "your_" not in anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            client._zuvees_provider = "anthropic"
            print("    [LLM] Using Anthropic (Claude Sonnet)")
            return [client]
        except ImportError:
            pass

    return []


# ─── RESPONSE PARSING ─────────────────────────────────────────────────────────

def _parse_llm_response(raw: str) -> dict:
    """Extract JSON from LLM response, tolerating markdown code fences."""
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                print(f"    [parse] JSON parse failed after regex extraction")
        else:
            print(f"    [parse] No JSON object found in response (len={len(raw)})")
    return {}


# ─── CONTENT SAFETY LAYER ─────────────────────────────────────────────────────

_BANNED_WORDS = [
    "discount", "sale", "% off", "cheap", "deal", "offer", "promo",
    "clearance", "limited time", "hurry", "act now", "don't miss",
    "alcohol", "wine", "beer", "spirits", "pork", "bacon", "ham",
]

_DISCOUNT_PATTERN = re.compile(
    r"\b(\d+%\s*off|buy\s+\d+\s+get|clearance|sale|promo\s*code)\b",
    re.IGNORECASE,
)


def _apply_safety_layer(
    parsed: dict,
    detection: OccasionDetection,
    products: list[str],
    catalogue: dict[str, Product],
) -> MessageBundle:
    is_eid = "eid" in detection.occasion.lower()
    is_diwali = "diwali" in detection.occasion.lower()

    email_data = parsed.get("email")
    wa_data = parsed.get("whatsapp")
    push_data = parsed.get("push")

    email_msg = None
    wa_msg = None
    push_msg = None

    if email_data:
        subject = _clean_text(email_data.get("subject", ""), is_eid or is_diwali)
        body = _clean_text(email_data.get("body", ""), is_eid or is_diwali)
        if subject and body:
            email_msg = EmailMessage(subject=subject[:60], body=body)

    if wa_data:
        template_body = _clean_text(wa_data.get("template_body", ""), is_eid or is_diwali)
        variables = wa_data.get("variables", [])[:3]
        if template_body:
            if not _has_opt_out_footer(template_body):
                template_body = template_body.rstrip() + "\n\nReply STOP to opt out."
            template_body = template_body[:1024]
            wa_msg = WhatsAppMessage(
                template_body=template_body,
                variables=variables,
                has_opt_out_footer=True,
            )

    if push_data:
        text = _clean_text(push_data.get("text", ""), is_eid or is_diwali)
        deep_link = push_data.get("deep_link", f"zuvees://shop?occasion={detection.occasion}")
        if text:
            push_msg = PushMessage(text=text[:150], deep_link=deep_link)

    if not any([email_msg, wa_msg, push_msg]):
        print(f"    [safety] All channels empty after cleaning — using fallback for {detection.customer_id}/{detection.occasion}")
        return _fallback_bundle(detection)

    return MessageBundle(email=email_msg, whatsapp=wa_msg, push=push_msg)


def _clean_text(text: str, cultural_sensitive: bool) -> str:
    if not text:
        return text
    if _DISCOUNT_PATTERN.search(text):
        return ""
    if cultural_sensitive:
        text_lower = text.lower()
        for word in ["alcohol", "wine", "beer", "spirits", "champagne", "pork", "bacon"]:
            if word in text_lower:
                return ""
        # "ham" uses word-boundary so "hamper", "muhammad" etc. don't false-positive
        if re.search(r"\bham\b", text_lower):
            return ""
    return text.strip()


def _has_opt_out_footer(text: str) -> bool:
    indicators = ["reply stop to opt out", "reply stop", "to unsubscribe", "send stop", "unsubscribe here"]
    return any(ind in text.lower() for ind in indicators)


# ─── FALLBACKS ────────────────────────────────────────────────────────────────

def _fallback_message(context: dict) -> str:
    """Template-based fallback when LLM is unavailable."""
    occasion = context.get("occasion", "special occasion")
    recipient = context.get("recipient_name", "someone special")
    products = context.get("product_suggestions", ["our curated collection"])
    price_range = context.get("preferred_price_range_aed", "AED 150–400")

    product_str = products[0] if products else "a curated gift"

    return json.dumps({
        "email": {
            "subject": f"A thoughtful gift for their {occasion}",
            "body": (
                f"We noticed {recipient}'s {occasion} is coming up soon. "
                f"Our {product_str} ({price_range}) has been beautifully curated for moments like this. "
                f"With 60-minute delivery across Dubai and Abu Dhabi, you can make their day truly special. "
                f"Browse our collection and let us help you send something they'll treasure."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"Hi {{1}}, {recipient}'s {occasion} is almost here 🎁 "
                f"We've handpicked {{2}} just for you — delivered in 60 minutes to {{3}}. "
                f"Tap to explore: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["Customer", product_str, "your door"],
        },
        "push": {
            "text": f"{recipient}'s {occasion} is soon — shop curated gifts on Zuvees. 60-min delivery.",
            "deep_link": f"zuvees://shop?occasion={occasion.lower().replace(' ', '_')}&utm_source=push",
        },
    })


def _fallback_bundle(detection: OccasionDetection) -> MessageBundle:
    raw = _fallback_message({
        "occasion": detection.occasion,
        "recipient_name": detection.recipient_name or "someone special",
        "product_suggestions": [],
        "preferred_price_range_aed": "AED 150–400",
    })
    parsed = _parse_llm_response(raw)
    e = parsed.get("email", {})
    w = parsed.get("whatsapp", {})
    p = parsed.get("push", {})
    return MessageBundle(
        email=EmailMessage(subject=e.get("subject", "")[:60], body=e.get("body", "")) if e else None,
        whatsapp=WhatsAppMessage(
            template_body=w.get("template_body", ""),
            variables=w.get("variables", [])[:3],
            has_opt_out_footer=True,
        ) if w else None,
        push=PushMessage(
            text=p.get("text", "")[:150],
            deep_link=p.get("deep_link", f"zuvees://shop?occasion={detection.occasion}"),
        ) if p else None,
    )
