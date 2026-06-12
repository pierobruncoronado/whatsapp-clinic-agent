# Reglas del proyecto (leer siempre)

## Contexto
- Proyecto: agente de WhatsApp IA para clínicas. La spec completa está en `docs/spec.md` — es la fuente de verdad. Ante cualquier ambigüedad, consultarla; si la spec no lo resuelve, PREGUNTARME antes de asumir.
- El agente conversa en español. Código, comentarios y README en inglés.

## Flujo de trabajo (obligatorio en cada sesión)
1. Antes de escribir código: enumerar el plan de la sesión en pasos y esperar mi OK.
2. Después de implementar: CORRER el código y mostrarme el output real. Nada se declara "listo" sin ejecución visible.
3. Al detectar que algo pedido contradice la spec o agranda el alcance v1: avisarme y no implementarlo sin confirmación.
4. Cerrar cada sesión con: (a) verificación contra los criterios de aceptación de la spec que apliquen, (b) commit con mensaje descriptivo, (c) lista de pendientes para la próxima sesión.

## Estándares técnicos
- Secrets SOLO en `.env` (nunca en código ni en commits). Verificar `.gitignore` antes del primer commit.
- Manejo de errores en toda llamada externa (API, DB): try/except con log + fallback, nunca crash silencioso.
- Logs estructurados, sin datos personales de pacientes en claro.
- Funciones cortas, nombres descriptivos, sin abstracciones especulativas ("lo haré genérico por si acaso" = prohibido en v1).
- Modelo por defecto: Haiku. Subir a Sonnet solo si las evals lo justifican.

## Anti-patrones de Piero (interrumpir si aparecen)
- Si pido refactorizar/embellecer algo que ya funciona antes de terminar la fase: recordarme que terminado > perfecto.
- Si pido agregar features fuera del alcance v1: señalar la sección "Fuera de alcance" de la spec.
