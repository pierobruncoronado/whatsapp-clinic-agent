"""Create the `leads` and `sessions` tables in Supabase (docs/spec.md section 5).

Idempotent: uses CREATE TABLE IF NOT EXISTS, safe to re-run.

Run with: python -m scripts.init_tables
"""

import logging

from src.db import get_connection

logger = logging.getLogger(__name__)

CREATE_LEADS_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL,
    servicio TEXT,
    preferencia_horaria TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    estado TEXT NOT NULL DEFAULT 'nuevo'
);
"""

CREATE_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    telefono TEXT PRIMARY KEY,
    historial JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_LEADS_SQL)
            cur.execute(CREATE_SESSIONS_SQL)
        conn.commit()
        logger.info("leads and sessions tables ready")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
