"""Adapter tests against a mocked HTTP transport (no real API calls are made)."""
import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.llm import base
from app.llm.base import FatalLLMError, LLMError
from app.llm.factory import get_llm_client
from app.llm.gemini import GeminiClient
from app.llm.openai_compat import OpenAICompatClient


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def fast(_):
        return None

    monkeypatch.setattr(base.asyncio, "sleep", fast)


def with_transport(client, handler):
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


def test_gemini_request_shape_and_parsing():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["key"] = req.headers.get("x-goog-api-key")
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"a": 1}'}]}}]})

    c = with_transport(GeminiClient("SECRET", "some-model"), handler)
    out = asyncio.run(c.complete_json("SYS", "USER"))
    assert out == '{"a": 1}'
    assert "SECRET" not in seen["url"]            # key never in the URL
    assert seen["key"] == "SECRET"
    assert seen["url"].endswith("/models/some-model:generateContent")
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_safety_block_is_not_retryable():
    c = with_transport(
        GeminiClient("k", "m"),
        lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
    )
    with pytest.raises(LLMError) as e:
        asyncio.run(c.complete_json("s", "u"))
    assert e.value.retryable is False and "SAFETY" in str(e.value)


def test_bad_key_is_fatal_and_message_hides_key():
    c = with_transport(
        GeminiClient("SECRET-KEY", "m"),
        lambda r: httpx.Response(403, json={"error": {"message": "API key not valid"}}),
    )
    with pytest.raises(FatalLLMError) as e:
        asyncio.run(c.complete_json("s", "u"))
    assert "SECRET-KEY" not in str(e.value) and "403" in str(e.value)


def test_transient_errors_are_retried_then_succeed():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    c = with_transport(OpenAICompatClient("k", "m"), handler)
    assert asyncio.run(c.complete_json("s", "u")) == "{}"
    assert calls["n"] == 3


def test_transient_errors_give_up_after_retries():
    c = with_transport(OpenAICompatClient("k", "m"), lambda r: httpx.Response(429, json={"error": "slow down"}))
    with pytest.raises(LLMError) as e:
        asyncio.run(c.complete_json("s", "u"))
    assert e.value.retryable is True


def test_openai_compat_request_shape():
    seen = {}

    def handler(req):
        seen["auth"] = req.headers["authorization"]
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    c = with_transport(OpenAICompatClient("tok", "gpt-x", base_url="https://example.test/v1/"), handler)
    asyncio.run(c.complete_json("SYS", "USER"))
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["auth"] == "Bearer tok"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "SYS"}
    assert seen["body"]["response_format"] == {"type": "json_object"}


def test_network_failure_is_an_llm_error():
    def handler(req):
        raise httpx.ConnectError("boom")

    c = with_transport(GeminiClient("k", "m"), handler)
    with pytest.raises(LLMError):
        asyncio.run(c.complete_json("s", "u"))


def test_factory():
    assert get_llm_client(Settings(llm_api_key="", llm_model="")) is None
    assert get_llm_client(Settings(llm_api_key="k", llm_model="")) is None      # model required
    assert isinstance(get_llm_client(Settings(llm_api_key="k", llm_model="m")), GeminiClient)
    assert isinstance(
        get_llm_client(Settings(llm_api_key="k", llm_model="m", llm_provider="openai_compat")),
        OpenAICompatClient,
    )
    with pytest.raises(ValueError):
        get_llm_client(Settings(llm_api_key="k", llm_model="m", llm_provider="nope"))
