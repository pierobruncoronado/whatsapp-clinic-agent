"""Intent classification for incoming patient messages."""

import logging

from src.anthropic_client import MODEL, client
from src.prompts import CLASSIFIER_SYSTEM_PROMPT, CLASSIFY_INTENT_TOOL

logger = logging.getLogger(__name__)

VALID_INTENTS = {"info", "cita", "urgencia", "otro"}
FALLBACK_INTENT = "otro"


def classify_intent(message: str) -> str:
    """Classify a patient message into info/cita/urgencia/otro.

    Falls back to "otro" if the API call fails, so the agent can still
    respond (with a generic/derivation reply) instead of crashing.
    """
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=50,
            system=CLASSIFIER_SYSTEM_PROMPT,
            tools=[CLASSIFY_INTENT_TOOL],
            tool_choice={"type": "tool", "name": "classify_intent"},
            messages=[{"role": "user", "content": message}],
        )
    except Exception:
        logger.exception("classify_intent: API call failed, using fallback")
        return FALLBACK_INTENT

    for block in response.content:
        if block.type == "tool_use" and block.name == "classify_intent":
            intent = block.input.get("intent")
            if intent in VALID_INTENTS:
                logger.info(
                    "classify_intent: intent=%s input_tokens=%s output_tokens=%s",
                    intent,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )
                return intent

    logger.warning("classify_intent: no valid tool_use block found, using fallback")
    return FALLBACK_INTENT
