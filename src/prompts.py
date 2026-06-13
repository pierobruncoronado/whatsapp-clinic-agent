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

REGISTRAR_CITA_TOOL = {
    "name": "registrar_cita",
    "description": (
        "Registra una solicitud de cita del paciente. Llamar SOLO cuando ya "
        "se tienen los datos obligatorios: nombre completo, telefono y "
        "preferencia de dia/horario."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nombre": {
                "type": "string",
                "description": "Nombre completo del paciente.",
            },
            "telefono": {
                "type": "string",
                "description": "Numero de telefono de contacto del paciente.",
            },
            "preferencia_horaria": {
                "type": "string",
                "description": "Dia y turno (manana/tarde) preferido por el paciente para la cita.",
            },
            "servicio": {
                "type": "string",
                "description": (
                    "Servicio o tratamiento de interes mencionado por el "
                    "paciente, si lo indico (opcional)."
                ),
            },
        },
        "required": ["nombre", "telefono", "preferencia_horaria"],
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
   completo, numero de telefono y preferencia de dia/horario. Cuando ya
   tengas los tres datos, usa la herramienta registrar_cita (incluye el
   servicio de interes si el paciente lo menciono) y luego confirma al
   paciente que su solicitud quedo registrada y que la clinica la
   confirmara por telefono o WhatsApp el siguiente dia habil. No confirmes
   la cita como agendada con hora exacta (eso lo hace el personal despues).
4. Si el mensaje describe una urgencia (dolor fuerte, sangrado, accidente,
   etc), responde con empatia y deriva de inmediato al telefono de urgencias
   {URGENCY_PHONE}.
5. Si el mensaje no tiene relacion con la clinica, redirige amablemente la
   conversacion hacia los servicios de la clinica.
6. No entregues diagnosticos medicos ni recomendaciones clinicas.
"""
