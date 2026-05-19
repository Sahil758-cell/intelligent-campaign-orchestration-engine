# Post-Mortem: If I Had 2 More Weeks

## What I built in 8–10 hours

A working campaign orchestration engine: occasion detection (Hijri + Gregorian), LLM message generation with content safety, per-customer send-time optimisation, fatigue/consent management, and a Docker-based pipeline that produces all required outputs. Tests pass at 88% coverage.

---

## What I'd prioritise in 2 more weeks (in order of business impact)

### 1. Real-time feedback loops and A/B testing (Priority: Critical)

**The gap:** The current system generates campaigns but has no way to learn from their performance. Every campaign after Day 1 is as blind as the first one.

**What I'd build:**
- A/B variant generation: 2 messages per occasion (warm vs. benefit-focused tone)
- A webhook receiver (`POST /events/campaign-outcome`) to ingest open/click/conversion events from CleverTap/WATI
- A multi-armed bandit (Thompson Sampling) that shifts traffic toward better-performing variants per occasion type and customer segment
- The send-time model updates its priors with each interaction event

**Expected impact:** 15–25% lift in conversion rate within 4 weeks of live traffic, based on typical A/B test outcomes in gifting e-commerce.

### 2. Attribution and ROI measurement (Priority: High)

**The gap:** There's no connection between campaign sends and revenue. We can't tell the CEO whether this system is worth the compute cost.

**What I'd build:**
- Multi-touch attribution: tag every outbound message with `utm_campaign=occasion_engine&utm_occasion=birthday&utm_customer=CUST001`
- A BigQuery (or Redshift) view that joins Shopify orders with campaign send logs on `customer_id + order_placed_within_72h_of_send`
- A weekly automated report: `occasions_detected, messages_sent, orders_attributed, revenue_attributed, cost_per_attributed_order`
- Incrementality test: hold out 10% of eligible customers, compare conversion rates

**Expected impact:** Attribution clarity that justifies investment and guides the channel-allocation decision (email vs. WA vs. push).

### 3. Hijri calendar accuracy and cultural calendar expansion (Priority: Medium)

**The gap:** The current Hijri conversion is astronomical, not sighting-based. UAE officially announces Eid dates after moon sighting, which can differ by 1–2 days.

**What I'd build:**
- Integration with an Islamic calendar API (UAE GCAM announcements)
- Extend the cultural calendar: Mawlid al-Nabi, Laylat al-Qadr, Ramadan start (affects messaging tone during the month)
- Add Hindu calendar: Navratri, Ganesh Chaturthi, Onam — relevant for the Indian expat segment

**Expected impact:** Eid campaigns sent on the correct day (currently could be 1–2 days off), and expanded coverage for a population that makes up ~30% of the UAE's resident gifting market.

### 4. Scalability: from 50 to 500K customers (Priority: Medium)

**The gap:** The current pipeline loads all events into memory. At 500K customers × 20 events = 10M events, this would OOM.

**What I'd build:**
- Chunked processing: read events in batches of 10K customers at a time
- Stateful occasion detection: store detected occasions in SQLite/Postgres, only re-run detection for customers whose events changed since the last run
- Async message generation: use `asyncio` to batch LLM calls (10 concurrent requests) instead of sequential calls
- Estimated throughput: 10K messages/hour at current Anthropic rate limits

---

## Self-awareness: where this submission falls short

Compared to a production system I'd build at a company:

1. **No real A/B infrastructure** — I'd never ship a marketing engine without it. The system can learn nothing from its own output.

2. **Email open rate is approximated** — I used order placement time as a proxy. Real email open tracking needs ZeptoMail webhook integration, which I deprioritised.

3. **The cold-start fallback is naive** — segment defaults are hand-tuned. A production system would use a collaborative filter ("customers like this one open emails at X").

4. **No rollback mechanism** — If the LLM generates a bad batch of messages (e.g., model update changes tone), there's no way to detect and revert. Production needs a human-in-the-loop review queue for high-value occasions.

---

## What I'm proud of

The Hijri calendar integration works correctly. The content safety layer is principled. The architecture is genuinely modular — each stage can be run and tested independently. The prompt is opinionated about the "personal but not creepy" line, which is the hardest thing to get right in marketing AI.
