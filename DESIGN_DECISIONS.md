# Design Decisions

Numbered decisions made during implementation, each with trade-offs.

---

## 1. Rule-based confidence scoring vs. ML-based

**Decision:** Use rule-based thresholds: 1 year of data → low, 2+ years → medium, explicit profile save → high.

**Rationale:** With 50 synthetic customers and 14 months of history, there isn't enough data to train a meaningful ML model. Rule-based scoring is explainable, debuggable, and produces sensible outputs immediately.

**Trade-off:** A Bayesian confidence model (updating priors each time a customer confirms an occasion) would be more accurate as data accumulates. The hard threshold at 2 years means a customer who ordered in Year 1 and Year 3 (skipped Year 2) gets the same confidence as one who ordered every year.

**What I'd do differently:** Implement a decay function — confidence increases logarithmically with number of years of evidence, and decays if there's a gap year (the customer may have stopped caring about that occasion).

---

## 2. Template-based LLM fallback vs. always-requiring API key

**Decision:** The pipeline runs in two modes: with `ANTHROPIC_API_KEY` set (real LLM messages) or without (template-based fallback). All tests use the fallback.

**Rationale:** This enables zero-cost CI, demo runs, and reviewer testing without a paid API key. It also means the pipeline doesn't fail on startup if the key is missing.

**Trade-off:** Fallback messages are generic and not truly personalised. The reviewer evaluating message quality will get richer output when an API key is provided.

**What I'd do differently:** Pre-generate and cache LLM responses for all 54 detected occasions, commit the cache to the repo, and serve from cache in CI. This gives reviewers real LLM output without needing a key.

---

## 3. Batch pipeline vs. event-driven triggers

**Decision:** The entire pipeline is a batch job — load all events, detect all occasions, generate all messages, schedule all sends in one run.

**Rationale:** An event-driven architecture (Shopify webhook → occasion detection → immediate campaign trigger) is the production-correct approach but requires infrastructure (queues, workers, state management) that would take much longer than 8–10 hours to build correctly.

**Trade-off:** Batch processing means there's latency between a customer saving a birthday and the system generating a campaign. In production, a profile update should trigger immediate re-scoring.

**What I'd do differently:** Add a separate `watch` mode: `python -m src.pipeline --stage detect --watch` that polls for new events every 15 minutes and re-runs detection for modified customers only.

---

## 4. Hour-averaging for send-time vs. Gaussian Mixture Model

**Decision:** Compute the arithmetic mean of past interaction hours for each channel and use that as the send time.

**Rationale:** Simple, interpretable, and fast. With sparse data (most customers have <20 interaction events per channel), a GMM would overfit.

**Trade-off:** Fails for bimodal users (checks email at 8 AM and 9 PM — mean of 14:30 is the worst time for both). Also doesn't model day-of-week patterns (many users are more responsive on weekends).

**What I'd do differently:** Cluster interaction hours using K-means (K=2) per channel. If two clusters are found with similar counts, pick the one that's in "business hours" first.

---

## 5. In-memory fatigue tracking vs. Redis-backed state

**Decision:** Fatigue counts are tracked in a Python dict within a single pipeline run.

**Rationale:** No infrastructure dependency, no persistence needed for a batch pipeline. The dict is rebuilt from scratch each run.

**Trade-off:** If the pipeline runs twice in the same week (e.g., morning and evening), it won't know about sends from the earlier run and could double-send.

**What I'd do differently:** Persist send history to a lightweight SQLite database (or Redis in production). The campaign engine would query `SELECT COUNT(*) WHERE customer_id = ? AND sent_at >= week_start` before scheduling.

---

## 6. Hijri date library choice: hijri-converter vs. manual lookup table

**Decision:** Used `hijri-converter` (now deprecated; successor is `hijridate`) for Hijri-to-Gregorian conversion.

**Rationale:** The library handles the complex astronomical calculations correctly. A manual lookup table would need to be updated every year.

**Trade-off:** The library uses calculated Hijri dates, which can differ from official moon-sighting announcements by 1–2 days. In the UAE, Eid dates are officially announced by the Supreme Court based on moon sighting.

**What I'd do differently:** In production, integrate with an Islamic calendar API (e.g., ISNA or UAE GCAM announcements) and use the library date only as a fallback when official announcement hasn't been made yet.

---

## 7. Single message per occasion vs. A/B variants

**Decision:** Generate one message bundle per detected occasion.

**Rationale:** Generating 2–3 variants per occasion would double/triple API costs and add complexity around variant selection, tracking, and analysis.

**Trade-off:** Without variants, we can't run A/B tests to learn which message style converts better. Over time, the system becomes unable to improve its own messaging.

**What I'd do differently:** Generate variant A (warm/personal) and variant B (benefit-focused) for each occasion. Route 20% of sends to variant B. Track open/click rates per variant and use a multi-armed bandit to shift budget toward the better performer.
