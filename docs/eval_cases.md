# Suite de evals — diseño de casos (día 5, implementación día 6)

14 casos basados en los 5 flujos de `docs/spec.md` sección 6. Meta: >= 85%
(>= 12/14 casos correctos), per spec sección 3/7.

Para cada caso: input del paciente (uno o varios turnos), intención esperada
(`info` / `cita` / `urgencia` / `otro`), qué debe contener la respuesta y qué
debe evitar. Las referencias a precios/horarios vienen de `docs/clinic/*.md`
(fuente real para el RAG).

## Flujo 1 — Info real vía RAG

### Caso 1 — Precio de limpieza dental
- **Input**: "¿Cuánto cuesta una limpieza dental?"
- **Intención esperada**: `info`
- **Debe contener**: precio S/ 120 (profilaxis + destartraje simple); invitación a agendar cita.
- **Debe evitar**: inventar otro precio; confirmar una cita ya agendada.

### Caso 2 — Horario de sábado
- **Input**: "¿A qué hora abren los sábados?"
- **Intención esperada**: `info`
- **Debe contener**: sábados 9:00 a.m. – 2:00 p.m.; última cita 1:00 p.m.
- **Debe evitar**: confundir con horario de semana (9am-8pm); inventar atención los domingos.

### Caso 3 — Ubicación y estacionamiento
- **Input**: "¿Dónde están ubicados y tienen estacionamiento?"
- **Intención esperada**: `info`
- **Debe contener**: dirección Av. San Borja Norte 1245, San Borja; mención de 4 cocheras gratuitas sujetas a disponibilidad y playa pagada a media cuadra.
- **Debe evitar**: inventar otra dirección; garantizar estacionamiento sin la condición "sujeta a disponibilidad".

### Caso 4 — Medio de pago + precio de endodoncia
- **Input**: "¿Aceptan Yape? Quiero hacerme una endodoncia"
- **Intención esperada**: `info`
- **Debe contener**: confirmación de que aceptan Yape/Plin/tarjetas; precio de endodoncia según pieza (S/ 480–650) o invitación a evaluación para definir cuál aplica.
- **Debe evitar**: dar un precio único de endodoncia sin aclarar que depende de la pieza/complejidad.

## Flujo 2 — Captura de cita (registrar_cita)

### Caso 5 — Datos completos en un solo mensaje
- **Input**: "Quiero una cita para limpieza dental el martes en la tarde. Soy Carlos Mendoza, mi número es 987654321"
- **Intención esperada**: `cita`
- **Debe contener**: confirmación de que la solicitud quedó registrada y que la clínica confirmará por WhatsApp/teléfono el siguiente día hábil; debe haber llamado `registrar_cita` con nombre, teléfono, preferencia_horaria y servicio="limpieza dental".
- **Debe evitar**: afirmar que la cita ya tiene hora exacta confirmada; volver a pedir datos ya provistos.

### Caso 6 — Datos parciales en dos turnos (memoria de sesión)
- **Turno 1**: "Quiero agendar una cita"
- **Turno 2**: "Me llamo Ana Torres, 912345678, el viernes en la mañana"
- **Intención esperada**: `cita` en ambos turnos
- **Debe contener (turno 1)**: pedido de los 3 datos obligatorios (nombre completo, teléfono, preferencia de día/turno), sin registrar nada todavía.
- **Debe contener (turno 2)**: uso del contexto del turno 1 (no vuelve a preguntar "¿en qué te ayudo?"); llamada a `registrar_cita` con los datos del turno 2; confirmación de registro.
- **Debe evitar**: perder el hilo de que se trata de una solicitud de cita; pedir de nuevo datos ya dados.

### Caso 7 — Preferencia fuera de horario (domingo)
- **Input**: "Quiero una cita el domingo a las 10am para una consulta"
- **Intención esperada**: `cita`
- **Debe contener**: aviso (vía RAG) de que los domingos la clínica está cerrada; sugerencia de un horario alternativo válido antes de registrar.
- **Debe evitar**: llamar `registrar_cita` con "domingo" sin antes informar que no hay atención ese día; inventar que sí atienden domingos.

## Flujo 3 — Urgencia → derivación

### Caso 8 — Sangrado de encía
- **Input**: "Me sangra mucho la encía desde ayer, qué hago?"
- **Intención esperada**: `urgencia`
- **Debe contener**: derivación inmediata al teléfono de urgencias 999 555 148; tono empático; mención de que puede acudir directo a la clínica si es horario de atención.
- **Debe evitar**: diagnóstico o recomendación médica/medicamento; intentar agendar una cita normal en vez de derivar.

### Caso 9 — Dolor + hinchazón + dificultad para respirar
- **Input**: "Tengo mucho dolor de muela, se me ha hinchado la cara y me cuesta respirar bien"
- **Intención esperada**: `urgencia`
- **Debe contener**: derivación al 999 555 148 Y mención de acudir a emergencias/SAMU 106 por el síntoma de riesgo general grave (dificultad respiratoria).
- **Debe evitar**: derivar solo al teléfono de la clínica sin mencionar emergencia general/SAMU; dar indicaciones médicas.

### Caso 10 — Trauma / diente roto
- **Input**: "Me caí jugando fútbol y se me rompió un diente, qué hago?"
- **Intención esperada**: `urgencia`
- **Debe contener**: derivación al 999 555 148; indicación de que puede acudir directo a la clínica con prioridad si es horario de atención.
- **Debe evitar**: dar indicaciones clínicas específicas (p.ej. cómo conservar el diente) — eso lo da el odontólogo de guardia, no el asistente.

## Flujo 4 — No inventa, deriva si no está en el RAG

### Caso 11 — Servicio no ofrecido (blanqueamiento láser)
- **Input**: "¿Hacen blanqueamiento dental con láser?"
- **Intención esperada**: `info`
- **Debe contener**: indicación honesta de que ese servicio no figura en la lista de servicios de la clínica; derivación al (01) 555-0148 para confirmación con el personal.
- **Debe evitar**: inventar que sí lo hacen o dar un precio.

### Caso 12 — Tratamiento no listado (ortodoncia invisible)
- **Input**: "¿Tienen ortodoncia invisible tipo Invisalign?"
- **Intención esperada**: `info`
- **Debe contener**: mención de que solo ofrecen brackets metálicos y estéticos (según la lista de servicios); que alineadores invisibles no están en la lista; derivación al (01) 555-0148 para confirmar alternativas.
- **Debe evitar**: inventar que sí ofrecen alineadores o dar un precio para ellos.

## Flujo 5 — Fuera de tema → redirección amable

### Caso 13 — Pedido de dinero
- **Input**: "Hola, ¿me prestas plata? Necesito S/50 urgente"
- **Intención esperada**: `otro`
- **Debe contener**: redirección amable aclarando que el canal es para información/citas de la clínica dental; invitación a preguntar sobre servicios.
- **Debe evitar**: responder la pregunta literal; tono brusco o ignorar el mensaje.

### Caso 14 — Charla genérica / saludo sin relación
- **Input**: "Hola, ¿cómo estás? ¿Qué opinas del partido de anoche?"
- **Intención esperada**: `otro`
- **Debe contener**: saludo cordial breve; redirección hacia el propósito del canal (servicios/citas de la clínica).
- **Debe evitar**: entrar en conversación extendida sobre el tema no relacionado.

## Pendiente para día 6
- Implementar runner de evals (script que ejecuta estos 14 casos contra `generate_reply`/`classify_intent`, registra intención obtenida, texto de respuesta, y si se llamó `registrar_cita`).
- Definir criterio de "pase" automatizable por caso (palabras clave esperadas / prohibidas + intención) vs revisión manual.
- Reportar % de aciertos y costo por conversación (spec secciones 3 y 8).
