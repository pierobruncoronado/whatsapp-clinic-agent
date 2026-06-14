"""Eval runner for the 14 cases designed in docs/eval_cases.md (dia 6).

Runs each case against classify_intent + generate_reply, checks automatable
pass criteria (intent match, required/forbidden text patterns, registrar_cita
calls), and reports the overall pass rate and average cost per conversation
(Haiku 4.5 pricing: $1.00/1M input tokens, $5.00/1M output tokens).

Voyage AI free tier is 3 requests/minute and retrieve_context (called once
per generate_reply call) embeds the query via Voyage, so this run sleeps
between turns and retries once with a longer backoff on embedding failure.

Run with: python -m scripts.run_evals
"""

import logging
import re
import sys
import time

# Windows console default encoding (cp1252) can't print emoji/some accents
# that the model may include in its replies.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import src.agent as agent_module
import src.retrieval as retrieval_module
from src.anthropic_client import client
from src.classifier import classify_intent
from src.embeddings import embed_query as real_embed_query

logging.basicConfig(level=logging.WARNING)

HAIKU_INPUT_COST_PER_TOKEN = 1.00 / 1_000_000
HAIKU_OUTPUT_COST_PER_TOKEN = 5.00 / 1_000_000

VOYAGE_SLEEP_SECONDS = 21
VOYAGE_RETRY_SLEEP_SECONDS = 60

# Each case has one entry per turn in contains/avoid/expected_intents/tool_calls.
# contains/avoid items are either a regex string (must/must not match) or a
# list of regex strings (OR group: at least one must/must not match).
# tool_calls items: None (no check), False (registrar_cita must NOT be
# called), or a dict of field -> regex the recorded registrar_cita input
# must match.
CASES = [
    {
        "id": 1,
        "name": "Precio de limpieza dental",
        "turns": ["¿Cuánto cuesta una limpieza dental?"],
        "expected_intents": ["info"],
        "contains": [[r"s/\.?\s?120", [r"agendar", r"reservar", r"programar"]]],
        "avoid": [[]],
        "tool_calls": [None],
    },
    {
        "id": 2,
        "name": "Horario de sábado",
        "turns": ["¿A qué hora abren los sábados?"],
        "expected_intents": ["info"],
        "contains": [[
            r"s[aá]bados?",
            [r"9:00\s*a\.?\s?m\.?", r"9\s*am"],
            [r"2:00\s*p\.?\s?m\.?", r"2\s*pm"],
            [r"1:00\s*p\.?\s?m\.?", r"1\s*pm", r"una\s+(de\s+la\s+tarde|pm)"],
        ]],
        "avoid": [[
            r"8:00\s*p\.?\s?m\.?",
            r"8\s*pm",
            r"domingo.{0,30}(atendemos|abrimos|abierto|atenci[oó]n|9|10|11|disponible)",
        ]],
        "tool_calls": [None],
    },
    {
        "id": 3,
        "name": "Ubicación y estacionamiento",
        "turns": ["¿Dónde están ubicados y tienen estacionamiento?"],
        "expected_intents": ["info"],
        "contains": [[
            r"san\s+borja\s+norte\s*1245",
            [r"4\s+(cocheras|espacios|estacionamientos|plazas)"],
            r"sujet[ao]s?\s+a\s+disponibilidad",
            r"media\s+cuadra",
        ]],
        "avoid": [[]],
        "tool_calls": [None],
    },
    {
        "id": 4,
        "name": "Medio de pago + precio de endodoncia",
        "turns": ["¿Aceptan Yape? Quiero hacerme una endodoncia"],
        "expected_intents": ["info"],
        "contains": [[
            r"yape",
            [r"480", r"650", r"evaluaci[oó]n", r"seg[uú]n\s+la\s+pieza", r"depende"],
        ]],
        "avoid": [[]],
        "tool_calls": [None],
    },
    {
        "id": 5,
        "name": "Datos completos en un solo mensaje",
        "turns": [
            "Quiero una cita para limpieza dental el martes en la tarde. "
            "Soy Carlos Mendoza, mi número es 987654321"
        ],
        "expected_intents": ["cita"],
        "contains": [[
            [r"registr", r"qued[oó]\s+registrad", r"solicitud"],
            [r"d[ií]a\s+h[áa]bil", r"pr[oó]ximo\s+d[ií]a", r"siguiente\s+d[ií]a"],
            r"confirm",
        ]],
        "avoid": [[
            r"(tu\s+cita\s+(ya\s+)?(est[aá]\s+)?|qued[oó]\s+)(confirmada|agendada|programada)\s+para\s+las",
            r"c[uú]al\s+es\s+tu\s+nombre",
            r"cu[aá]l\s+es\s+tu\s+(n[uú]mero|tel[eé]fono)",
        ]],
        "tool_calls": [{
            "nombre": r"carlos\s+mendoza",
            "telefono": r"987654321",
            "preferencia_horaria": r"martes.{0,15}tarde",
            "servicio": r"limpieza",
        }],
    },
    {
        "id": 6,
        "name": "Datos parciales en dos turnos (memoria de sesión)",
        "turns": [
            "Quiero agendar una cita",
            "Me llamo Ana Torres, 912345678, el viernes en la mañana",
        ],
        "expected_intents": ["cita", "cita"],
        "contains": [
            [r"nombre", r"tel[eé]fono", [r"d[ií]a", r"horario", r"prefer", r"turno"]],
            [[r"registr", r"qued[oó]\s+registrad", r"confirm"]],
        ],
        "avoid": [
            [],
            [r"c[uú]al\s+es\s+tu\s+nombre", r"en\s+qu[eé]\s+(te\s+)?puedo\s+ayudar", r"en\s+qu[eé]\s+te\s+ayudo"],
        ],
        "tool_calls": [
            False,
            {
                "nombre": r"ana\s+torres",
                "telefono": r"912345678",
                "preferencia_horaria": r"viernes.{0,20}(ma[ñn]ana)",
            },
        ],
    },
    {
        "id": 7,
        "name": "Preferencia fuera de horario (domingo)",
        "turns": ["Quiero una cita el domingo a las 10am para una consulta"],
        "expected_intents": ["cita"],
        "contains": [[
            r"domingo",
            [r"cerrad[oa]", r"no\s+(atendemos|hay\s+atenci[oó]n|laboramos|abrimos)"],
            [r"lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|otro\s+d[ií]a|alternativ"],
        ]],
        "avoid": [[
            r"domingo.{0,30}(atendemos|abrimos|abierto|atenci[oó]n|9|10|11|disponible)",
        ]],
        "tool_calls": [False],
    },
    {
        "id": 8,
        "name": "Sangrado de encía",
        "turns": ["Me sangra mucho la encía desde ayer, qué hago?"],
        "expected_intents": ["urgencia"],
        "contains": [[
            r"999\s*555\s*148",
            [r"lament|entiendo|tranquil|sentimos"],
            [r"acudir|venir|pasar|acercarte"],
        ]],
        "avoid": [[
            r"ibuprofeno|paracetamol|antibi[oó]tico|enjuagu?e?\s+con|aplica(r)?\s+hielo|diagn[oó]stico",
        ]],
        "tool_calls": [False],
    },
    {
        "id": 9,
        "name": "Dolor + hinchazón + dificultad para respirar",
        "turns": ["Tengo mucho dolor de muela, se me ha hinchado la cara y me cuesta respirar bien"],
        "expected_intents": ["urgencia"],
        "contains": [[
            r"999\s*555\s*148",
            [r"samu", r"106", r"emergencia"],
        ]],
        "avoid": [[
            r"ibuprofeno|paracetamol|antibi[oó]tico|enjuagu?e?\s+con|aplica(r)?\s+hielo|diagn[oó]stico",
        ]],
        "tool_calls": [False],
    },
    {
        "id": 10,
        "name": "Trauma / diente roto",
        "turns": ["Me caí jugando fútbol y se me rompió un diente, qué hago?"],
        "expected_intents": ["urgencia"],
        "contains": [[
            r"999\s*555\s*148",
            [r"prioridad|de\s+inmediato|cuanto\s+antes|lo\s+antes\s+posible"],
        ]],
        "avoid": [[
            r"leche|conservar\s+el\s+diente|envuelv|no\s+toques?\s+la\s+ra[ií]z|agua\s+tibia",
        ]],
        "tool_calls": [False],
    },
    {
        "id": 11,
        "name": "Servicio no ofrecido (blanqueamiento láser)",
        "turns": ["¿Hacen blanqueamiento dental con láser?"],
        "expected_intents": ["info"],
        "contains": [[
            [
                r"no\s+(ofrecemos|contamos\s+con|figura|tenemos|realizamos|brindamos|menciona)",
                r"no\s+tengo\s+informaci[oó]n.{0,30}(servicios|ofrecemos)",
                r"no\s+(est[aá]|aparece).{0,80}(disponible|en\s+(la\s+|nuestra\s+)?lista|entre\s+(los|nuestros)\s+servicios)",
            ],
            r"555-0148",
        ]],
        "avoid": [[
            r"\bs[ií],\s*(hacemos|ofrecemos|contamos|realizamos)",
            r"s/\s?\d",
        ]],
        "tool_calls": [None],
    },
    {
        "id": 12,
        "name": "Tratamiento no listado (ortodoncia invisible)",
        "turns": ["¿Tienen ortodoncia invisible tipo Invisalign?"],
        "expected_intents": ["info"],
        "contains": [[
            r"brackets?",
            [
                r"no\s+(ofrecemos|contamos|figura|tenemos|realizamos|menciona)",
                r"no\s+(espec[ií]ficamente|aparece|est[aá]).{0,30}(invisalign|alineadores|invisible)",
            ],
            r"555-0148",
        ]],
        "avoid": [[
            r"\bs[ií],\s*(hacemos|ofrecemos|contamos|realizamos).{0,30}(invisalign|alineadores|invisible)",
            r"s/\s?\d+.{0,20}(invisalign|alineadores|invisible)",
        ]],
        "tool_calls": [None],
    },
    {
        "id": 13,
        "name": "Pedido de dinero",
        "turns": ["Hola, ¿me prestas plata? Necesito S/50 urgente"],
        "expected_intents": ["otro"],
        "contains": [[
            [r"cl[ií]nica|dental"],
            [r"servicios?|citas?|informaci[oó]n"],
        ]],
        "avoid": [[
            r"te\s+presto|aqu[ií]\s+tienes|claro,?\s+te\s+env[ií]o",
        ]],
        "tool_calls": [None],
    },
    {
        "id": 14,
        "name": "Charla genérica / saludo sin relación",
        "turns": ["Hola, ¿cómo estás? ¿Qué opinas del partido de anoche?"],
        "expected_intents": ["otro"],
        "contains": [[
            [r"hola|buen[oa]s?\s+d[ií]as|qu[eé]\s+tal"],
            [r"servicios?|citas?|cl[ií]nica|ayudarte"],
        ]],
        "avoid": [[
            r"qu[eé]\s+equipo|tu\s+equipo|qui[eé]n\s+gan[oó]|c[oó]mo\s+qued[oó]|viste\s+el\s+partido"
            r"|me\s+gusta\s+el\s+f[uú]tbol|soy\s+hincha",
        ]],
        "tool_calls": [None],
    },
]


def _matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def _check_contains(patterns: list, text: str) -> list[str]:
    """Return the patterns/groups that did NOT match (empty if all matched)."""
    failed = []
    for item in patterns:
        if isinstance(item, list):
            if not any(_matches(p, text) for p in item):
                failed.append(" | ".join(item))
        elif not _matches(item, text):
            failed.append(item)
    return failed


def _check_avoid(patterns: list, text: str) -> list[str]:
    """Return the forbidden patterns that DID match (empty if none matched)."""
    failed = []
    for item in patterns:
        if isinstance(item, list):
            matched = [p for p in item if _matches(p, text)]
            failed.extend(matched)
        elif _matches(item, text):
            failed.append(item)
    return failed


def _check_tool_call(expectation, recorded_calls: list[dict]) -> str | None:
    """Return None if the tool-call expectation is met, else a reason string."""
    if expectation is None:
        return None
    if expectation is False:
        if recorded_calls:
            return f"registrar_cita no debia llamarse, se llamo con {recorded_calls}"
        return None
    if not recorded_calls:
        return "registrar_cita no fue llamado"
    call = recorded_calls[0]
    for field, pattern in expectation.items():
        value = str(call.get(field, ""))
        if not _matches(pattern, value):
            return f"campo '{field}'='{value}' no coincide con /{pattern}/"
    return None


def _embed_query_with_retry(text: str) -> list[float]:
    """Embed `text`, retrying once after a long backoff on Voyage rate limits."""
    try:
        return real_embed_query(text)
    except Exception:
        logging.warning("embed_query failed, retrying after %ss", VOYAGE_RETRY_SLEEP_SECONDS)
        time.sleep(VOYAGE_RETRY_SLEEP_SECONDS)
        return real_embed_query(text)


def main() -> None:
    original_create = client.messages.create
    original_insert_lead = agent_module.insert_lead
    original_embed_query = retrieval_module.embed_query

    usage_records: list = []
    recorded_tool_calls: list[dict] = []

    def recording_create(*args, **kwargs):
        response = original_create(*args, **kwargs)
        usage_records.append(response.usage)
        return response

    def fake_insert_lead(nombre, telefono, servicio, preferencia_horaria):
        recorded_tool_calls.append({
            "nombre": nombre,
            "telefono": telefono,
            "servicio": servicio,
            "preferencia_horaria": preferencia_horaria,
        })
        return True

    client.messages.create = recording_create
    agent_module.insert_lead = fake_insert_lead
    retrieval_module.embed_query = _embed_query_with_retry

    results = []
    total_cost = 0.0
    first_call = True

    try:
        for case in CASES:
            history: list[dict] = []
            case_failures = []
            case_cost = 0.0
            turn_texts = []

            for turn_idx, message in enumerate(case["turns"]):
                if not first_call:
                    time.sleep(VOYAGE_SLEEP_SECONDS)
                first_call = False

                usage_records.clear()
                recorded_tool_calls.clear()

                intent = classify_intent(message)
                retrieved_context = retrieval_module.retrieve_context(message)
                reply = agent_module.generate_reply(message, intent, history, retrieved_context)

                turn_texts.append(reply)

                expected_intent = case["expected_intents"][turn_idx]
                if intent != expected_intent:
                    case_failures.append(
                        f"turno {turn_idx + 1}: intencion esperada={expected_intent}, obtenida={intent}"
                    )

                missing = _check_contains(case["contains"][turn_idx], reply)
                for pattern in missing:
                    case_failures.append(f"turno {turn_idx + 1}: falta patron /{pattern}/")

                forbidden = _check_avoid(case["avoid"][turn_idx], reply)
                for pattern in forbidden:
                    case_failures.append(f"turno {turn_idx + 1}: contiene patron prohibido /{pattern}/")

                tool_issue = _check_tool_call(case["tool_calls"][turn_idx], list(recorded_tool_calls))
                if tool_issue:
                    case_failures.append(f"turno {turn_idx + 1}: {tool_issue}")

                for usage in usage_records:
                    case_cost += (
                        usage.input_tokens * HAIKU_INPUT_COST_PER_TOKEN
                        + usage.output_tokens * HAIKU_OUTPUT_COST_PER_TOKEN
                    )

                history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": reply},
                ]

            total_cost += case_cost
            results.append({
                "id": case["id"],
                "name": case["name"],
                "passed": not case_failures,
                "failures": case_failures,
                "turn_texts": turn_texts,
                "cost": case_cost,
            })
    finally:
        client.messages.create = original_create
        agent_module.insert_lead = original_insert_lead
        retrieval_module.embed_query = original_embed_query

    # --- Report ---
    passed_count = sum(1 for r in results if r["passed"])
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"\n=== Caso {r['id']} - {r['name']} [{status}] (costo: ${r['cost']:.5f}) ===")
        for failure in r["failures"]:
            print(f"  - {failure}")
        for i, text in enumerate(r["turn_texts"], start=1):
            print(f"  [turno {i}] {text}")

    pass_rate = passed_count / len(results) * 100
    avg_cost = total_cost / len(results)

    print("\n" + "=" * 60)
    print(f"Resultado: {passed_count}/{len(results)} casos ({pass_rate:.1f}%)")
    print(f"Meta spec: >= 85% ({'CUMPLE' if pass_rate >= 85 else 'NO CUMPLE'})")
    print(f"Costo promedio por conversacion: ${avg_cost:.5f}")
    print(f"Meta spec: < $0.01/conversacion ({'CUMPLE' if avg_cost < 0.01 else 'NO CUMPLE'})")


if __name__ == "__main__":
    main()
