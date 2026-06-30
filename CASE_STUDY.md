# WhatsApp AI Agent for Dental Clinics
### A production-lite case study — RAG, lead capture, and graceful degradation, deployed 24/7

**Built solo in ~4 days** · Python · FastAPI · Anthropic (Claude Haiku) · Voyage embeddings · pgvector/Supabase · Docker · Railway · Twilio
**Repo:** github.com/pierobruncoronado/whatsapp-clinic-agent

> A WhatsApp agent that answers patient questions from a clinic's real knowledge base, books appointments, and escalates emergencies — running in the cloud with the laptop closed.

| Metric | Result |
|---|---|
| Eval accuracy (14 real scenarios) | **100%** (up from 64% on the first run) |
| Cost per conversation | **$0.00448** (target was < $0.01) |
| Avg production response time | **7.7 s** (with a diagnosed, fixable bottleneck — see below) |
| Hallucination on out-of-scope questions | **Eliminated** via RAG grounding |
| Uptime | 24/7 on Railway, container-based |
| Patient PII in logs | **None** (hashed identifiers) |

---

## The problem

Small dental and aesthetic clinics in Lima lose leads after hours. Patients message on WhatsApp at any time — evenings, weekends — and no one replies until the next business day. Every lead that isn't answered within minutes loses conversion probability. The clinic doesn't need a call center; it needs an always-on first responder that gives accurate information and captures the booking before the patient moves on.

## What I built

A WhatsApp agent that, 24/7:

1. Classifies each incoming message by intent (info / booking / emergency / other).
2. Answers questions about services, prices, hours, and location **from the clinic's actual documents** via retrieval-augmented generation — never from the model's imagination.
3. Captures a booking request (name, phone, time preference) and writes it to the database.
4. Escalates emergencies and anything outside its knowledge to a human, with an explicit handoff — it never guesses.

The agent speaks **Spanish** (the patients); the code, README, and this case study are in **English** (the audience that hires). That bilingual split was a deliberate design decision, not an afterthought.

I scoped v1 hard: one thing done well. Real calendar integration, payments, a multi-clinic admin panel, and migration off the WhatsApp sandbox were all explicitly deferred to v2. Scope discipline was part of the engineering, not separate from it.

## Architecture

```
WhatsApp (Twilio)
      │ signed webhook
      ▼
FastAPI  ──►  structured JSON logging (no PII)
      │
      ▼
Agent (Claude Haiku)
  ├─ intent classification (forced tool-use)
  ├─ RAG  ──►  Voyage embeddings → pgvector (Supabase), top-4 cosine
  ├─ session memory  ──►  Supabase (last 10 turns)
  └─ tool: register_appointment  ──►  Supabase (leads)
      │
      ▼
Reply → WhatsApp
```

Containerized with Docker, deployed to Railway, exposed over HTTPS with Twilio request-signature validation. Everything runs without my machine on.

## Results

**RAG killed the hallucinations — and I can show the before/after.** Early on, asked about a service not in the clinic's documents ("laser whitening"), the agent confidently invented a price of S/350. After grounding every answer in retrieved chunks, the same question now returns "I don't have that information" and hands off to a human. That diff is the whole point of the system.

**Evals went from 64% to 100%, and the gap is the interesting part.** The first run scored 9/14. Diagnosing the five misses taught me more than the final number: four were *false negatives in my own test harness* (over-strict regex), not agent errors — so I fixed the eval, not the agent. Distinguishing a measurement failure from a real failure is a skill in itself. The two real failures were worth catching: one was a retrieval gap, and the other was a **safety issue** — in an emergency scenario the agent was offering first-aid advice. I changed the rules so it escalates only, never coaches at-home treatment for a medical emergency. That class of bug is exactly what you want an eval suite to catch *before* production, not a patient.

**Cost is $0.00448 per conversation**, under half the target, by defaulting to Claude Haiku for both classification and generation and only reserving heavier models for cases the evals proved needed them. Token usage is measured, not estimated.

**Latency is 7.7s average — and I instrumented it honestly.** Per-stage timing showed classification (~0.7s), retrieval (~1.6s), and generation (~1.9s) account for only ~54% of the total. The remaining ~46% is a *fixed ~3.5s overhead present on every single request, independent of message content* — a signature of network round-trips. The cause: compute runs in US West, the database in São Paulo, so every session read/write crosses regions. This is the single highest-leverage optimization, and co-locating compute and database is the first item on the v2 list. I'd rather ship a measured 7.7s with a known fix than a hand-waved number.

**It degrades gracefully under failure.** When the embedding provider hit a free-tier rate limit mid-conversation, retrieval fell back cleanly to an empty-context path instead of crashing — the agent stayed up and kept the conversation alive. External calls have retries with backoff; the system has basic abuse limits (per-number rate limiting, input truncation).

**Patient data is handled with care.** Phone numbers are pseudonymized with a truncated one-way hash before they ever reach a log line; names and message contents are never logged. For a system that touches health-adjacent data, that's table stakes, and I treated it that way.

## Key decisions & trade-offs

- **Twilio WhatsApp Sandbox over Meta's Cloud API.** The Cloud API requires business verification with a multi-day lead time I didn't have. The sandbox proves the full end-to-end flow today; migrating to the Cloud API is a documented v2 step. Shipping beat waiting.
- **Haiku-first.** Start with the cheapest capable model and let the evals — not intuition — justify any upgrade.
- **One-way hashed identifiers over raw or masked phone numbers.** A stronger privacy posture for a tiny implementation cost.
- **Hard v1 scope.** Five things done well, everything tempting written down as out-of-scope.

## What's next (v2)

1. **Co-locate compute and database** to remove the ~3.5s cross-region overhead — the biggest latency win available.
2. Migrate to the WhatsApp Cloud API for production-grade messaging.
3. Real calendar/booking integration.
4. Lift the embedding rate limit for burst traffic.

## Honest scope note

This is a portfolio project, built solo, against a realistic but **synthetic** knowledge base for a fictional Lima dental clinic. The engineering — RAG grounding, the eval suite, the cloud deployment, the observability, the privacy handling — is real and reproducible from the README. No real patient data was used.
