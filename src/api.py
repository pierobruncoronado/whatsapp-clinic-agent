"""FastAPI webhook for the Twilio WhatsApp sandbox.

Receives inbound WhatsApp messages, runs intent classification + RAG reply
generation (src/classifier.py, src/agent.py — unchanged), and responds with
TwiML so Twilio delivers the reply back to the patient.

Run with: uvicorn src.api:app --port 8000
"""

import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from src.agent import FALLBACK_REPLY, generate_reply
from src.classifier import classify_intent
from src.clinic_data import CONTACT_PHONE
from src.logging_utils import configure_logging, hash_phone
from src.retrieval import retrieve_context
from src.sessions import get_history, save_history

load_dotenv()

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

# Validates X-Twilio-Signature on every webhook request (docs/spec.md
# section 3: requests must come from Twilio). An empty/missing auth token
# makes every signature check fail closed (403), surfacing misconfiguration
# instead of silently skipping validation.
_validator = RequestValidator(os.getenv("TWILIO_AUTH_TOKEN", ""))

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


def _is_rate_limited(phone: str) -> bool:
    """Track and check the per-number hourly message rate limit."""
    now = time.monotonic()
    recent = [t for t in _rate_limit.get(phone, []) if now - t < RATE_LIMIT_WINDOW_SECONDS]
    recent.append(now)
    _rate_limit[phone] = recent
    return len(recent) > RATE_LIMIT_MAX_MESSAGES


@app.get("/")
def health() -> dict:
    """Health check endpoint for Railway."""
    return {"status": "ok"}


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> Response:
    """Handle an inbound Twilio WhatsApp message and reply via TwiML."""
    start = time.monotonic()
    form = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    url = f"https://{request.headers.get('host', '')}{request.url.path}"

    if not _validator.validate(url, dict(form), signature):
        logger.warning("whatsapp_webhook: invalid Twilio signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    From = form.get("From", "")
    Body = form.get("Body", "")
    phone_id = hash_phone(From)
    message = Body.strip()[:MAX_MESSAGE_LENGTH]

    if _is_rate_limited(From):
        logger.warning(
            "whatsapp_webhook: rate limited",
            extra={
                "event": "message_processed",
                "phone_id": phone_id,
                "status": "rate_limited",
                "total_ms": round((time.monotonic() - start) * 1000, 1),
            },
        )
        twiml = MessagingResponse()
        twiml.message(RATE_LIMIT_REPLY)
        return Response(content=str(twiml), media_type="application/xml")

    status = "ok"
    classify_ms = retrieval_ms = generation_ms = 0.0
    try:
        history = get_history(From)

        t0 = time.monotonic()
        intent = classify_intent(message)
        classify_ms = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        retrieved_context = retrieve_context(message)
        retrieval_ms = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        reply = generate_reply(message, intent, history, retrieved_context)
        generation_ms = (time.monotonic() - t0) * 1000

        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ]
        save_history(From, history[-(MAX_HISTORY_TURNS * 2):])
    except Exception:
        logger.exception("whatsapp_webhook: unexpected error", extra={"phone_id": phone_id})
        intent = "error"
        reply = FALLBACK_REPLY
        status = "error"

    logger.info(
        "whatsapp_webhook: message processed",
        extra={
            "event": "message_processed",
            "phone_id": phone_id,
            "intent": intent,
            "status": status,
            "classify_ms": round(classify_ms, 1),
            "retrieval_ms": round(retrieval_ms, 1),
            "generation_ms": round(generation_ms, 1),
            "total_ms": round((time.monotonic() - start) * 1000, 1),
        },
    )

    twiml = MessagingResponse()
    twiml.message(reply)
    return Response(content=str(twiml), media_type="application/xml")
