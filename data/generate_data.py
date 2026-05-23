"""
Synthetic data generator for Zuvees Campaign Orchestration Engine.
Produces product_catalogue.json (100 SKUs) and synthetic_events.json (~250 events, 25 customers).
"""

import json
import uuid
import random
from datetime import datetime, timedelta, date
import pytz

random.seed(42)

# ─── PRODUCT CATALOGUE ────────────────────────────────────────────────────────

FLOWER_NAMES = [
    "Red Rose Bouquet (12 stems)", "White Lily Arrangement", "Mixed Wildflower Bunch",
    "Pink Peony Bouquet", "Sunflower Delight (6 stems)", "Orchid in Pot",
    "Lavender Dream Bouquet", "Tulip Collection (15 stems)", "Jasmine Garland",
    "Pastel Carnation Bouquet", "Yellow Freesia Bundle", "Blue Iris Arrangement",
    "Premium Red Roses (24 stems)", "Baby's Breath Cloud", "Hydrangea Bliss Bouquet",
    "Daisy Garden Mix", "Chrysanthemum Wreath", "Exotic Bird of Paradise",
    "Cherry Blossom Stem Bouquet", "Romantic Rose & Lily Combo",
]

CAKE_NAMES = [
    "Dark Chocolate Truffle Cake", "Vanilla Bean Dream Cake", "Red Velvet Celebration Cake",
    "Strawberry Shortcake", "Caramel Lotus Biscoff Cake", "Pistachio Rose Cake",
    "Mango Mousse Cake", "Lemon Drizzle Layer Cake", "Hazelnut Praline Cake",
    "Black Forest Gateau", "Tres Leches Cake", "Kunafa Cheesecake Fusion",
    "Saffron & Cardamom Cake", "Blueberry Chiffon Cake", "Tiramisu Tower Cake",
    "Cookie & Cream Ice Cream Cake", "Ferrero Rocher Drip Cake",
    "Salted Caramel Bundt Cake", "Pineapple Upside Down Cake", "Churros Cake",
]

CHOCOLATE_NAMES = [
    "Godiva Assorted Truffles Box (16pc)", "Lindt Gold Box Assortment",
    "Belgian Dark Chocolate Bark", "Milk Chocolate Praline Selection",
    "Haribo Gummy & Chocolate Tower", "Ferrero Rocher Gift Tin (24pc)",
    "Patchi Luxury Date & Chocolate Box", "White Chocolate Raspberry Bark",
    "Sugar-Free Dark Chocolate Set", "Kinder Bueno Gift Hamper",
    "Artisan Salted Caramel Bonbons", "Valrhona Single Origin Bar Set",
    "Rose & Pistachio Chocolate Slab", "Nutella Swirl Chocolate Box",
    "Toblerone Tower Set",
]

HAMPER_NAMES = [
    "Luxury Date & Nut Hamper", "Arabian Nights Gift Basket",
    "Wellness & Self-Care Hamper", "Tea & Biscuit Indulgence Box",
    "Baby Shower Celebration Hamper", "Gourmet Cheese & Crackers Basket",
    "Birthday Celebration Mega Hamper", "Spa & Relaxation Gift Set",
    "Ramadan Family Sharing Hamper", "Premium Coffee & Sweets Basket",
    "Eid Mubarak Luxury Gift Box", "New Home Housewarming Hamper",
    "Fruit & Nut Paradise Basket", "Mother's Love Pampering Hamper",
    "Corporate Gratitude Gift Box", "His & Hers Pamper Bundle",
    "Kids Birthday Fun Box", "Diwali Celebration Hamper",
    "Winter Warmth Gift Basket", "Picnic in the Park Hamper",
]

PERFUME_NAMES = [
    "Oud Royale Eau de Parfum 100ml", "Rose Arabica Parfum 50ml",
    "Musk & Amber Night Spray", "Jasmine Bloom EDP 75ml",
    "Sandalwood Serenity Cologne", "Saffron & Gold Parfum 100ml",
    "Midnight Oud Intense 50ml", "Fresh Citrus Burst EDT 100ml",
    "Bakhoor Concentrated Perfume Oil", "Frankincense & Myrrh Roll-On",
    "Lavender Mist Body Spray", "Velvet Rose Parfum 80ml",
    "Ocean Breeze Unisex EDT", "Vanilla Musk Signature Spray",
    "Cedar & Vetiver Parfum 100ml",
]

COMBO_NAMES = [
    "Roses & Red Velvet Cake Combo", "Orchid & Godiva Chocolates Set",
    "Sunflowers & Birthday Cake Bundle", "Peony & Perfume Gift Set",
    "Tulip Bouquet & Patchi Box Combo", "Lilies & Luxury Hamper Bundle",
    "Rose Bouquet & Tiramisu Combo", "Wildflower & Wellness Hamper Set",
    "Bouquet & Belgian Chocolate Duo", "Premium Rose & Oud Perfume Gift",
]

OCCASION_TAGS_MAP = {
    "flowers": ["birthday", "anniversary", "mothers_day", "valentines_day", "eid", "graduation", "womens_day", "get_well"],
    "cakes": ["birthday", "anniversary", "graduation", "christmas", "diwali", "eid"],
    "chocolates": ["valentines_day", "eid", "diwali", "christmas", "birthday", "thank_you"],
    "hampers": ["eid", "diwali", "christmas", "new_home", "corporate", "baby_shower", "birthday", "ramadan"],
    "perfumes": ["eid", "birthday", "anniversary", "valentines_day", "christmas", "graduation"],
    "combos": ["birthday", "anniversary", "valentines_day", "mothers_day", "eid", "diwali"],
}

PRICE_RANGES = {
    "flowers": (49, 450),
    "cakes": (89, 380),
    "chocolates": (39, 280),
    "hampers": (149, 850),
    "perfumes": (99, 650),
    "combos": (149, 750),
}


def make_catalogue():
    catalogue = []
    sku_counter = 1000

    categories = [
        ("flowers", FLOWER_NAMES),
        ("cakes", CAKE_NAMES),
        ("chocolates", CHOCOLATE_NAMES),
        ("hampers", HAMPER_NAMES),
        ("perfumes", PERFUME_NAMES),
        ("combos", COMBO_NAMES),
    ]

    for cat, names in categories:
        for name in names:
            low, high = PRICE_RANGES[cat]
            price = round(random.uniform(low, high), 2)
            tags = random.sample(OCCASION_TAGS_MAP[cat], k=min(3, len(OCCASION_TAGS_MAP[cat])))

            alcohol_free = cat not in ["chocolates"] or random.random() > 0.15
            halal = True
            vegan = cat == "flowers" or (cat in ["chocolates", "hampers"] and random.random() > 0.7)

            catalogue.append({
                "sku": f"ZUV-{sku_counter}",
                "name": name,
                "category": cat,
                "price_aed": price,
                "occasion_tags": tags,
                "cultural_flags": {
                    "alcohol_free": alcohol_free,
                    "halal": halal,
                    "vegan": vegan,
                },
                "available": random.random() > 0.05,
            })
            sku_counter += 1

    return catalogue


# ─── CUSTOMER PROFILES ────────────────────────────────────────────────────────

CUSTOMERS = [
    # UAE residents - Arab/Muslim names
    {"id": "CUST001", "name": "Fatima Al Mansoori", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "uae_female_25_35", "religion": "muslim"},
    {"id": "CUST002", "name": "Mohammed Al Rashidi", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": False, "segment": "uae_male_35_45", "religion": "muslim"},
    {"id": "CUST003", "name": "Aisha Khalid", "tz": "Asia/Dubai", "email_optin": False, "wa_optin": True, "push_optin": True, "segment": "uae_female_25_35", "religion": "muslim"},
    {"id": "CUST004", "name": "Omar Bin Hamdan", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": False, "segment": "uae_male_25_35", "religion": "muslim"},
    {"id": "CUST005", "name": "Noor Al Zaabi", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": False, "push_optin": True, "segment": "uae_female_35_45", "religion": "muslim"},

    # UAE residents - Indian expats
    {"id": "CUST006", "name": "Priya Nair", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "uae_female_25_35", "religion": "hindu"},
    {"id": "CUST007", "name": "Rahul Sharma", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "uae_male_25_35", "religion": "hindu"},
    {"id": "CUST008", "name": "Ananya Menon", "tz": "Asia/Dubai", "email_optin": False, "wa_optin": True, "push_optin": False, "segment": "uae_female_25_35", "religion": "hindu"},
    {"id": "CUST009", "name": "Vikram Patel", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "uae_male_35_45", "religion": "hindu"},
    {"id": "CUST010", "name": "Deepa Krishnamurthy", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": False, "push_optin": True, "segment": "uae_female_35_45", "religion": "hindu"},

    # UAE residents - Western expats
    {"id": "CUST011", "name": "Sarah Mitchell", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "uae_female_25_35", "religion": "other"},
    {"id": "CUST012", "name": "James Anderson", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": False, "push_optin": False, "segment": "uae_male_35_45", "religion": "other"},
    {"id": "CUST013", "name": "Emma Clarke", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "uae_female_25_35", "religion": "other"},
    {"id": "CUST014", "name": "David Thompson", "tz": "Asia/Dubai", "email_optin": False, "wa_optin": True, "push_optin": True, "segment": "uae_male_25_35", "religion": "other"},
    {"id": "CUST015", "name": "Sophie Laurent", "tz": "Asia/Dubai", "email_optin": True, "wa_optin": True, "push_optin": False, "segment": "uae_female_35_45", "religion": "other"},

    # India-based customers
    {"id": "CUST016", "name": "Arjun Mehta", "tz": "Asia/Kolkata", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "india_male_25_35", "religion": "hindu"},
    {"id": "CUST017", "name": "Kavya Reddy", "tz": "Asia/Kolkata", "email_optin": True, "wa_optin": True, "push_optin": False, "segment": "india_female_25_35", "religion": "hindu"},
    {"id": "CUST018", "name": "Siddharth Joshi", "tz": "Asia/Kolkata", "email_optin": True, "wa_optin": False, "push_optin": True, "segment": "india_male_35_45", "religion": "hindu"},
    {"id": "CUST019", "name": "Pooja Agarwal", "tz": "Asia/Kolkata", "email_optin": False, "wa_optin": True, "push_optin": True, "segment": "india_female_25_35", "religion": "hindu"},
    {"id": "CUST020", "name": "Rajesh Kumar", "tz": "Asia/Kolkata", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "india_male_25_35", "religion": "hindu"},

    # UK-based customers
    {"id": "CUST021", "name": "Charlotte Williams", "tz": "Europe/London", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "uk_female_25_35", "religion": "other"},
    {"id": "CUST022", "name": "Oliver Brown", "tz": "Europe/London", "email_optin": True, "wa_optin": False, "push_optin": True, "segment": "uk_male_35_45", "religion": "other"},
    {"id": "CUST023", "name": "Amira Hassan", "tz": "Europe/London", "email_optin": True, "wa_optin": True, "push_optin": False, "segment": "uk_female_25_35", "religion": "muslim"},
    {"id": "CUST024", "name": "Ben Davies", "tz": "Europe/London", "email_optin": False, "wa_optin": True, "push_optin": True, "segment": "uk_male_25_35", "religion": "other"},
    {"id": "CUST025", "name": "Yasmin Patel", "tz": "Europe/London", "email_optin": True, "wa_optin": True, "push_optin": True, "segment": "uk_female_25_35", "religion": "muslim"},
]

CUSTOMER_MAP = {c["id"]: c for c in CUSTOMERS}

# ─── KEY DATES ────────────────────────────────────────────────────────────────

# Gregorian
VALENTINES_2025 = date(2025, 2, 14)
WOMENS_DAY_2025 = date(2025, 3, 8)
MOTHERS_DAY_2025 = date(2025, 5, 11)
FATHERS_DAY_2025 = date(2025, 6, 15)
DIWALI_2025 = date(2025, 10, 20)
CHRISTMAS_2025 = date(2025, 12, 25)
VALENTINES_2026 = date(2026, 2, 14)
WOMENS_DAY_2026 = date(2026, 3, 8)
MOTHERS_DAY_2026 = date(2026, 5, 10)

# Islamic calendar (approximate Gregorian equivalents)
EID_FITR_2025 = date(2025, 3, 30)
EID_ADHA_2025 = date(2025, 6, 6)
EID_FITR_2026 = date(2026, 3, 20)
EID_ADHA_2026 = date(2026, 5, 27)

START_DATE = date(2025, 3, 1)
TODAY = date(2026, 5, 19)

CATALOGUE_GLOBAL = make_catalogue()
CAT_BY_OCCASION = {}
for p in CATALOGUE_GLOBAL:
    for tag in p["occasion_tags"]:
        CAT_BY_OCCASION.setdefault(tag, []).append(p)

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def rand_sku_for_occasion(occasion, exclude_alcohol=False):
    pool = CAT_BY_OCCASION.get(occasion, CATALOGUE_GLOBAL)
    if exclude_alcohol:
        pool = [p for p in pool if p["cultural_flags"]["alcohol_free"]]
    if not pool:
        pool = [p for p in CATALOGUE_GLOBAL if p["cultural_flags"]["alcohol_free"]]
    p = random.choice(pool)
    return {"sku": p["sku"], "name": p["name"], "price": p["price_aed"], "category": p["category"]}

def make_order_event(customer, event_date, occasion, recipient_name, recipient_rel, is_muslim_occasion=False, email_opened=False):
    tz = pytz.timezone(customer["tz"])
    hour = random.randint(10, 21)
    dt = tz.localize(datetime(event_date.year, event_date.month, event_date.day, hour,
                              random.randint(0, 59)))
    item = rand_sku_for_occasion(occasion, exclude_alcohol=is_muslim_occasion)
    qty = random.randint(1, 2)
    total = round(item["price"] * qty * random.uniform(0.9, 1.1), 2)
    return {
        "event_id": str(uuid.uuid4()),
        "customer_id": customer["id"],
        "event_type": "order",
        "timestamp": dt.isoformat(),
        "data": {
            "order_id": f"ORD-{uuid.uuid4().hex[:8].upper()}",
            "line_items": [{"sku": item["sku"], "name": item["name"], "price": item["price"], "category": item["category"]}],
            "occasion_tag": occasion,
            "recipient_name": recipient_name,
            "recipient_relationship": recipient_rel,
            "total_aed": total,
            "delivery_area": "Al Quoz" if customer["tz"] == "Asia/Dubai" else "Online",
            "email_opened": email_opened,
        }
    }

def make_browse_event(customer, event_date, offset_minutes=0):
    tz = pytz.timezone(customer["tz"])
    hour = random.randint(8, 23)
    dt = tz.localize(datetime(event_date.year, event_date.month, event_date.day, hour,
                              random.randint(0, 59)))
    dt -= timedelta(minutes=offset_minutes)
    prod = random.choice(CATALOGUE_GLOBAL)
    return {
        "event_id": str(uuid.uuid4()),
        "customer_id": customer["id"],
        "event_type": "browse",
        "timestamp": dt.isoformat(),
        "data": {
            "page_url": f"https://zuvees.ae/products/{prod['sku'].lower()}",
            "product_sku": prod["sku"],
            "category": prod["category"],
            "time_spent_seconds": random.randint(30, 420),
        }
    }

def make_whatsapp_event(customer, event_date, opted_out=False, direction="outbound"):
    tz = pytz.timezone(customer["tz"])
    hour = random.randint(9, 22)
    dt = tz.localize(datetime(event_date.year, event_date.month, event_date.day, hour,
                              random.randint(0, 59)))
    templates = ["order_confirmation", "delivery_update", "occasion_reminder", "welcome_message"]
    return {
        "event_id": str(uuid.uuid4()),
        "customer_id": customer["id"],
        "event_type": "whatsapp_interaction",
        "timestamp": dt.isoformat(),
        "data": {
            "direction": direction,
            "template_name": random.choice(templates),
            "read": random.random() > 0.3,
            "opted_out": opted_out,
        }
    }

def make_profile_update(customer, field, value, recipient_name=None):
    tz = pytz.timezone(customer["tz"])
    event_date = START_DATE + timedelta(days=random.randint(0, 30))
    dt = tz.localize(datetime(event_date.year, event_date.month, event_date.day,
                              random.randint(9, 17), random.randint(0, 59)))
    event = {
        "event_id": str(uuid.uuid4()),
        "customer_id": customer["id"],
        "event_type": "profile_update",
        "timestamp": dt.isoformat(),
        "data": {
            "field": field,
            "value": value,
        }
    }
    if recipient_name:
        event["data"]["recipient_name"] = recipient_name
    return event


# ─── EVENT GENERATION ─────────────────────────────────────────────────────────

def generate_events():
    events = []

    # 1) PROFILE UPDATES: explicit birthday/anniversary saves (→ high confidence)
    profile_updates = [
        # Upcoming within next 9 months
        ("CUST001", "birthday", "1992-07-15", "Husband"),      # Jul 15
        ("CUST002", "birthday", "1988-09-22", "Wife"),         # Sep 22
        ("CUST003", "anniversary", "2019-06-10", "Husband"),   # Jun 10
        ("CUST006", "birthday", "1990-12-05", "Mom"),          # Dec 5
        ("CUST007", "anniversary", "2020-08-14", "Wife"),      # Aug 14
        ("CUST009", "birthday", "1965-08-03", "Dad"),          # Aug 3
        ("CUST011", "birthday", "1994-11-28", "Sister"),       # Nov 28
        ("CUST013", "anniversary", "2018-06-20", "Partner"),   # Jun 20
        ("CUST016", "birthday", "1991-10-17", "Mom"),          # Oct 17
        ("CUST021", "birthday", "1993-07-30", "Best Friend"),  # Jul 30
        # More upcoming dates
        ("CUST004", "birthday", "1990-07-22", "Wife"),         # Jul 22
        ("CUST005", "anniversary", "2018-09-01", "Husband"),   # Sep 1
        ("CUST008", "birthday", "1993-08-19", "Mom"),          # Aug 19
        ("CUST010", "anniversary", "2016-11-05", "Husband"),   # Nov 5
        ("CUST012", "birthday", "1987-10-08", "Wife"),         # Oct 8
        ("CUST014", "birthday", "1995-07-04", "Partner"),      # Jul 4
        ("CUST015", "anniversary", "2019-06-28", "Partner"),   # Jun 28
        ("CUST017", "birthday", "1992-12-12", "Dad"),          # Dec 12
        ("CUST018", "anniversary", "2020-10-20", "Wife"),      # Oct 20
        ("CUST019", "birthday", "1994-08-30", "Mom"),          # Aug 30
        ("CUST020", "birthday", "1991-11-15", "Sister"),       # Nov 15
        ("CUST022", "birthday", "1989-09-14", "Wife"),         # Sep 14
        ("CUST023", "anniversary", "2017-07-07", "Husband"),   # Jul 7
        ("CUST024", "birthday", "1996-10-25", "Mom"),          # Oct 25
        ("CUST025", "anniversary", "2020-12-01", "Husband"),   # Dec 1
    ]
    for cid, field, val, recip in profile_updates:
        events.append(make_profile_update(CUSTOMER_MAP[cid], field, val, recip))

    # 2) VALENTINE'S DAY 2025 orders (Feb 14)
    valentines_buyers = ["CUST007", "CUST011", "CUST013", "CUST021",
                         "CUST003", "CUST022",
                         "CUST004", "CUST009", "CUST016", "CUST025"]
    for cid in valentines_buyers:
        c = CUSTOMER_MAP[cid]
        recipient = "Partner" if c["id"] in ["CUST007"] else "Boyfriend/Girlfriend"
        email_opened = bool(CUSTOMER_MAP[cid]["email_optin"])
        events.append(make_order_event(c, VALENTINES_2025, "valentines_day", "Partner", recipient,
                                       email_opened=email_opened))
        events.append(make_browse_event(c, VALENTINES_2025 - timedelta(days=2)))

    # 3) VALENTINE'S DAY 2026 orders (repeat buyers → medium confidence for next year)
    valentines_2026_buyers = ["CUST007", "CUST011", "CUST013", "CUST021", "CUST004", "CUST016"]
    for cid in valentines_2026_buyers:
        c = CUSTOMER_MAP[cid]
        email_opened = bool(CUSTOMER_MAP[cid]["email_optin"])
        events.append(make_order_event(c, VALENTINES_2026, "valentines_day", "Partner", "Boyfriend/Girlfriend",
                                       email_opened=email_opened))

    # 4) WOMEN'S DAY 2025 orders (March 8) → infer repeat next year
    womens_day_buyers = ["CUST001", "CUST006", "CUST015"]
    for cid in womens_day_buyers:
        c = CUSTOMER_MAP[cid]
        events.append(make_order_event(c, WOMENS_DAY_2025, "womens_day", "Mom", "Mother"))

    # 5) EID AL-FITR 2025 (March 30) - Muslim customers
    eid_fitr_2025_buyers = ["CUST001", "CUST002", "CUST003", "CUST004", "CUST023"]
    eid_recipients = [("Parents", "Parents"), ("Wife", "Spouse"), ("Mom", "Mother"),
                      ("Family", "Family"), ("Sister", "Sibling")]
    for cid in eid_fitr_2025_buyers:
        c = CUSTOMER_MAP[cid]
        recip_name, recip_rel = random.choice(eid_recipients)
        events.append(make_order_event(c, EID_FITR_2025, "eid", recip_name, recip_rel, is_muslim_occasion=True))
        events.append(make_browse_event(c, EID_FITR_2025 - timedelta(days=3)))

    # 6) EID AL-ADHA 2025 (June 6)
    eid_adha_2025_buyers = ["CUST002", "CUST004", "CUST005"]
    for cid in eid_adha_2025_buyers:
        c = CUSTOMER_MAP[cid]
        recip_name, recip_rel = random.choice(eid_recipients)
        events.append(make_order_event(c, EID_ADHA_2025, "eid", recip_name, recip_rel, is_muslim_occasion=True))

    # 7) MOTHER'S DAY 2025 (May 11)
    mothers_day_buyers = [
        ("CUST006", "Mom", "Mother"),
        ("CUST007", "Mom", "Mother"),
        ("CUST009", "Mom", "Mother"),
        ("CUST011", "Mum", "Mother"),
        ("CUST016", "Mom", "Mother"),
        ("CUST017", "Amma", "Mother"),
        ("CUST021", "Mum", "Mother"),
    ]
    for cid, recip_name, recip_rel in mothers_day_buyers:
        c = CUSTOMER_MAP[cid]
        events.append(make_order_event(c, MOTHERS_DAY_2025, "mothers_day", recip_name, recip_rel))
        events.append(make_browse_event(c, MOTHERS_DAY_2025 - timedelta(days=4)))

    # 8) DIWALI 2025 (Oct 20) - Hindu customers
    diwali_buyers = ["CUST006", "CUST007", "CUST008", "CUST009", "CUST016",
                     "CUST017", "CUST019"]
    for cid in diwali_buyers:
        c = CUSTOMER_MAP[cid]
        recip_name, recip_rel = random.choice([("Family", "Family"), ("Parents", "Parents"), ("Friends", "Friends")])
        events.append(make_order_event(c, DIWALI_2025, "diwali", recip_name, recip_rel))

    # 9) CHRISTMAS 2025 - Western customers
    christmas_buyers = ["CUST011", "CUST012", "CUST013", "CUST021", "CUST022"]
    for cid in christmas_buyers:
        c = CUSTOMER_MAP[cid]
        email_opened = bool(CUSTOMER_MAP[cid]["email_optin"])
        events.append(make_order_event(c, CHRISTMAS_2025, "christmas", "Family", "Family",
                                       email_opened=email_opened))
        events.append(make_browse_event(c, CHRISTMAS_2025 - timedelta(days=5)))

    # 10) BIRTHDAY orders based on profile-saved birthdays (high confidence evidence)
    birthday_orders = [
        ("CUST001", date(2025, 7, 15), "Husband", "Spouse"),
        ("CUST002", date(2025, 9, 22), "Wife", "Spouse"),
        ("CUST006", date(2025, 12, 5), "Mom", "Mother"),
        ("CUST009", date(2025, 8, 3), "Dad", "Father"),
        ("CUST016", date(2025, 3, 17), "Mom", "Mother"),
    ]
    for cid, bday, recip_name, recip_rel in birthday_orders:
        c = CUSTOMER_MAP[cid]
        events.append(make_order_event(c, bday, "birthday", recip_name, recip_rel))
        events.append(make_browse_event(c, bday - timedelta(days=2)))

    # 11) RECIPIENT CLUSTERING: same customer, same recipient, different occasions
    # CUST007 orders for "Wife" on Valentine's AND Anniversary
    events.append(make_order_event(CUSTOMER_MAP["CUST007"], date(2025, 2, 14),
                                   "anniversary", "Wife", "Spouse"))
    events.append(make_order_event(CUSTOMER_MAP["CUST007"], date(2025, 4, 10),
                                   "anniversary", "Wife", "Spouse"))

    # CUST009: "Dad" for birthday (Aug 3) + Father's Day (June 15)
    events.append(make_order_event(CUSTOMER_MAP["CUST009"], FATHERS_DAY_2025,
                                   "birthday", "Dad", "Father"))

    # 12) EID AL-FITR 2026 (March 20) - same Muslim customers repeat
    eid_fitr_2026_buyers = ["CUST001", "CUST002", "CUST003"]
    for cid in eid_fitr_2026_buyers:
        c = CUSTOMER_MAP[cid]
        recip_name, recip_rel = random.choice(eid_recipients)
        events.append(make_order_event(c, EID_FITR_2026, "eid", recip_name, recip_rel, is_muslim_occasion=True))
        events.append(make_browse_event(c, EID_FITR_2026 - timedelta(days=4)))

    # 13) WOMEN'S DAY 2026 (March 8) - repeat buyers
    womens_day_2026_buyers = ["CUST001", "CUST006"]
    for cid in womens_day_2026_buyers:
        c = CUSTOMER_MAP[cid]
        events.append(make_order_event(c, WOMENS_DAY_2026, "womens_day", "Mom", "Mother"))

    # 14) General browsing events to fill up to 250
    all_event_dates = [START_DATE + timedelta(days=i) for i in range((TODAY - START_DATE).days)]

    # WhatsApp interactions
    wa_customers = [c for c in CUSTOMERS if c["wa_optin"]]
    for _ in range(20):
        c = random.choice(wa_customers)
        d = random.choice(all_event_dates)
        if d < TODAY:
            events.append(make_whatsapp_event(c, d))

    # Opt-out events for some customers (to test consent management)
    opt_out_customers = ["CUST005", "CUST012"]
    for cid in opt_out_customers:
        c = CUSTOMER_MAP[cid]
        d = START_DATE + timedelta(days=random.randint(30, 200))
        events.append(make_whatsapp_event(c, d, opted_out=True))

    # Fill remaining with browse events
    while len(events) < 250:
        c = random.choice(CUSTOMERS)
        days_back = random.randint(1, (TODAY - START_DATE).days)
        d = TODAY - timedelta(days=days_back)
        events.append(make_browse_event(c, d))

    events = events[:250]

    # Sort by timestamp
    events.sort(key=lambda e: e["timestamp"])

    return events


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    base = os.path.dirname(os.path.abspath(__file__))

    catalogue = make_catalogue()
    events = generate_events()

    with open(os.path.join(base, "product_catalogue.json"), "w") as f:
        json.dump(catalogue, f, indent=2)
    print(f"Written product_catalogue.json ({len(catalogue)} SKUs)")

    with open(os.path.join(base, "synthetic_events.json"), "w") as f:
        json.dump(events, f, indent=2)
    print(f"Written synthetic_events.json ({len(events)} events, "
          f"{len(set(e['customer_id'] for e in events))} customers)")
