"""Reply generation for the WhatsApp clinic agent."""

import logging

from src.anthropic_client import MODEL, client
from src.clinic_data import CONTACT_PHONE
from src.leads import insert_lead
from src.prompts import REGISTRAR_CITA_TOOL, build_agent_system_prompt

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "Disculpa, tuve un problema para procesar tu mensaje. "
    f"Por favor escribe directamente al {CONTACT_PHONE} y te ayudara nuestro equipo."
)

# Safety cap on tool-use round trips per reply (registrar_cita is normally
# called at most once, so 3 leaves headroom without allowing a runaway loop).
MAX_TOOL_ITERATIONS = 3


def _run_registrar_cita(tool_input: dict) -> str:
    """Execute the registrar_cita tool call and return the tool_result text."""
    success = insert_lead(
        nombre=tool_input.get("nombre", ""),
        telefono=tool_input.get("telefono", ""),
        servicio=tool_input.get("servicio"),
        preferencia_horaria=tool_input.get("preferencia_horaria", ""),
    )
    if success:
        return "Lead registrado correctamente en el sistema de la clinica."
    return "No se pudo registrar el lead. Informa al paciente que llame directamente a la clinica."


def generate_reply(message: str, intent: str, history: list[dict], retrieved_context: str) -> str:
    """Generate the agent's reply to a patient message.

    `history` is a list of {"role": "user"|"assistant", "content": str}
    dicts for the current conversation (last ~10 turns, per docs/spec.md).
    `retrieved_context` is the RAG context for `message` (src/retrieval.py),
    fetched by the caller so its latency can be measured separately.
    If the patient has provided all required appointment data, the model
    may call the registrar_cita tool, which inserts a row into the `leads`
    table (src/leads.py) before the final reply is generated.
    Falls back to a fixed derivation message if any API call fails.
    """
    system_prompt = (
        f"{build_agent_system_prompt(retrieved_context)}\n\nIntencion detectada "
        f"para el ultimo mensaje del paciente: {intent}."
    )
    messages = history + [{"role": "user", "content": message}]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=system_prompt,
            tools=[REGISTRAR_CITA_TOOL],
            messages=messages,
        )

        for _ in range(MAX_TOOL_ITERATIONS):
            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result_text = _run_registrar_cita(block.input)
                logger.info("generate_reply: tool=%s called", block.name)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
                )

            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]
            response = client.messages.create(
                model=MODEL,
                max_tokens=400,
                system=system_prompt,
                tools=[REGISTRAR_CITA_TOOL],
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
