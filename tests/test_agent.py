from datetime import datetime
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest
from anthropic.types.beta import BetaMessage

from emporio.agent import ERROR_REPLY, Agent
from emporio.clock import store_context
from emporio.data import load_policies, load_store
from emporio.store import ConversationStore


def message(stop_reason, *content):
    return BetaMessage.model_validate({
        "id": "msg", "type": "message", "role": "assistant", "model": "m", "stop_reason": stop_reason,
        "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}, "content": list(content),
    })


TEXT = {"type": "text", "text": "Olá!"}
THINK = {"type": "thinking", "thinking": "", "signature": "sig"}
CALL = {"type": "tool_use", "id": "t1", "name": "buscar_produtos", "input": {"termo": "Takamine GD20"}}


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_agent(client, conversations=None):
    return Agent(client, load_store(), load_policies(), conversations or ConversationStore(), "s", "m")


def status_error(cls, code):
    request = httpx.Request("POST", "http://x")
    return cls("error", response=httpx.Response(code, request=request), body=None)


def test_tool_round_then_answer_preserves_blocks():
    client = FakeClient(message("tool_use", THINK, CALL), message("end_turn", TEXT))
    conversations = ConversationStore()
    assert make_agent(client, conversations).reply("Quanto custa?") == "Olá!"
    history = conversations.load("s")
    assert [m["role"] for m in history] == ["user", "system", "assistant", "user", "assistant"]
    assert history[2]["content"][0]["signature"] == "sig"
    result = history[3]["content"][0]
    assert result["tool_use_id"] == "t1" and "2199" in result["content"]


def test_bad_tool_input_returns_error_result_and_continues():
    bad = {**CALL, "input": {"campo_inexistente": 1}}
    client = FakeClient(message("tool_use", bad), message("end_turn", TEXT))
    conversations = ConversationStore()
    make_agent(client, conversations).reply("x")
    assert conversations.load("s")[3]["content"][0]["is_error"] is True


def test_history_is_resumed_and_only_appended():
    conversations = ConversationStore()
    make_agent(FakeClient(message("end_turn", TEXT)), conversations).reply("um")
    first = conversations.load("s")
    client = FakeClient(message("end_turn", TEXT))
    make_agent(client, conversations).reply("dois")
    assert client.requests[0]["messages"][: len(first)] == first


def test_server_error_keeps_history_clean():
    conversations = ConversationStore()
    client = FakeClient(message("tool_use", CALL), status_error(anthropic.InternalServerError, 500))
    assert make_agent(client, conversations).reply("x") == ERROR_REPLY
    assert conversations.load("s") == []


def test_auth_error_is_not_hidden():
    with pytest.raises(anthropic.AuthenticationError):
        make_agent(FakeClient(status_error(anthropic.AuthenticationError, 401))).reply("x")


def test_tool_loop_is_bounded():
    client = FakeClient(*[message("tool_use", CALL) for _ in range(8)])
    assert make_agent(client).reply("x") == ERROR_REPLY


def test_store_context_hours():
    assert "aberta até 13:00" in store_context(datetime(2026, 10, 31, 10, 0))  # Saturday
    assert "reabre segunda-feira, 02/11 às 09:00" in store_context(datetime(2026, 10, 31, 20, 0))
    assert "reabre segunda-feira" in store_context(datetime(2026, 11, 1, 8, 0))  # Sunday


def test_wrongly_typed_tool_input_does_not_crash():
    bad = {**CALL, "name": "consultar_pedido", "input": {"numero_pedido": 6, "email": 123}}
    conversations = ConversationStore()
    assert make_agent(FakeClient(message("tool_use", bad), message("end_turn", TEXT)), conversations).reply("x") == "Olá!"
    assert conversations.load("s")[3]["content"][0]["is_error"] is True
