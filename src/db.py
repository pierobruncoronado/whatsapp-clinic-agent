"""Postgres/pgvector connection helper for the RAG pipeline.

Loads DATABASE_URL from .env (Supabase Postgres connection string, see
.env.example). The `vector` extension is already enabled on the database.
"""

import logging
import os
import time

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

load_dotenv()

logger = logging.getLogger(__name__)

MAX_CONNECT_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 1.0


def get_connection():
    """Open a new DB connection with the pgvector type adapter registered.

    Retries once after a short delay on a transient connection failure
    before giving up (see CLAUDE.md: external calls need error handling).
    """
    for attempt in range(1, MAX_CONNECT_ATTEMPTS + 1):
        try:
            conn = psycopg2.connect(os.getenv("DATABASE_URL"))
            register_vector(conn)
            return conn
        except psycopg2.OperationalError:
            if attempt == MAX_CONNECT_ATTEMPTS:
                raise
            logger.warning("get_connection: attempt %d failed, retrying", attempt)
            time.sleep(RETRY_DELAY_SECONDS)
