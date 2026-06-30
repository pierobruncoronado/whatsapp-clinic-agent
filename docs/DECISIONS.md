# DECISIONS — WhatsApp Clinic Agent

Decisions only (what / why / how / gotchas). Not a line-by-line log.

---

## Channel & Infrastructure

### Channel: Twilio WhatsApp Sandbox (not Meta Cloud API)
- **What:** v1 uses the Twilio WhatsApp Sandbox, not Meta's official Cloud API.
- **Why:** Meta's Cloud API requires business account verification — a process with days to
  weeks of lead time. The Sandbox provides a working end-to-end WhatsApp connection for demo
  and eval purposes without that dependency. Explicitly a v1 scope decision, not a workaround:
  migration to Cloud API is out of scope (`docs/spec.md` section 2, closed decision).
- **How:** Twilio receives the inbound WhatsApp message and forwards it as an HTTP POST to the
  webhook URL with a `X-Twilio-Signature` header. The agent replies via TwiML
  (`twilio.twiml.messaging_response.MessagingResponse`). No change to agent logic for v2 —
  only the Twilio configuration changes.
- **Gotcha:** The Sandbox phone number can only receive messages from numbers that have opted
  in by sending a join code. Real patients cannot message it unprompted — this is a demo
  limitation, not a production-ready channel.

---

## Model & LLM

### Model: `claude-haiku-4-5-20251001` for both classification and generation
- **What:** `src/anthropic_client.py:14` sets `MODEL = "claude-haiku-4-5-20251001"` and this
  constant is shared between the intent classifier (`src/classifier.py`) and the reply
  generator (`src/agent.py`). The spec said to use Haiku and upgrade to Sonnet only if evals
  required it (`docs/spec.md` section 3).
- **Why:** Cost target was <$0.01/conversation. Evals closed at 100 % pass rate with
  $0.00448/conversation — Haiku was sufficient. No upgrade was triggered.
- **How:** Single shared `Anthropic` client in `src/anthropic_client.py`. Both modules call
  `client.messages.create(model=MODEL, ...)`.
- **Gotcha:** None identified at this scale. The cost and quality bar were both met with Haiku.

### Intent classification: forced tool-use with enum schema (not free text)
- **What:** `src/classifier.py` uses `tool_choice={"type": "tool", "name": "classify_intent"}`
  and an enum schema (`["info", "cita", "urgencia", "otro"]`). The model cannot return
  anything outside those four values.
- **Why:** Free-text classification requires parsing — Haiku might respond "parece ser una
  intención de cita" instead of "cita", breaking the downstream routing silently. Forced
  tool-use with an enum guarantees a valid value or a hard API failure; there is no ambiguous
  middle state.
- **How:** classifier loops over `response.content`, finds the `tool_use` block for
  `classify_intent`, reads `block.input["intent"]`, validates against `VALID_INTENTS`. Falls
  back to `"otro"` on API failure (logged, not crashed) so the agent still generates a reply.
- **Gotcha:** The intent is passed to `generate_reply` as a hint injected into the system
  prompt, not used to branch the code. A single generation call handles all intents —
  tone, derivation, and lead capture are governed by the system prompt rules, not by
  Python `if/elif` branching.

---

## RAG Pipeline

### Chunking: per H2 section, each chunk carries the H1 doc title as prefix
- **What:** `src/chunking.py` splits each clinic `.md` file on `\n(?=## )` and builds
  `content = f"{title}\n\n{section}"` where `title` is the H1 heading stripped of `# `
  markers (plain text) and `section` is the full H2 block including heading and body.
- **Why:** Semantic chunking by heading beats fixed-token chunking for this knowledge base —
  the docs are short, well-structured, and each H2 section is an atomic fact unit (prices,
  hours, policies). Fixed-token splitting would cut across price tables mid-row. Prepending
  the H1 title gives the LLM parent context without a metadata join at retrieval time:
  a chunk starting with `## Precios` alone is ambiguous; prefixed with the doc title it
  is not.
- **How:** `chunk_markdown_file` splits the body on H2 boundaries. Each chunk's `content`
  field is `[H1 title text]\n\n## [H2 heading]\n[body]`. The separate `heading` field
  (H2 title alone) is stored for observability only, not used in retrieval.
- **Gotcha:** Intro text before the first H2 is accumulated in `intro` and prepended to the
  first H2 chunk. If a document has no H2 sections at all, `chunk_markdown_file` returns an
  empty list and the document is silently skipped. All current clinic docs have H2 sections —
  this is a latent issue only.

### Retrieval: top_k=4, cosine distance (`<=>`), no similarity threshold
- **What:** `src/retrieval.py` fetches the 4 nearest chunks by cosine distance
  (`ORDER BY embedding <=> %s::vector LIMIT %s`, `TOP_K = 4`). There is no minimum score
  filter — the 4 closest chunks are always returned.
- **Why:** The knowledge base is small (5 short clinic docs). A similarity threshold would
  add tuning complexity with no demonstrated benefit at this scale. Anti-hallucination is
  delegated to the system prompt (rule 2: if the retrieved context doesn't answer the
  question, say so and derive to a human). This was validated in eval cases 11 and 12
  (topic not in KB → correct derivation).
- **How:** Patient message → `embed_query` (Voyage `voyage-3.5-lite`, `input_type="query"`) →
  pgvector cosine distance query → top 4 chunk texts joined with `\n\n---\n\n` → injected
  into the system prompt as `retrieved_context`.
- **Gotcha:** No threshold means a semantically unrelated question still gets 4 chunks
  returned. The prompt rule is the sole guardrail against the model using irrelevant chunks.
  Acceptable for v1; a threshold sweep would be needed if the knowledge base grows. Voyage
  free tier limits to 3 requests/minute — eval runs required 21 s sleeps between turns plus
  a 60 s backoff retry in the eval runner.

### Retrieval fallback cascade: infra failure → `""` → system prompt branch → derive to human
- **What:** `src/retrieval.py` returns `""` on any failure: embedding call exception (line 35)
  or DB query exception (line 48). The caller receives an empty string, not a raised
  exception. `src/prompts.py:build_agent_system_prompt` has an explicit branch: if
  `retrieved_context` is `""`, the system prompt says "No se encontró información relevante"
  and system rule 2 instructs the model to derive to the human contact phone.
- **Why:** A retrieval infra failure (Voyage API down, Supabase outage) should not crash the
  agent or surface a 500 to the patient. The degraded behavior — "I don't have info, please
  call" — is correct and safe. No extra error-handling code is needed in `api.py`; the
  empty-string contract handles the full cascade.
- **How:** `embed_query` fails → log at `ERROR` + `return ""` → `generate_reply` receives
  `retrieved_context=""` → system prompt activates the "no context" branch → model replies
  with derivation and the human contact phone → patient gets a useful response.
- **Gotcha:** The failure is silent at the patient layer (no error message). Observability
  depends on the structured log line emitted by `retrieve_context` — Railway log drain must
  be configured to surface `ERROR` level entries.

---

## Resilience & Security

### Session memory: Supabase `sessions` table, 10-turn sliding window
- **What:** `src/sessions.py` persists conversation history as a JSONB array in the `sessions`
  table (keyed by phone number, upserted on every reply). `src/api.py` trims to
  `history[-(MAX_HISTORY_TURNS * 2):]` (20 message dicts = 10 turns) before saving.
- **Why:** In-memory history dies on server restart. Supabase is already a dependency
  (pgvector for RAG, `leads` for appointment capture), so adding `sessions` adds no new
  infrastructure. The 10-turn window comes from `docs/spec.md` section 5; it was not
  calibrated against token cost — it is a reasonable default for short clinic conversations.
- **How:** `GET_HISTORY_SQL` fetches by phone; `UPSERT_HISTORY_SQL` inserts or replaces.
  `psycopg2.extras.Json` wraps the list for the upsert. Failure to load or save history is
  logged and swallowed — the agent still replies without memory rather than crashing.
- **Gotcha (Supabase connection string, must hold):** `DATABASE_URL` must use the
  **Session Pooler (port 5432, IPv4)**. The direct connection is IPv6-only and fails from
  Railway/Docker; the Transaction pooler (port 6543) breaks the prepared statements that
  pgvector relies on. Without `Json()` wrapper, psycopg2 sends the Python list as a string
  literal, not valid JSONB, causing a silent type error on insert.

### Rate limiting: in-process dict, 20 messages/hour/number (no Redis)
- **What:** `src/api.py` uses `_rate_limit: dict[str, list[float]]` in the process. Each
  phone number's timestamps are stored as a list; entries older than 3600 s are dropped on
  each check. Limit: 20 messages/hour/number. Exceeded → fixed Spanish reply, not a 429.
- **Why:** The spec requires "anti-abuso básico" (`docs/spec.md` section 3). Redis would add
  an external stateful dependency. The in-process dict resets on restart — acceptable for
  this protection level (a determined abuser can bypass it on restart, but v1 basic scope).
  The limit of 20 msg/hour is a default, not a calibrated number.
- **How:** `_is_rate_limited(phone)` filters the list to the last hour, appends the current
  timestamp, returns `True` if the count exceeds `RATE_LIMIT_MAX_MESSAGES`. On rate-limit,
  the webhook returns a user-friendly TwiML message so the patient sees a text in WhatsApp,
  not a silent failure.
- **Gotcha:** Phone numbers are stored in clear text in the in-process dict (never persisted
  or logged). This differs from the structured logs, where `hash_phone` emits
  `sha256(phone)[:12]` for correlation. That truncated hash has no HMAC secret — crackeable
  by brute force for a known phone namespace. For stronger anonymization, replace with
  `HMAC-SHA256(phone, secret)`. Accepted as-is for v1.

### Twilio webhook signature: fail-closed on missing or empty auth token
- **What:** `src/api.py:38` initializes
  `_validator = RequestValidator(os.getenv("TWILIO_AUTH_TOKEN", ""))`. If
  `TWILIO_AUTH_TOKEN` is absent from the environment, the validator receives `""` and every
  `validate()` call returns `False` → HTTP 403 on all requests.
- **Why:** The alternative — a missing token falling back to no validation — would silently
  accept any POST to the webhook, including spoofed messages not from Twilio. Fail-closed on
  misconfiguration surfaces the problem immediately (every request returns 403) rather than
  silently degrading security.
- **How:** `RequestValidator.validate(url, params, signature)` computes HMAC-SHA1 with the
  auth token and compares to the `X-Twilio-Signature` header. With `""` as the token, the
  computed HMAC never matches any real signature → always `False` → always 403.
- **Gotcha:** The URL passed to `validate` is reconstructed from request headers
  (`https://` + `host` header + `request.url.path`). It must match the URL Twilio used to
  send the request **byte for byte** — scheme included. This works identically behind ngrok
  (dev) and Railway (prod) because both terminate TLS and forward `https` as the scheme in
  the `host` header, but any proxy that does not would break signature validation.
