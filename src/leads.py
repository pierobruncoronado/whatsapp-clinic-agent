"""Lead capture: insert appointment requests into the `leads` table."""

import logging

from src.db import get_connection

logger = logging.getLogger(__name__)

DEFAULT_ESTADO = "nuevo"

INSERT_LEAD_SQL = """
INSERT INTO leads (nombre, telefono, servicio, preferencia_horaria, estado)
VALUES (%s, %s, %s, %s, %s)
"""


def insert_lead(nombre: str, telefono: str, servicio: str | None, preferencia_horaria: str) -> bool:
    """Insert a new appointment lead into Supabase.

    Returns True on success, False if the insert failed (logged, no crash;
    see CLAUDE.md error handling rules).
    """
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(INSERT_LEAD_SQL, (nombre, telefono, servicio, preferencia_horaria, DEFAULT_ESTADO))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("insert_lead: failed to insert lead")
        return False

    logger.info("insert_lead: lead registered")
    return True
