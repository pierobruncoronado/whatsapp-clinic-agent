"""RAG retrieval: embed a patient message and fetch the most relevant
clinic doc chunks from the `documents` table (pgvector cosine distance).
"""

import logging

from src.db import get_connection
from src.embeddings import embed_query

logger = logging.getLogger(__name__)

TOP_K = 4

SEARCH_SQL = """
SELECT content
FROM documents
ORDER BY embedding <=> %s::vector
LIMIT %s
"""


def _to_vector_literal(embedding: list[float]) -> str:
    """Format an embedding as a pgvector text literal, e.g. "[0.1,0.2]"."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def retrieve_context(query: str, top_k: int = TOP_K) -> str:
    """Return the top-k most relevant clinic doc chunks for `query`.

    Chunks are joined with a separator for the system prompt. Returns an
    empty string if embedding or the DB query fails, so the agent falls
    back to deriving instead of crashing (see CLAUDE.md).
    """
    try:
        query_embedding = embed_query(query)
    except Exception:
        logger.exception("retrieve_context: embedding failed")
        return ""

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(SEARCH_SQL, (_to_vector_literal(query_embedding), top_k))
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        logger.exception("retrieve_context: DB query failed")
        return ""

    chunks = [row[0] for row in rows]
    logger.info("retrieve_context: retrieved %d chunks", len(chunks))
    return "\n\n---\n\n".join(chunks)
