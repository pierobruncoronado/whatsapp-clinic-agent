"""Interactive console entry point for the WhatsApp clinic agent (dev tool).

Run with: python -m src.cli
Type "salir" to exit.
"""

import logging

from src.agent import generate_reply
from src.classifier import classify_intent
from src.retrieval import retrieve_context

MAX_HISTORY_TURNS = 10
EXIT_WORDS = {"salir", "exit", "quit"}


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    print("Agente de Clinica Dental Sonrie. Escribe 'salir' para terminar.\n")

    history: list[dict] = []

    while True:
        user_message = input("Paciente: ").strip()
        if not user_message:
            continue
        if user_message.lower() in EXIT_WORDS:
            print("Agente: Gracias por escribir. Hasta pronto.")
            break

        intent = classify_intent(user_message)
        retrieved_context = retrieve_context(user_message)
        reply = generate_reply(user_message, intent, history, retrieved_context)

        print(f"[intencion: {intent}]")
        print(f"Agente: {reply}\n")

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": reply})
        history = history[-(MAX_HISTORY_TURNS * 2):]


if __name__ == "__main__":
    main()
