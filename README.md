# WhatsApp AI Agent for Clinics

24/7 WhatsApp agent that answers patient questions with real clinic data (RAG) and captures appointment leads.

## Problem

Clinics (dental/aesthetic, Lima) lose leads and appointments outside business hours: patients message on WhatsApp at any time and nobody replies until the next day. Every lead left unanswered for minutes loses conversion probability.

## Architecture

```
Patient (WhatsApp)
  -> Twilio WhatsApp Sandbox webhook (X-Twilio-Signature verified)
  -> FastAPI app (src/api.py)
       -> intent classification (src/classifier.py, Claude Haiku)
       -> reply generation (src/agent.py, Claude Haiku + RAG)
            -> retrieval (src/retrieval.py): Voyage AI embeddings
               + pgvector similarity search over `documents`
            -> appointment lead capture (src/leads.py -> `leads` table)
       -> conversation history (src/sessions.py -> `sessions` table)
  <- TwiML reply
```

- **Model**: Claude Haiku for both intent classification and reply generation.
- **RAG**: clinic docs (`docs/clinic/*.md`) are chunked and embedded with Voyage AI (`voyage-3.5-lite`) and stored in a `pgvector` column on Supabase Postgres.
- **Storage**: Supabase Postgres tables — `documents` (RAG chunks), `leads` (captured appointment requests), `sessions` (conversation history).
- **Channel**: Twilio WhatsApp Sandbox (v1; Meta Cloud API migration is out of scope for v1).

## Prerequisites

- Python 3.11+
- Docker (only needed for the Deploy section below)
- Accounts:
  - [Anthropic](https://console.anthropic.com/) — Claude Haiku API key
  - [Voyage AI](https://dash.voyageai.com/) — embeddings API key
  - [Twilio](https://www.twilio.com/console) — account with the WhatsApp Sandbox enabled
  - [Supabase](https://supabase.com/) — project with the `vector` extension enabled

## Environment variables

Copy `.env.example` to `.env` and fill in real values (never commit `.env`):

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (Claude Haiku) |
| `VOYAGE_API_KEY` | Voyage AI API key (`voyage-3.5-lite` embeddings) |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token — also used to validate the `X-Twilio-Signature` on incoming webhooks |
| `TWILIO_WHATSAPP_NUMBER` | Twilio WhatsApp Sandbox number, e.g. `+14155238886` |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |
| `DATABASE_URL` | Supabase Postgres connection string. Use the **Session Pooler** connection string (port `5432`) — it's IPv4-compatible, required for Docker/Railway. The direct connection (`db.<project>.supabase.co`) is IPv6-only and will fail to connect from most cloud hosts. Keep port `5432` (session mode); port `6543` (transaction mode) breaks the prepared statements `pgvector` relies on. |

## Local setup

1. Create a virtualenv and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in the variables above.
3. Create the `leads` and `sessions` tables (idempotent, safe to re-run):
   ```
   python -m scripts.init_tables
   ```
4. Index the clinic knowledge base into the `documents` table (idempotent — truncates and repopulates):
   ```
   python -m scripts.ingest_clinic_docs
   ```
5. Chat with the agent in the console:
   ```
   python -m src.cli
   ```
6. Run the webhook server locally:
   ```
   uvicorn src.api:app --port 8000
   ```

## Evals

Run the eval suite (14 cases covering the 5 flows from `docs/spec.md` section 6):
```
python -m scripts.run_evals
```
Reports the overall pass rate and the average cost per conversation.

## Deploy

Deploy target: [Railway](https://railway.app/), using the included `Dockerfile`.

1. **(Optional) verify the image builds locally**:
   ```
   docker build -t whatsapp-clinic-agent .
   ```
2. **Create the Railway project**:
   - Log in to [railway.app](https://railway.app) with GitHub.
   - **New Project -> Deploy from GitHub repo** -> select this repository.
   - Railway detects the `Dockerfile` and builds from it — no extra build config needed.
3. **Set environment variables** (service -> **Variables** tab):
   - `ANTHROPIC_API_KEY`
   - `VOYAGE_API_KEY`
   - `TWILIO_AUTH_TOKEN`
   - `DATABASE_URL` (Session Pooler string, port `5432` — see table above)

   Do not set `PORT` manually: Railway injects it, and the `Dockerfile` binds to it (`uvicorn ... --host 0.0.0.0 --port ${PORT:-8000}`).
4. **Generate a public domain**: **Settings -> Networking -> Generate Domain**. This gives a URL like `https://<app>.up.railway.app`.
5. **Verify the deploy**:
   ```
   curl https://<app>.up.railway.app/
   ```
   Should return `{"status": "ok"}`.
6. **Configure the Twilio webhook**:
   - Twilio Console -> Messaging -> Try it out -> **WhatsApp Sandbox Settings**.
   - Set "When a message comes in" to:
     ```
     POST https://<app>.up.railway.app/whatsapp
     ```
   - Save.
7. **End-to-end test**: send a WhatsApp message to the Twilio Sandbox number from your phone and confirm the agent replies.
