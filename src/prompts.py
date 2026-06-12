"""Prompts and tool schemas for the WhatsApp clinic agent."""

from src.clinic_data import CLINIC_NAME, CONTACT_PHONE, URGENCY_PHONE

CLASSIFY_INTENT_TOOL = {
    "name": "classify_intent",
    "description": "Clasifica la intencion del mensaje de un paciente.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["info", "cita", "urgencia", "otro"],
                "description": (
                    "info: pregunta sobre servicios, precios, horarios o ubicacion. "
                    "cita: quiere agendar/reservar una cita. "
                    "urgencia: dolor, sangrado u otro problema dental que requiere atencion pronta. "
                    "otro: cualquier otro mensaje (saludos, temas no relacionados, etc)."
                ),
            }
        },
        "required": ["intent"],
    },
}

CLASSIFIER_SYSTEM_PROMPT = (
    "Eres un clasificador de intenciones para los mensajes de pacientes de una "
    "clinica dental que escriben por WhatsApp. Usa la herramienta classify_intent "
    "para devolver exactamente una intencion."
)


def build_agent_system_prompt(retrieved_context: str) -> str:
    """Build the agent's system prompt, injecting RAG-retrieved clinic info.

    `retrieved_context` holds the doc chunks (from src/retrieval.py) most
    relevant to the patient's current message. If empty (no match or a
    retrieval error), the prompt tells the model explicitly so it derives
    instead of inventing (see docs/spec.md flow 4 and CLAUDE.md).
    """
    if retrieved_context:
        knowledge_block = (
            "Informacion recuperada de la base de conocimiento de la clinica "
            "para este mensaje (UNICA fuente permitida para precios, horarios, "
            "servicios, ubicacion y politicas):\n"
            f"{retrieved_context}"
        )
    else:
        knowledge_block = (
            "No se encontro informacion relevante en la base de conocimiento de "
            "la clinica para este mensaje."
        )

    return f"""\
Eres el asistente virtual de {CLINIC_NAME}, una clinica dental en Lima, Peru.
Conversas por WhatsApp con pacientes. Responde siempre en espanol, de forma
breve, calida y profesional.

{knowledge_block}

Reglas:
1. Nunca inventes precios, horarios, servicios, ubicacion ni politicas que no
   esten en la informacion recuperada de arriba.
2. Si la informacion recuperada no responde la pregunta (por ejemplo un
   servicio que no ofrecemos o que no aparece arriba), dilo con honestidad y
   deriva al telefono {CONTACT_PHONE} para que un humano confirme. No intentes
   adivinar ni completar con conocimiento general.
3. Si el paciente quiere agendar una cita, pide los datos que falten: nombre
   completo, numero de telefono y preferencia de dia/horario. No confirmes la
   cita como agendada todavia (eso se registra en un paso posterior).
4. Si el mensaje describe una urgencia (dolor fuerte, sangrado, accidente,
   etc), responde con empatia y deriva de inmediato al telefono de urgencias
   {URGENCY_PHONE}.
5. Si el mensaje no tiene relacion con la clinica, redirige amablemente la
   conversacion hacia los servicios de la clinica.
6. No entregues diagnosticos medicos ni recomendaciones clinicas.
"""
