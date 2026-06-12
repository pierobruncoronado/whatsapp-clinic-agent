"""Voyage AI embeddings client for the RAG pipeline.

Loads VOYAGE_API_KEY from .env (see .env.example). Uses voyage-3.5-lite,
Anthropic's recommended embeddings partner (see docs/spec.md section 4).
"""

import os

import voyageai
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = "voyage-3.5-lite"
EMBEDDING_DIMENSIONS = 1024

_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of clinic doc chunks for indexing (ingestion)."""
    result = _client.embed(texts, model=EMBEDDING_MODEL, input_type="document")
    return result.embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single patient message for retrieval."""
    result = _client.embed([text], model=EMBEDDING_MODEL, input_type="query")
    return result.embeddings[0]
