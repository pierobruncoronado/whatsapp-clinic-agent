"""Reply generation for the WhatsApp clinic agent."""

import logging

from src.anthropic_client import MODEL, client
from src.clinic_data import CONTACT_PHONE
from src.prompts import AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "Disculpa, tuve un problema para procesar tu mensaje. "
    f"Por favor escribe directamente al {CONTACT_PHONE} y te ayudara nuestro equipo."
)


def generate_reply(message: str, intent: str, history: list[dict]) -> str:
    """Generate the agent's reply to a patient message.

    `history` is a list of {"role": "user"|"assistant", "content": str}
    dicts for the current conversation (last ~10 turns, per docs/spec.md).
    Falls back to a fixed derivation message if the API call fails.
    """
    system_prompt = (
        f"{AGENT_SYSTEM_PROMPT}\n\nIntencion detectada para el ultimo mensaje "
        f"del paciente: {intent}."
    )
    messages = history + [{"role": "user", "content": message}]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=system_prompt,
            messages=messages,
        )
    except Exception:
        logger.exception("generate_reply: API call failed, using fallback")
        return FALLBACK_REPLY

    text_blocks = [block.text for block in response.content if block.type == "text"]
    reply = "".join(text_blocks).strip()

    logger.info(
        "generate_reply: intent=%s input_tokens=%s output_tokens=%s",
        intent,
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    return reply or FALLBACK_REPLY
