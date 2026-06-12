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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

MAX_HISTORY_TURNS = 10

# In-memory conversation history per phone number (lost on restart).
# Replacing this with the `sessions` table in Supabase (docs/spec.md
# section 5) is a future step, not part of today's channel integration.
_history: dict[str, list[dict]] = {}


def _mask_phone(phone: str) -> str:
    """Mask a phone number for logs (keep only the last 4 digits)."""
    return f"***{phone[-4:]}" if len(phone) >= 4 else "***"


@app.post("/whatsapp")
def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)) -> Response:
    """Handle an inbound Twilio WhatsApp message and reply via TwiML."""
    start = time.monotonic()
    masked_phone = _mask_phone(From)
    message = Body.strip()

    try:
        history = _history.get(From, [])
        intent = classify_intent(message)
        reply = generate_reply(message, intent, history)

        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ]
        _history[From] = history[-(MAX_HISTORY_TURNS * 2):]
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
