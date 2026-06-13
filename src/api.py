"""FastAPI webhook for the Twilio WhatsApp sandbox.

Receives inbound WhatsApp messages, runs intent classification + RAG reply
generation (src/classifier.py, src/agent.py — unchanged), and responds with
TwiML so Twilio delivers the reply back to the patient.

Run with: uvicorn src.api:app --port 8000
"""

import logging
import time

from fastapi import FastAPI, Form
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

from src.agent import FALLBACK_REPLY, generate_reply
from src.classifier import classify_intent
from src.clinic_data import CONTACT_PHONE
from src.sessions import get_history, save_history

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

MAX_HISTORY_TURNS = 10

# Anti-abuse limits (docs/spec.md section 3).
MAX_MESSAGE_LENGTH = 1000
RATE_LIMIT_MAX_MESSAGES = 20
RATE_LIMIT_WINDOW_SECONDS = 3600

RATE_LIMIT_REPLY = (
    "Has enviado muchos mensajes en poco tiempo. Por favor espera unos "
    f"minutos o llama directamente al {CONTACT_PHONE}."
)

# In-memory rate-limit counters per phone number (resets on restart, which
# is acceptable for this basic anti-abuse check).
_rate_limit: dict[str, list[float]] = {}


def _mask_phone(phone: str) -> str:
    """Mask a phone number for logs (keep only the last 4 digits)."""
    return f"***{phone[-4:]}" if len(phone) >= 4 else "***"


def _is_rate_limited(phone: str) -> bool:
    """Track and check the per-number hourly message rate limit."""
    now = time.monotonic()
    recent = [t for t in _rate_limit.get(phone, []) if now - t < RATE_LIMIT_WINDOW_SECONDS]
    recent.append(now)
    _rate_limit[phone] = recent
    return len(recent) > RATE_LIMIT_MAX_MESSAGES


@app.post("/whatsapp")
def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)) -> Response:
    """Handle an inbound Twilio WhatsApp message and reply via TwiML."""
    start = time.monotonic()
    masked_phone = _mask_phone(From)
    message = Body.strip()[:MAX_MESSAGE_LENGTH]

    if _is_rate_limited(From):
        logger.warning("whatsapp_webhook: phone=%s rate limited", masked_phone)
        twiml = MessagingResponse()
        twiml.message(RATE_LIMIT_REPLY)
        return Response(content=str(twiml), media_type="application/xml")

    try:
        history = get_history(From)
        intent = classify_intent(message)
        reply = generate_reply(message, intent, history)

        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ]
        save_history(From, history[-(MAX_HISTORY_TURNS * 2):])
    except Exception:
        logger.exception("whatsapp_webhook: unexpected error from %s", masked_phone)
        intent = "error"
        reply = FALLBACK_REPLY

    elapsed = time.monotonic() - start
    logger.info(
        "whatsapp_webhook: phone=%s intent=%s elapsed=%.2fs",
        masked_phone,
        intent,
        elapsed,
    )

    twiml = MessagingResponse()
    twiml.message(reply)
    return Response(content=str(twiml), media_type="application/xml")
