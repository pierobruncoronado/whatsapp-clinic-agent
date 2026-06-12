# Clinic knowledge base (RAG source documents)

Fictional but realistic dental clinic in Lima ("Clínica Dental Altavista", San Borja). These documents are the **single source of truth** for the agent's RAG pipeline (Phase 3 / Day 3). All names, addresses, phone numbers and prices are invented for demo purposes.

## Files
| File | Content | Feeds spec flow |
|---|---|---|
| `01-servicios-y-precios.md` | Services catalog with prices in soles | Flow 1 (price questions) |
| `02-horarios-ubicacion-contacto.md` | Hours, location, contact channels | Flow 1 (info questions) |
| `03-preguntas-frecuentes.md` | FAQ: payments, first visit, treatments | Flow 1 |
| `04-politica-de-citas.md` | How appointments work (name + phone + time preference) | Flow 2 (lead capture) |
| `05-protocolo-urgencias.md` | What counts as an emergency + derivation rules | Flow 3 (urgency derivation) |

## Deliberate design decisions (do not "fix")
1. **Intentional knowledge gap — no teeth whitening.** The clinic catalog deliberately does NOT include "blanqueamiento" (laser or otherwise). This is the anti-hallucination test from the spec (flow 4): when asked "¿Hacen blanqueamiento con láser?", the agent must find nothing in RAG and derive to a human instead of inventing. Do not add whitening to the catalog — it would break eval case 4.
2. **Explicit derivation rule inside the docs** (`01` footer, `05`): the documents themselves instruct derivation for unlisted treatments, reinforcing the system prompt at the retrieval level.
3. **Appointment policy matches the agent's capture flow**: the three fields in `04-politica-de-citas.md` (nombre, teléfono, preferencia horaria) are exactly the columns of the `leads` table in the spec — the RAG content and the tool schema stay consistent.
4. **Phone numbers are fictional** (555-range and 999 555 148) and the email uses a `-demo` domain to avoid colliding with any real business.

## Replacing with a real clinic (post-v1)
Swap these five files with the real clinic's content keeping the same structure, re-run the ingestion pipeline (chunking → embeddings → pgvector), and re-run the eval suite. No code changes should be needed.
