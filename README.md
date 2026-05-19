# Intelligent Campaign Orchestration Engine

An AI-powered marketing intelligence layer for Zuvees — a premium gifting platform in the UAE — that personalises campaign timing, messaging, and channel selection based on customer occasion patterns.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Campaign Orchestration Pipeline                         │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐ │
│  │ INGEST   │───▶│ DETECT   │───▶│ GENERATE │───▶│SCHEDULE  │───▶│OUTPUT │ │
│  │          │    │          │    │          │    │          │    │ JSON  │ │
│  │ Load     │    │ Occasion │    │ LLM      │    │ Fatigue  │    │files  │ │
│  │ events + │    │ detection│    │ message  │    │ Consent  │    │       │ │
│  │catalogue │    │ (Hijri + │    │generation│    │ Channel  │    │       │ │
│  │ Build    │    │  Gregorian│   │ per      │    │ pref.    │    │       │ │
│  │ profiles │    │  clustering│  │ occasion │    │ Send time│    │       │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └───────┘ │
│                                                                             │
│  Stateless stages: each can run independently via --stage <name>           │
│  Stateful artefacts: outputs/*.json (written to disk between stages)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Component responsibility:**

| Module | Stateless? | Responsibility |
|--------|-----------|----------------|
| `src/ingestor.py` | Yes | Load + validate events; build customer profiles |
| `src/occasion_detector.py` | Yes | Detect upcoming occasions (Gregorian + Hijri) |
| `src/message_generator.py` | Yes | Call Claude API; apply content safety |
| `src/send_time_optimizer.py` | Yes | Per-channel optimal send time |
| `src/campaign_engine.py` | Yes | Fatigue, consent, channel preference, scheduling |
| `src/pipeline.py` | Orchestrator | Chains all stages; CLI entrypoint |

---

## Setup & Running

### Prerequisites
- Docker + Docker Compose

### One-command start

```bash
docker-compose up
```

This runs the full pipeline and writes all output files to `outputs/`.

### With a real LLM (optional)

```bash
ANTHROPIC_API_KEY=sk-ant-... docker-compose up
```

Without the key, the pipeline uses template-based fallback messages (still valid, still passes all schema checks).

### Run specific stage

```bash
docker-compose run campaign-engine python -m src.pipeline --stage detect
docker-compose run campaign-engine python -m src.pipeline --stage schedule --mock-llm
```

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | No | `""` | Anthropic API key. If empty, fallback messages are used. |

### Run tests locally

```bash
pip install -r requirements.txt
python -m pytest tests/ --cov=src --cov-report=term-missing
```

---

## Synthetic Data Design

See [`data/DATA_GENERATION.md`](data/DATA_GENERATION.md) for full details.

**Summary:**
- **50 customers** across 7 geographic regions: UAE (Dubai/Abu Dhabi), India, UK, Canada, Egypt, USA (New York, LA)
- **500+ events** spanning **14 months** (March 2025 – May 2026)
- **7 distinct timezone regions** for timezone-awareness testing
- **Seasonal spikes** built into the data:
  - Valentine's Day (Feb 14)
  - Women's Day (Mar 8)
  - Eid al-Fitr (March 30, 2025 / March 20, 2026)
  - Eid al-Adha (June 6, 2025 / **May 27, 2026** — 8 days from simulation date)
  - Mother's Day (May 2025)
  - Diwali (October 2025)
  - Christmas (December 2025)
- **Cultural diversity**: Muslim (Eid patterns), Hindu (Diwali patterns), Western (Christmas/Valentine's)
- **Cold-start customers** (CUST046–050): 1–2 events each, used to test segment-default fallback
- **Recipient clustering**: multiple customers have ordered for the same recipient (e.g., "Mom") across multiple occasions

---

## Occasion Detection Logic

See `src/occasion_detector.py` for the implementation.

### Algorithm

The engine runs four strategies and deduplicates by `(customer_id, occasion, recipient_name)`, keeping the highest confidence:

**1. Profile saves → high confidence**
```
customer profile_update: { field: "birthday", value: "1990-07-15", recipient_name: "Husband" }
→ detect birthday on 2026-07-15, confidence=high
```

**2. Multi-year order patterns → medium confidence**
```
Order on 2024-02-14 (valentines_day) + Order on 2025-02-14 (valentines_day)
→ 2 years of evidence → confidence=medium → predict 2027-02-14
```

**3. Single order pattern → low confidence**
```
Order on 2025-03-08 (womens_day)
→ 1 data point → confidence=low → predict 2026-03-08
```

**4. Recipient clustering**
```
Customer ordered for "Mom" on Mother's Day AND for "Mom" birthday
→ both occasions modelled independently, both linked to recipient "Mom"
```

### Hijri Calendar Conversion

Islamic calendar occasions (Eid al-Fitr, Eid al-Adha) shift ~11 days earlier each Gregorian year. The engine:

1. Identifies a past Eid order by proximity to known Eid dates
2. Classifies it as Eid al-Fitr (1 Shawwal) or Eid al-Adha (10 Dhul Hijjah)
3. Uses `hijri-converter` to convert today's Gregorian date to Hijri
4. Projects forward to find the next occurrence of that Hijri month/day in Gregorian

```python
from hijri_converter import convert

# Example: find next Eid al-Adha (10 Dhul Hijjah)
today_hijri = convert.Gregorian(2026, 5, 19).to_hijri()  # → 1447-11-21
# Search 1447-12-10 (10 Dhul Hijjah 1447)
g = convert.Hijri(1447, 12, 10).to_gregorian()  # → 2026-05-27
```

### Confidence Scoring

| Confidence | Evidence Required |
|-----------|-----------------|
| `high` | Explicit save in customer profile |
| `medium` | Same occasion ordered in 2+ different years |
| `low` | Single order data point |

---

## Prompt Engineering

All prompt templates live in [`prompts/`](prompts/).

| File | Purpose |
|------|---------|
| `prompts/message_generation.md` | System prompt with brand voice rules, few-shot examples, output schema |
| `prompts/content_safety.md` | Content safety rules referenced in the user message |

### Prompt Structure

```
SYSTEM: [message_generation.md — brand voice, examples, format]
USER:   CUSTOMER CONTEXT: {json context}
        AVAILABLE PRODUCTS: {catalogue items for this occasion}
        CONTENT SAFETY RULES: {content_safety.md}
        Respond ONLY with JSON: {schema}
```

### Key Design Decisions

**Personal but not creepy:** The prompt explicitly defines the line:
- `"We noticed your mum's birthday is coming up"` → GOOD
- `"Based on your 7 previous orders for Recipient: Mom..."` → BAD

**Few-shot examples** cover three scenarios: birthday, Eid, Valentine's repeat-gifter.

**Output schema is in the prompt** to enforce structure and enable deterministic parsing.

### Content Safety Layer (post-generation filter)

Applied in `src/message_generator.py::_apply_safety_layer`:

1. **Discount/sale language:** regex scan → message rejected if found
2. **Cultural sensitivity (Eid/Diwali):** alcohol, pork, non-halal mentions → rejected
3. **WhatsApp constraints:** truncated to 1024 chars; opt-out footer auto-appended if missing
4. **Push constraints:** truncated to 150 chars
5. **Product accuracy:** only names from `_get_product_recommendations()` (which reads from catalogue) are passed to the LLM context

---

## Send-Time Optimisation

Implemented in `src/send_time_optimizer.py`.

### Model

For customers with ≥3 events, the model computes the **mean local hour** of past interactions per channel:
- **WhatsApp:** mean hour of `read=True` WA events
- **Email:** mean hour of order placements (proxy for screen-active time)
- **Push:** mean hour of browse events

### Timezone Handling

All timestamps in `synthetic_events.json` are ISO 8601 with timezone offsets. The optimizer converts each timestamp to the customer's local timezone using `pytz` before extracting the hour.

**Quiet hours enforced:** 11 PM – 6 AM in the customer's local timezone are clamped away.

### Cold-Start Fallback

Customers with < 3 total events use segment-level defaults:

```python
_SEGMENT_DEFAULTS = {
    "uae_female_25_35": (wa=10, email=20, push=9),
    "canada_female_25_35": (wa=10, email=20, push=10),
    ...
}
```

### Urgency Adjustment

| Days until occasion | Adjustment |
|--------------------|-----------|
| < 3 days | −2 hours (send earlier — more time to shop) |
| 3–7 days | −1 hour |
| 7+ days | No adjustment |

---

## Fatigue & Consent

Implemented in `src/campaign_engine.py`.

### Fatigue Management

- **Weekly cap:** ≤ 2 promotional messages per customer across all channels combined
- **Tracking:** `ISO year-week` key per customer, incremented at schedule time
- **Confidence conflict:** if high + low confidence occasions fall in the same week, only the high-confidence one gets a message

### Channel Preference

```
IF email_open_rate == 0.0 AND wa_read_rate > 0.60:
    preferred_channel = whatsapp
ELSE:
    channel_priority = [whatsapp, email, push]
```

The engine iterates the priority list and picks the first opted-in channel.

### Consent Management

Consent is checked from the `CustomerProfile` which reads:
- `email_optin` from the known consent map (set from profile data)
- `wa_optin` — automatically set to `False` if any `opted_out=True` WA event exists for that customer
- `push_optin` from the known consent map

The `consent_status` object in every `ScheduledSend` reflects the full profile state, not just the chosen channel.

---

## Test Strategy

```bash
python -m pytest tests/ --cov=src
# Coverage: 88% across all modules
```

| Test file | What's tested | LLM mocked? |
|-----------|--------------|------------|
| `test_ingestor.py` | Event loading, profile building, consent/timezone inference | N/A |
| `test_occasion_detector.py` | Hijri conversion, confidence scoring, recipient clustering, calendar helpers | N/A |
| `test_message_generator.py` | Content safety, WhatsApp constraints, push length, opt-out footer | Yes |
| `test_send_time_optimizer.py` | Timezone awareness, quiet hours, cold-start, urgency | N/A |
| `test_campaign_engine.py` | Fatigue cap, consent enforcement, channel preference | N/A |
| `test_pipeline.py` | End-to-end integration: detections ≥ 30 sends, no consent violations | Yes |

**LLM calls are mocked in all tests** using `pytest-mock` and a `_MockLLMClient` that returns valid pre-baked JSON without hitting the Anthropic API.

---

## Known Limitations

See also [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for trade-offs.

1. **Send-time model is a mean, not a distribution:** The hour-averaging model will be wrong for bimodal users (check email at 8 AM and 9 PM). A Gaussian Mixture Model would be more accurate.

2. **Hijri dates are approximate:** `hijri-converter` uses astronomical calculations which can be off by 1–2 days vs. official moon-sighting announcements in the UAE. Production would need to use the official GCAM (General Commission for Audio-Visual Media) announcements.

3. **No real-time fatigue state:** The current implementation tracks fatigue within a single pipeline run. In production, fatigue state must be persisted (Redis/DB) to survive multiple pipeline executions per day.

4. **50-customer scale vs. 500:** At 500K customers, the current in-memory approach would OOM. Production needs chunked processing with distributed workers (Celery/Ray).

5. **Product accuracy is prompt-level only:** We pass product names to the LLM context, but we don't validate that the LLM actually used them. A production system would parse LLM output and cross-check every product mention against the catalogue.

6. **Email open rate is approximated:** The pipeline uses order-placement timestamps as a proxy for email open times. Real email open tracking would require ZeptoMail webhook integration.

7. **No A/B testing infrastructure:** The engine generates one message per occasion. Production needs variant generation (2–3 per occasion) and feedback loops to update the send-time model.

---

## Intentional Design Trade-offs

See [`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) for the full numbered list.

**Top 3:**

1. **Static confidence scoring vs. ML scoring** — Used rule-based thresholds (1 year = low, 2+ years = medium) for explainability and speed. An ML model (collaborative filtering or Bayesian update) would be more accurate but adds complexity and training data requirements.

2. **Template-based fallback vs. always-LLM** — Pipeline runs without API key by producing rule-based messages. This enables zero-cost CI testing and demo runs. Trade-off: fallback messages are less personalised.

3. **Batch scheduling vs. event-driven triggers** — The current pipeline is a batch job (suitable for nightly runs). A production-grade system would use Shopify webhooks to trigger occasion detection in real time when a profile update event fires. Batch was chosen to meet the 8–10 hour time constraint.
