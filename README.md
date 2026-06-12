# WhatsApp AI Agent for Clinics

24/7 WhatsApp agent that answers patient questions with real clinic data (RAG) and captures appointment leads.

## Problem
## Architecture
## Setup

1. Create a virtualenv and install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in:
   - `ANTHROPIC_API_KEY` (Haiku, for intent classification and replies)
   - `VOYAGE_API_KEY` (Voyage AI, voyage-3.5-lite, for RAG embeddings)
   - `DATABASE_URL` (Supabase Postgres connection string, `vector` extension enabled)
   - `SUPABASE_URL` / `SUPABASE_KEY`
3. Index the clinic knowledge base (creates/repopulates the `documents` table):
   `python -m scripts.ingest_clinic_docs`
4. Run the console agent: `python -m src.cli`

## Evals
## Deploy
