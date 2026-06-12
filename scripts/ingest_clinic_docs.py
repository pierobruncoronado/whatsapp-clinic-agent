"""Ingest docs/clinic/*.md into the `documents` table for RAG retrieval.

Chunks each doc by H2 section, embeds the chunks with Voyage AI, and
replaces the contents of the `documents` table. Safe to re-run (idempotent):
each run truncates and repopulates the table.

Run with: python -m scripts.ingest_clinic_docs
"""

import logging

from src.chunking import chunk_clinic_docs
from src.db import get_connection
from src.embeddings import EMBEDDING_DIMENSIONS, embed_documents

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    heading TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR({EMBEDDING_DIMENSIONS}) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

INSERT_SQL = """
INSERT INTO documents (source_file, heading, content, embedding)
VALUES (%s, %s, %s, %s)
"""


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    chunks = chunk_clinic_docs()
    logger.info("Chunked %d sections from docs/clinic/", len(chunks))

    embeddings = embed_documents([chunk["content"] for chunk in chunks])

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            cur.execute("TRUNCATE TABLE documents RESTART IDENTITY")
            for chunk, embedding in zip(chunks, embeddings):
                cur.execute(
                    INSERT_SQL,
                    (chunk["source_file"], chunk["heading"], chunk["content"], embedding),
                )
        conn.commit()
        logger.info("Inserted %d chunks into documents table", len(chunks))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
