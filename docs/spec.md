# Spec: Agente WhatsApp IA para clínicas (SDD)
*Versión 0.2 (calibrada) — se refina solo cuando el build lo exija.*

## 1. Problema
Las clínicas (dentales/estéticas, Lima) pierden leads y citas fuera de horario: los pacientes escriben por WhatsApp a cualquier hora y nadie responde hasta el día siguiente. Cada lead no respondido en minutos pierde probabilidad de conversión.

## 2. Solución (alcance v1 — UNA cosa bien hecha)
Agente de WhatsApp que, 24/7:
1. Recibe el mensaje del paciente.
2. Clasifica la intención (info / cita / urgencia / otro).
3. Responde con información REAL de la clínica vía RAG (servicios, precios, horarios, ubicación).
4. Si pide cita: captura nombre + teléfono + preferencia horaria y la registra (tabla `leads` en Supabase). v1 NO integra calendario externo.
5. Si es urgencia o no sabe: deriva a humano con mensaje claro (fallback explícito, nunca inventa).

### Idioma (decisión cerrada)
- El agente conversa en español (pacientes de Lima).
- README, case study y Loom en inglés (audiencia: empleadores).

### Canal (decisión cerrada)
- v1 usa Twilio WhatsApp Sandbox. Razón: la Cloud API de Meta exige verificación de negocio (días/semanas de lead time). Sandbox basta para demo end-to-end y Loom. Migración a Cloud API = v2.

### Fuera de alcance v1 (anti scope-creep)
Calendario/agenda real, pagos, multi-clínica, panel admin, voz/imágenes, recordatorios automáticos, migración a Cloud API. Todo v2+. No se toca antes del case study.

## 3. Requisitos no funcionales
- Tiempo de respuesta: < 8 s (medido y reportado).
- Disponibilidad: deploy en cloud, corre con mi laptop apagada.
- Precisión: >= 85% en suite de evals (12-15 casos reales).
- Cero alucinación de datos de la clínica: si el RAG no lo respalda, deriva.
- Costo: objetivo < $0.01/conversación. Clasificación con Haiku; generación con Haiku, subir a Sonnet solo si las evals lo exigen. Medir tokens y reportar.
- Privacidad: datos de pacientes solo en Supabase, secrets en env vars, logs sin PII en claro.
- Anti-abuso básico: límite de mensajes por número/hora; truncar inputs absurdamente largos.

## 4. Arquitectura
WhatsApp (Twilio Sandbox)
| webhook  (dev local: ngrok -> URL publica)
v
API (Python + FastAPI)  --> logging estructurado
|
v
Agente (Anthropic SDK)

clasificacion de intencion (Haiku)
RAG --> pgvector (Supabase)   [docs de la clinica]
memoria de conversacion --> Supabase (sessions, ventana ultimos 10 turnos)
herramienta: registrar_cita --> Supabase (leads)
|
v
Respuesta -> WhatsApp

- Contenedor: Docker. Hosting: Railway/Render free tier.
- Repo: GitHub público, commits desde el día 1. Dev local: ngrok para exponer el webhook.

## 5. Modelo de datos (mínimo)
- `documents` (id, contenido, embedding) — base RAG.
- `sessions` (telefono, historial, updated_at) — memoria acotada a 10 turnos.
- `leads` (id, nombre, telefono, servicio, preferencia_horaria, created_at, estado).

## 6. Flujos de ejemplo (guían el system prompt y las evals)
1. "¿Cuánto cuesta una limpieza dental?" -> RAG -> precio real + invitación a agendar.
2. "Quiero una cita el sábado en la tarde" -> captura datos -> confirma registro -> lead en Supabase.
3. "Me sangra mucho la encía desde ayer" -> urgencia -> deriva a humano con teléfono directo.
4. "¿Hacen blanqueamiento con láser?" (no está en docs) -> no inventa -> deriva.
5. Mensaje fuera de tema ("¿me prestas plata?") -> redirige amable al propósito del canal.

## 7. Criterios de aceptación (qué significa "terminado")
- [ ] Mensaje real de WhatsApp entra y recibe respuesta correcta end-to-end.
- [ ] Responde precios/horarios desde RAG, no desde el prompt.
- [ ] Captura un lead de cita completo en Supabase.
- [ ] Deriva correctamente cuando no sabe (caso 4 arriba).
- [ ] Suite de evals corrida con % documentado (>= 85%).
- [ ] Costo por conversación medido y < $0.01.
- [ ] Desplegado en cloud, responde con la laptop apagada.
- [ ] README en inglés permite a un tercero levantarlo sin ayuda.

## 8. Métricas para el case study
Tiempo de respuesta promedio · % evals · cobertura de intenciones · costo por conversación · uptime del deploy.
