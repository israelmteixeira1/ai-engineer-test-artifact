import argparse
import os
import uuid

import anthropic
from dotenv import load_dotenv

from .agent import DEFAULT_MODEL, Agent
from .data import ROOT, load_policies, load_store
from .store import ConversationStore


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Empório da Música customer-service agent")
    parser.add_argument("--session", help="Session id; reuse it to continue a conversation")
    parser.add_argument("--debug", action="store_true", help="Show tool calls and results")
    args = parser.parse_args()
    session = args.session or uuid.uuid4().hex[:8]

    def show_tool(name, tool_args, result):
        print(f"  [tool] {name} {tool_args}\n         -> {result}")

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. See README.")

    agent = Agent(
        anthropic.Anthropic(), load_store(), load_policies(), ConversationStore(ROOT / ".state" / "emporio.db"),
        session, os.getenv("EMPORIO_MODEL", DEFAULT_MODEL), show_tool if args.debug else None,
    )
    print(f"Empório da Música | sessão {session} | digite 'sair' para encerrar\n")
    while True:
        try:
            text = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text.lower() in {"sair", "exit", "quit"}:
            return
        if text:
            try:
                print(f"\nTom: {agent.reply(text)}\n")
            except anthropic.AuthenticationError:
                raise SystemExit("Invalid ANTHROPIC_API_KEY.") from None


if __name__ == "__main__":
    main()
