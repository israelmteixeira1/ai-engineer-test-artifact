import json
from collections.abc import Callable

import anthropic

from . import clock
from .data import Store
from .prompts import SYSTEM_PROMPT
from .store import ConversationStore
from .tools import TOOL_DEFINITIONS, Tools

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 8
FALLBACK_BETA = "server-side-fallback-2026-07-01"
CONTACT = "(67) 3341-4444"
ERROR_REPLY = f"Tive um problema técnico aqui e não consegui concluir. Pode tentar de novo? Se preferir, fale com a equipe no {CONTACT}."
REFUSAL_REPLY = f"Não consigo ajudar com isso por aqui. Para outros assuntos da loja, é só falar, ou chame a equipe no {CONTACT}."


class Agent:
    def __init__(self, client, store: Store, policies: dict[str, str], conversations: ConversationStore,
                 session_id: str, model: str = DEFAULT_MODEL,
                 on_tool: Callable[[str, dict, dict], None] | None = None):
        self.client = client
        self.conversations = conversations
        self.session_id = session_id
        self.model = model
        self.on_tool = on_tool
        self.tools = Tools(store, policies, conversations, session_id)

    def _call_model(self, messages: list[dict]):
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=4000,
            output_config={"effort": "medium"},
            cache_control={"type": "ephemeral"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

    def _execute(self, block) -> dict:
        try:
            result = self.tools.run(block.name, dict(block.input))
            is_error = False
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            result = {"erro": f"Parâmetros inválidos: {exc}"}
            is_error = True
        if self.on_tool:
            self.on_tool(block.name, dict(block.input), result)
        payload = {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, ensure_ascii=False)}
        return payload | {"is_error": True} if is_error else payload

    def reply(self, user_text: str) -> str:
        messages = self.conversations.load(self.session_id)
        messages.append({"role": "user", "content": user_text})
        # outside the system prompt to keep the cached prefix stable
        messages.append({"role": "system", "content": clock.store_context(clock.now())})
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response = self._call_model(messages)
                messages.append({
                    "role": "assistant",
                    "content": [b.model_dump(mode="json", exclude_none=True) for b in response.content],
                })
                if response.stop_reason != "tool_use":
                    break
                calls = [b for b in response.content if b.type == "tool_use"]
                messages.append({"role": "user", "content": [self._execute(c) for c in calls]})
            else:
                return ERROR_REPLY
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500 and exc.status_code != 429:
                raise
            return ERROR_REPLY
        except anthropic.APIConnectionError:
            return ERROR_REPLY

        if response.stop_reason == "refusal":
            return REFUSAL_REPLY
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            return ERROR_REPLY
        # saved only here so a failed turn never leaves a dangling tool_use
        self.conversations.save(self.session_id, messages)
        return text
