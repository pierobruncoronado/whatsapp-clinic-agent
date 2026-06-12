"""Postgres/pgvector connection helper for the RAG pipeline.

Loads DATABASE_URL from .env (Supabase Postgres connection string, see
.env.example). The `vector` extension is already enabled on the database.
"""

import os

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

load_dotenv()


def get_connection():
    """Open a new DB connection with the pgvector type adapter registered."""
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    register_vector(conn)
    return conn
