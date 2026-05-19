# Content Safety Rules — Zuvees Campaign Messages

These rules are applied as a post-generation filter. Any message violating a rule is rejected or regenerated.

## 1. Brand Voice Violations (REJECT if found)

- Any mention of: discount, sale, % off, promo code, clearance, deal, special offer, limited time
- Urgency manipulation: "Act now", "Don't miss out", "Hurry", "Only X left"
- Desperation signals: multiple exclamation marks, ALL CAPS for emphasis
- Creepy data references: "Based on your 7 orders", "Our system shows", "We tracked"

## 2. Cultural Sensitivity — Eid / Ramadan Messaging (REJECT if found)

Eid al-Fitr and Eid al-Adha messages MUST NOT:
- Reference or suggest alcohol, wine, beer, spirits, champagne
- Reference pork, bacon, ham, or non-halal meat products
- Use imagery or language inconsistent with Islamic values
- Make jokes about fasting, prayer, or religious practice

Safe Eid products: flowers, halal chocolate boxes, date hampers, non-alcoholic gift sets, perfumes, oud.

## 3. Cultural Sensitivity — Diwali Messaging

Diwali messages should:
- Reflect warmth, light, family, celebration
- Be appropriate for Hindu cultural context
- Focus on flowers, sweets, hampers, decorative items

## 4. Factual Accuracy (REJECT if found)

- Never name a product that is not in the provided product_suggestions list
- Do not invent product categories or delivery times other than "60 minutes"
- Do not claim specific prices unless provided in context
- Do not reference features Zuvees does not have (e.g., subscription boxes, points systems)

## 5. WhatsApp Compliance (ENFORCE)

- Template body MUST be ≤ 1024 characters
- MUST use exactly {1}, {2}, {3} as variable placeholders (not {{name}} or [name])
- MUST end with opt-out footer: "Reply STOP to opt out."
- No external URLs other than zuvees.ae
- Max 1 emoji per message

## 6. Push Notification Compliance (ENFORCE)

- Text MUST be ≤ 150 characters (including spaces)
- Deep link format: zuvees://shop?occasion=<tag>&utm_source=push
- Must be actionable without being manipulative

## 7. Privacy & Personalization Boundary

The message should feel personal but not surveillance-like:
- ALLOWED: "Your mum's birthday is coming up" (if they saved this themselves)
- ALLOWED: "Eid is almost here — we thought of you"
- NOT ALLOWED: "We noticed you ordered flowers for your mum on 8 March 2025"
- NOT ALLOWED: "Based on your 3 previous Eid purchases..."

The golden rule: would the customer feel cared for, or watched?
