"""Conversation memory persistence in the `sessions` table (Supabase).

Replaces an in-memory history dict so conversation context survives a
server restart (docs/spec.md section 5: window of the last 10 turns).
"""

import logging

from psycopg2.extras import Json

from src.db import get_connection

logger = logging.getLogger(__name__)

GET_HISTORY_SQL = "SELECT historial FROM sessions WHERE telefono = %s"

UPSERT_HISTORY_SQL = """
INSERT INTO sessions (telefono, historial, updated_at)
VALUES (%s, %s, now())
ON CONFLICT (telefono) DO UPDATE SET historial = EXCLUDED.historial, updated_at = now()
"""


def get_history(telefono: str) -> list[dict]:
    """Return the stored conversation history for `telefono`.

    Returns [] if there is no stored session or the lookup fails (logged,
    so the agent still replies without memory rather than crashing).
    """
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(GET_HISTORY_SQL, (telefono,))
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception:
        logger.exception("get_history: failed to load session")
        return []

    return row[0] if row else []


def save_history(telefono: str, history: list[dict]) -> None:
    """Persist `history` for `telefono`. Logs and no-ops on failure."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(UPSERT_HISTORY_SQL, (telefono, Json(history)))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("save_history: failed to persist session")
