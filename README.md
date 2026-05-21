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
│  │ Build    │    │ Gregorian│    │ per      │    │ pref.    │    │       │ │
│  │ profiles │    │ clustering)   │ occasion │    │ Send time│    │       │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └───────┘ │
│                                                                             │
│  Stateless stages: each can run independently via --stage <name>           │
│  Stateful artefacts: outputs/*.json (written to disk between stages)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Component responsibility:**

| Module | Stateless? | Responsibility |
|--------|-----------|----------------|
| `src/ingestor.py` | Yes | Load + validate events; build customer profiles with email open rate, WA read rate |
| `src/occasion_detector.py` | Yes | Detect upcoming occasions (Gregorian + Hijri calendar) |
| `src/message_generator.py` | Yes | Call Cerebras / Groq / Anthropic API; apply content safety layer |
| `src/send_time_optimizer.py` | Yes | Per-channel optimal send time with timezone + urgency |
| `src/campaign_engine.py` | Yes | Fatigue cap, consent enforcement, channel preference, scheduling |
| `src/pipeline.py` | Orchestrator | Chains all stages; CLI entrypoint |

---

## LLM Integration

The engine supports **four LLM tiers** — checked in order at startup:

```
1. Cerebras (Llama 3.1-8b)        ← free tier, fast, OpenAI-compatible API
        ↓ if no key / quota exhausted
2. Groq (Llama 3.1-8b-instant)    ← free tier, 14,400 req/day, OpenAI-compatible
        ↓ if no key
3. Anthropic Claude (claude-sonnet-4-6)  ← paid, highest quality
        ↓ if no key
4. Template fallback               ← no API key needed, always works
```

### Cerebras — Llama 3.1-8b (Primary / Free)

[Cerebras Cloud](https://cloud.cerebras.ai) offers a free tier with the Llama 3.1-8b model. It uses an OpenAI-compatible API so no extra SDK is needed.

```python
# How Cerebras is called in src/message_generator.py
from openai import OpenAI

client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=os.environ["CEREBRAS_API_KEY"],
)
response = client.chat.completions.create(
    model="llama3.1-8b",
    messages=[{"role": "system", "content": system_prompt},
              {"role": "user", "content": user_prompt}],
    max_tokens=1024,
    temperature=0.7,
)
```

### Anthropic Claude (Fallback)

```python
# How Anthropic is called in src/message_generator.py
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}],
)
```

### Template Fallback

When neither API key is set, `_fallback_bundle()` generates rule-compliant messages without any API call. All brand voice rules, WhatsApp opt-out footer, and character limits are still enforced.

---

## Setup & Running

### Prerequisites
- Docker + Docker Compose

### One-command start (no API key needed)

```bash
docker-compose up --build
```

Runs the full pipeline using template fallback messages. All 4 output files are written to `outputs/`.

### With Cerebras Llama 3.1-8b (free — recommended)

Get a free API key at [cloud.cerebras.ai](https://cloud.cerebras.ai).

```bash
# Linux / Mac
CEREBRAS_API_KEY=csk-... docker-compose up --build

# Windows PowerShell
$env:CEREBRAS_API_KEY="csk-..."
docker-compose up --build
```

### With Anthropic Claude

```bash
# Linux / Mac
ANTHROPIC_API_KEY=sk-ant-... docker-compose up --build

# Windows PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-..."
docker-compose up --build
```

### Run locally (without Docker)

```bash
pip install -r requirements.txt

# With Cerebras
$env:CEREBRAS_API_KEY="csk-..."
python -m src.pipeline

# With mock LLM (no key needed, instant)
python -m src.pipeline --mock-llm
```

### Run specific pipeline stage

```bash
python -m src.pipeline --stage ingest
python -m src.pipeline --stage detect
python -m src.pipeline --stage generate --mock-llm
python -m src.pipeline --stage schedule --mock-llm
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CEREBRAS_API_KEY` | No | Cerebras free-tier key. Checked first. Model: `llama3.1-8b` |
| `GROQ_API_KEY` | No | Groq free-tier key. Used if Cerebras key not set. Model: `llama-3.1-8b-instant` |
| `ANTHROPIC_API_KEY` | No | Anthropic key. Used if Cerebras and Groq keys not set. Model: `claude-sonnet-4-6` |

If no key is set, template fallback messages are generated automatically.

### Run tests locally

```bash
pip install -r requirements.txt
python -m pytest tests/ --cov=src --cov-report=term-missing
# 110 passed, 87% coverage
```

---

## Synthetic Data Design

See [`data/DATA_GENERATION.md`](data/DATA_GENERATION.md) for full details.

**Summary:**
- **50 customers** across 7 geographic regions: UAE, India, UK, Canada, Egypt, USA (New York, LA)
- **500+ events** spanning **14 months** (March 2025 – May 2026)
- **7 distinct timezone regions** for timezone-awareness testing
- **Seasonal order spikes** built into data (reviewer-verifiable):
  - Valentine's Day (Feb 14) — 12 buyers in 2025, 6 repeat buyers in 2026
  - Women's Day (Mar 8) — 5 buyers in 2025, 3 repeat in 2026
  - Eid al-Fitr (Mar 30 2025 / Mar 20 2026) — 10 buyers each year
  - Eid al-Adha (Jun 6 2025 / **May 27 2026** — 8 days from simulation date)
  - Mother's Day (May 2025) — 9 buyers
  - Diwali (October 2025) — 8 buyers
  - Christmas (December 2025) — 8 buyers
- **Cultural diversity**: Muslim (Eid), Hindu (Diwali), Western (Christmas/Valentine's)
- **Cold-start customers** (CUST046–050): 1–2 events each → segment-default fallback
- **`email_opened`** field on order events drives real `email_open_rate` computation
- **Recipient clustering**: multiple customers ordered for same recipient across multiple occasions

---

## Occasion Detection Logic

See `src/occasion_detector.py`.

### Algorithm

Four strategies run in order; results are deduplicated by `(customer_id, occasion, recipient_name)`, keeping highest confidence:

**1. Profile saves → high confidence**
```
profile_update: { field: "birthday", value: "1990-07-15", recipient_name: "Husband" }
→ birthday detected on 2026-07-15, confidence=high
```

**2. Multi-year order patterns → medium confidence**
```
Order 2025-02-14 (valentines_day) + Order 2026-02-14 (valentines_day)
→ 2 years of data → confidence=medium → predict 2027-02-14
```

**3. Single order → low confidence**
```
Order 2025-03-08 (womens_day), no repeat
→ 1 data point → confidence=low → predict 2026-03-08
```

**4. Recipient clustering**
```
Customer ordered for "Mom" on Mother's Day AND Mom's birthday
→ both occasions modelled independently, both linked to recipient "Mom"
```

### Hijri Calendar Conversion

Islamic occasions (Eid al-Fitr = 1 Shawwal, Eid al-Adha = 10 Dhul Hijjah) shift ~11 days earlier each Gregorian year. The engine uses `hijridate==2.3.0`:

```python
from hijridate import Hijri, Gregorian as HijriGregorian

# Convert today to Hijri
today_hijri = HijriGregorian(2026, 5, 19).to_hijri()  # → 1447-11-21

# Find next 10 Dhul Hijjah (Eid al-Adha) in Gregorian
g = Hijri(1447, 12, 10).to_gregorian()  # → 2026-05-27
```

The detector classifies past `"eid"` orders as Eid al-Fitr or Eid al-Adha by proximity to known dates, then projects the next occurrence.

### Confidence Scoring

| Confidence | Evidence |
|-----------|---------|
| `high` | Explicit profile save |
| `medium` | Same occasion ordered in 2+ different years |
| `low` | Single order data point |

**Current run output: 30 high / 15 medium / 47 low — 92 total detections, 20 Hijri**

---

## Prompt Engineering

All prompts live in [`prompts/`](prompts/).

| File | Purpose |
|------|---------|
| `prompts/message_generation.md` | System prompt: brand voice, few-shot examples (birthday, Eid, Valentine's), output schema |
| `prompts/content_safety.md` | Safety rules appended to every user message |

### Prompt Structure

```
SYSTEM: [message_generation.md — brand voice, examples, output schema]
USER:   CUSTOMER CONTEXT: {occasion, days_until, recipient, channel}
        AVAILABLE PRODUCTS: {3 catalogue items for this occasion}
        CONTENT SAFETY RULES: {content_safety.md}
        Respond ONLY with valid JSON.
```

### Brand Voice Rules

- Warm and personal — never transactional
- Never mention discounts, sales, or promotional codes
- Never reveal data machinery: say "we thought of you", not "our system detected"
- Vocabulary: "curated", "handpicked", "thoughtful", "crafted"

### Content Safety Layer (post-generation)

Applied in `_apply_safety_layer()` after every LLM response:

1. **Discount language** — regex scan → message rejected and regenerated
2. **Cultural sensitivity** — alcohol/pork mentions rejected for Eid/Diwali occasions
3. **WhatsApp constraints** — truncated to 1024 chars; opt-out footer auto-appended
4. **Push constraints** — truncated to 150 chars
5. **Product accuracy** — only catalogue items passed in context; LLM cannot hallucinate SKUs

---

## Send-Time Optimisation

Implemented in `src/send_time_optimizer.py`.

### Model

For customers with ≥3 events — mean local hour of past interactions per channel:

| Channel | Signal used |
|---------|------------|
| WhatsApp | Hour of `read=True` WA interactions |
| Email | Hour of order placements (proxy for screen-active time) |
| Push | Hour of browse events |

### Timezone Handling

All timestamps are ISO 8601 with offsets. Times are converted to the customer's local timezone via `pytz` before hour extraction. **0 sends scheduled in quiet hours (11 PM – 6 AM local).**

### Cold-Start Fallback (< 3 events)

Customers with few events use segment-level defaults:

```python
_SEGMENT_DEFAULTS = {
    "uae_female_25_35":    (wa=10, email=20, push=9),
    "uk_mixed_25_35":      (wa=11, email=19, push=10),
    "canada_mixed_25_35":  (wa=10, email=20, push=10),
    ...
}
```

### Urgency Adjustment

| Days until occasion | Adjustment |
|--------------------|-----------|
| < 3 days | −2 hours (send earlier — customer needs time to order) |
| 3–7 days | −1 hour |
| > 7 days | No adjustment |

Example: Eid al-Adha on May 27 (8 days away) → send date May 20 → 7 days until occasion → −1 hour applied → sends at 09:00 instead of 10:00.

---

## Fatigue & Consent

Implemented in `src/campaign_engine.py`.

### Fatigue Management

- **Weekly cap:** ≤ 2 messages per customer per week (all channels combined)
- **Confidence conflict:** high + low confidence in same week → only high is sent
- **Current run: 0 fatigue violations across 92 sends**

### Channel Preference Logic

```python
if wa_read_rate >= 0.6 and email_open_rate == 0.0:
    channel_priority = ["whatsapp", "push", "email"]
else:
    channel_priority = ["whatsapp", "email", "push"]
```

`email_open_rate` is computed dynamically from order events with `email_opened=True`. Customers who have never opened an email and have high WA engagement are routed to WhatsApp.

### Consent Management

- `wa_optin` is set to `False` if any `opted_out=True` WA event exists for the customer
- `email_optin`, `push_optin` from known consent map
- **Current run: 0 consent violations across 92 sends**

### Send Scheduling

| Days until occasion | Send date |
|--------------------|----------|
| < 3 days | Today |
| 3–7 days | Occasion − 3 days |
| > 7 days | Occasion − 7 days |

---

## Output Files

All files written to `outputs/` on every pipeline run:

| File | Contents |
|------|---------|
| `occasion_detection_results.json` | 92 detected occasions with confidence, predicted date, evidence, calendar type |
| `campaign_schedule.json` | 92 scheduled sends: channel, send time, message bundle, consent status, reasoning |
| `evaluation_report.json` | Self-evaluation across 7 dimensions (scores 3–4/5) |
| `test-results.json` | 110 tests, 0 failures, 87% coverage |

---

## Test Strategy

```bash
python -m pytest tests/ --cov=src
# 110 passed, 87% coverage, 0 warnings
```

| Test file | What is tested | LLM mocked? |
|-----------|---------------|------------|
| `test_ingestor.py` | Event loading, profile building, consent, email_open_rate, timezone | No |
| `test_occasion_detector.py` | Hijri conversion, confidence scoring, clustering, calendar helpers | No |
| `test_message_generator.py` | Content safety, WhatsApp/push constraints, opt-out footer, Cerebras/Anthropic routing | Yes |
| `test_send_time_optimizer.py` | Timezone awareness, quiet hours, cold-start, urgency | No |
| `test_campaign_engine.py` | Fatigue cap, consent enforcement, channel preference | No |
| `test_pipeline.py` | End-to-end: ≥30 sends, 0 consent violations, Hijri detections present | Yes |

**All LLM calls are mocked in tests** using `_MockLLMClient` — no live API calls, no cost, deterministic output.

---

## Known Limitations

1. **Send-time model is a mean, not a distribution** — bimodal users (email at 8 AM and 9 PM) will get a wrong midpoint. A Gaussian Mixture Model would be more accurate.

2. **Hijri dates are astronomical approximations** — `hijridate` can be off by 1–2 days vs. official UAE moon-sighting announcements. Production would use official GCAM announcements.

3. **No real-time fatigue state** — fatigue is tracked within a single pipeline run. Production needs Redis/DB persistence across multiple daily runs.

4. **In-memory at 50-customer scale** — at 500K customers, chunked processing with distributed workers (Celery/Ray) is required.

5. **Product accuracy is prompt-level only** — we pass product names to LLM context but don't validate the LLM actually used them in the output.

6. **No A/B testing** — one message per occasion. Production needs variant generation and feedback loops.

---

## Intentional Design Trade-offs

See [`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) for the full list.

**Top 3:**

1. **Cerebras (Llama) over Anthropic as default** — Cerebras offers a free tier with Llama 3.1-8b and an OpenAI-compatible API. This means no SDK changes, no cost for the reviewer to run the pipeline, and near-instant inference. Anthropic Claude is kept as a higher-quality fallback.

2. **Rule-based confidence over ML scoring** — 1 year = low, 2+ years = medium is explainable and requires no training data. An ML model (collaborative filtering or Bayesian update) would be more accurate but adds complexity.

3. **Batch pipeline over event-driven** — A nightly batch job is simpler to review and run via Docker. Production would use Shopify webhooks to trigger occasion detection in real time.
