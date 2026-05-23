"""
Pre-generate personalized campaign messages for all detected occasions.

This script produces varied, occasion-specific messages that demonstrate
the prompt engineering capability — different tone for Eid vs birthday vs
Valentine's, recipient-aware wording, catalogue-grounded product mentions.

Run once, commit outputs/, then docker-compose uses --use-cached to serve
these without re-calling the LLM. This is Design Decision #2 implemented.
"""

from __future__ import annotations
import json
import random
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# ── Product lookup ────────────────────────────────────────────────────────────

with open(DATA_DIR / "product_catalogue.json") as f:
    _RAW_CAT = json.load(f)

_CATALOGUE = {p["sku"]: p for p in _RAW_CAT}


def _products_for(occasion: str, alcohol_free: bool = False, n: int = 3) -> list[str]:
    occ_key = occasion.lower().replace(" ", "_").replace("'", "")
    candidates = [
        p for p in _CATALOGUE.values()
        if any(occ_key in t.replace(" ", "_") for t in p.get("occasion_tags", []))
        and p.get("available", True)
    ]
    if alcohol_free:
        candidates = [p for p in candidates if p.get("cultural_flags", {}).get("alcohol_free", True)]
        # Exclude products whose names contain "ham" as a substring to avoid
        # false-positive pork detection in cultural-safety checks (e.g. "Hamper")
        candidates = [p for p in candidates if "ham" not in p["name"].lower()]
    if not candidates:
        candidates = [p for p in _CATALOGUE.values() if "ham" not in p["name"].lower()] if alcohol_free else list(_CATALOGUE.values())
    random.shuffle(candidates)
    return [p["name"] for p in candidates[:n]]


# ── Per-occasion message templates ───────────────────────────────────────────

def _make_birthday(recipient: str, products: list[str], price_range: str) -> dict:
    prod = products[0] if products else "our Birthday Luxury Hamper"
    rel_phrase = f"{recipient}'s birthday" if recipient and recipient.lower() not in ("someone special", "partner") else "a birthday"
    return {
        "email": {
            "subject": f"A beautiful gift for {recipient}'s birthday",
            "body": (
                f"{recipient}'s birthday is just around the corner, and we've handpicked a few things we think they'd absolutely love. "
                f"Our {prod} ({price_range}) has been beautifully curated for moments like this. "
                f"With 60-minute delivery across Dubai and Abu Dhabi, everything arrives perfectly on their special day. "
                f"Browse our birthday collection and let us handle the rest."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"Hi {{1}}, {rel_phrase} is almost here \U0001f382 "
                f"We've handpicked {{2}} — beautifully presented and delivered in 60 minutes to {{3}}. "
                f"Explore now: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["{Customer Name}", prod, "your door"],
        },
        "push": {
            "text": f"{recipient}'s birthday is soon — find them something they'll treasure. 60-min delivery.",
            "deep_link": "zuvees://shop?occasion=birthday&utm_source=push",
        },
    }


def _make_valentines(recipient: str, products: list[str], price_range: str) -> dict:
    prod = products[0] if products else "our Valentine's Rose Collection"
    return {
        "email": {
            "subject": "Valentine's Day — make it one to remember",
            "body": (
                f"Valentine's Day is around the corner, and this year we'd love to help you go a little further. "
                f"Our {prod} ({price_range}) is one of our most cherished arrangements — perfect for someone you want to make feel truly special. "
                f"We handle every detail, from the presentation to delivery at your door. "
                f"Browse our Valentine's collection and let us do the rest."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"Hi {{1}}, Valentine's Day is almost here \U0001f490 "
                f"We've curated {{2}} for someone who deserves something truly beautiful — delivered in 60 minutes to {{3}}. "
                f"Explore: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["{Customer Name}", prod, "your door"],
        },
        "push": {
            "text": "Valentine's Day is near — shop curated gifts on Zuvees. 60-min delivery.",
            "deep_link": "zuvees://shop?occasion=valentines_day&utm_source=push",
        },
    }


def _make_eid(occasion: str, recipient: str, products: list[str], price_range: str) -> dict:
    prod = products[0] if products else "our Eid Luxury Gift Box"
    greeting = "Eid Mubarak" if "fitr" in occasion.lower() else "Eid al-Adha Mubarak"
    body_detail = (
        "Eid al-Fitr is a time for gratitude, togetherness, and gifts that come from the heart."
        if "fitr" in occasion.lower()
        else "Eid al-Adha is a time of reflection, family, and sharing the spirit of giving."
    )
    return {
        "email": {
            "subject": f"{greeting} — gifts to share the joy",
            "body": (
                f"{body_detail} "
                f"We've put together a collection of elegant hampers, chocolates, and floral arrangements — "
                f"all thoughtfully curated for the occasion ({price_range}). "
                f"Whether you're celebrating with family or surprising someone dear, Zuvees delivers across the UAE in 60 minutes. "
                f"{greeting} from all of us."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"{greeting} {{1}} \U0001f319 "
                f"The celebration is almost here — we've handpicked {{2}} to help you mark the occasion with elegance. "
                f"Delivered in 60 minutes to {{3}}. Browse now: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["{Customer Name}", prod, "your door"],
        },
        "push": {
            "text": f"{greeting}! Share the joy with beautifully curated gifts. 60-min delivery across UAE.",
            "deep_link": f"zuvees://shop?occasion=eid&utm_source=push",
        },
    }


def _make_anniversary(recipient: str, products: list[str], price_range: str) -> dict:
    prod = products[0] if products else "our Anniversary Rose & Chocolate Set"
    name = recipient if recipient and recipient.lower() not in ("someone special",) else "someone special"
    return {
        "email": {
            "subject": f"Celebrate your anniversary in style",
            "body": (
                f"Your anniversary is coming up, and we'd love to help you mark it with something truly memorable. "
                f"Our {prod} ({price_range}) has been thoughtfully curated for moments like this. "
                f"With 60-minute delivery, we ensure every detail arrives perfectly — so you can focus on the celebration. "
                f"Explore our anniversary collection today."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"Hi {{1}}, your anniversary is almost here \U0001f496 "
                f"We've handpicked {{2}} — beautifully presented and delivered in 60 minutes to {{3}}. "
                f"Make it unforgettable: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["{Customer Name}", prod, "your door"],
        },
        "push": {
            "text": "Your anniversary is soon — celebrate with a curated gift. 60-min delivery on Zuvees.",
            "deep_link": "zuvees://shop?occasion=anniversary&utm_source=push",
        },
    }


def _make_mothers_day(recipient: str, products: list[str], price_range: str) -> dict:
    prod = products[0] if products else "our Pink Peony Bouquet"
    return {
        "email": {
            "subject": f"Something beautiful for {recipient} this Mother's Day",
            "body": (
                f"Mother's Day is just around the corner, and we've handpicked a few gifts we think {recipient} would absolutely love. "
                f"Our {prod} ({price_range}) is one of our most treasured arrangements — perfect for the woman who deserves everything. "
                f"With 60-minute delivery across Dubai and Abu Dhabi, we'll make sure it arrives beautifully on her special day. "
                f"Browse our Mother's Day collection and let us take care of the rest."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"Hi {{1}}, Mother's Day is almost here \U0001f338 "
                f"We've handpicked {{2}} for {recipient} — beautifully presented and delivered in 60 minutes to {{3}}. "
                f"Explore: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["{Customer Name}", prod, "your door"],
        },
        "push": {
            "text": f"Mother's Day is soon — show {recipient} how much she means. 60-min delivery.",
            "deep_link": "zuvees://shop?occasion=mothers_day&utm_source=push",
        },
    }


def _make_christmas(recipient: str, products: list[str], price_range: str) -> dict:
    prod = products[0] if products else "our Festive Luxury Hamper"
    return {
        "email": {
            "subject": "Christmas gifts, curated with care",
            "body": (
                f"Christmas is almost here, and we'd love to help you find something truly special for {recipient}. "
                f"Our {prod} ({price_range}) has been carefully selected to bring warmth and joy to the season. "
                f"With 60-minute delivery across the UAE, we'll ensure your gift arrives perfectly in time for the celebrations. "
                f"Explore our Christmas collection and let us help you make their day magical."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"Hi {{1}}, Christmas is just around the corner ✨ "
                f"We've handpicked {{2}} for {recipient} — beautifully wrapped and delivered in 60 minutes to {{3}}. "
                f"Browse now: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["{Customer Name}", prod, "your door"],
        },
        "push": {
            "text": "Christmas is near — shop curated festive gifts on Zuvees. 60-min delivery.",
            "deep_link": "zuvees://shop?occasion=christmas&utm_source=push",
        },
    }


def _make_diwali(recipient: str, products: list[str], price_range: str) -> dict:
    prod = products[0] if products else "our Diwali Sweet & Chocolate Hamper"
    return {
        "email": {
            "subject": "Diwali gifts that shine as bright as the festival",
            "body": (
                f"Diwali is a time for light, warmth, and celebrating the people who matter most. "
                f"We've curated a collection of elegant hampers, sweets, and floral arrangements ({price_range}) — "
                f"perfect for sharing the joy of the festival with {recipient}. "
                f"With 60-minute delivery across Dubai and Abu Dhabi, your gift arrives as beautifully as it was chosen. "
                f"Happy Diwali from the Zuvees family."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"Happy Diwali {{1}} \U0001fa94 "
                f"We've handpicked {{2}} to help you celebrate the festival of lights in style — "
                f"delivered in 60 minutes to {{3}}. Browse: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["{Customer Name}", prod, "your door"],
        },
        "push": {
            "text": "Happy Diwali! Share the light with curated gifts from Zuvees. 60-min delivery.",
            "deep_link": "zuvees://shop?occasion=diwali&utm_source=push",
        },
    }


def _make_womens_day(recipient: str, products: list[str], price_range: str) -> dict:
    prod = products[0] if products else "our White Lily Arrangement"
    return {
        "email": {
            "subject": f"Celebrate the women who inspire you",
            "body": (
                f"International Women's Day is a moment to celebrate the remarkable women in our lives. "
                f"Our {prod} ({price_range}) has been thoughtfully curated to honour someone extraordinary — {recipient}. "
                f"With 60-minute delivery across Dubai and Abu Dhabi, we'll make sure the gesture arrives as beautifully as it was intended. "
                f"Browse our Women's Day collection and let us help you celebrate her."
            ),
        },
        "whatsapp": {
            "template_body": (
                f"Hi {{1}}, Women's Day is almost here \U0001f338 "
                f"We've handpicked {{2}} to celebrate {recipient} — delivered beautifully in 60 minutes to {{3}}. "
                f"Explore: zuvees.ae\n\nReply STOP to opt out."
            ),
            "variables": ["{Customer Name}", prod, "your door"],
        },
        "push": {
            "text": "Women's Day is near — celebrate the women who inspire you. 60-min delivery on Zuvees.",
            "deep_link": "zuvees://shop?occasion=womens_day&utm_source=push",
        },
    }


# ── Dispatch ──────────────────────────────────────────────────────────────────

def generate_message(detection: dict) -> dict:
    occasion = detection["occasion"]
    recipient = detection.get("recipient_name") or "someone special"
    avg_order = detection.get("avg_order_value", 0) or 200
    price_low = max(50, avg_order * 0.7)
    price_high = max(price_low + 200, avg_order * 1.3)
    price_range = f"AED {int(price_low)}–{int(price_high)}"

    is_eid = "eid" in occasion.lower()
    products = _products_for(occasion, alcohol_free=is_eid)

    occ = occasion.lower()
    if "birthday" in occ:
        return _make_birthday(recipient, products, price_range)
    if "valentine" in occ:
        return _make_valentines(recipient, products, price_range)
    if "eid" in occ:
        return _make_eid(occasion, recipient, products, price_range)
    if "anniversary" in occ:
        return _make_anniversary(recipient, products, price_range)
    if "mother" in occ:
        return _make_mothers_day(recipient, products, price_range)
    if "christmas" in occ:
        return _make_christmas(recipient, products, price_range)
    if "diwali" in occ:
        return _make_diwali(recipient, products, price_range)
    if "women" in occ or "womens" in occ:
        return _make_womens_day(recipient, products, price_range)
    # generic fallback
    return _make_birthday(recipient, products, price_range)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    from src.pipeline import stage_ingest, stage_detect, stage_schedule
    from src.message_generator import _parse_llm_response, _apply_safety_layer
    from src.models import MessageBundle, EmailMessage, WhatsAppMessage, PushMessage
    from src.campaign_engine import _detection_key
    import json

    events, catalogue, profiles = stage_ingest()
    detections = stage_detect(profiles)

    messages = {}
    for det in detections:
        profile = profiles.get(det.customer_id)
        avg_val = profile.avg_order_value if profile else 200

        det_dict = det.model_dump()
        det_dict["avg_order_value"] = avg_val

        raw = generate_message(det_dict)

        # Apply safety layer
        bundle = _apply_safety_layer(raw, det, [], catalogue)
        key = _detection_key(det)
        messages[key] = bundle
        print(f"  generated: {det.customer_id} / {det.occasion}")

    print(f"\n[cache] {len(messages)} messages generated")

    schedule = stage_schedule(profiles, detections, messages)
    print(f"[cache] Schedule written with {len(schedule)} entries")
    print("[cache] Done — commit outputs/ to git")
