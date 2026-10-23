from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from triage.providers.anthropic_provider import AnthropicProvider
from triage.providers.base import FatalProviderError, LLMParams, RefusalError, TransientProviderError

PARAMS = LLMParams(model="claude-haiku-5-5", temperature=0.0, max_tokens=600, timeout_s=30.0)
SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeMessages:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.last_kwargs = result, error, None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self.error:
            raise self.error
        return self.result


def _client(**kw):
    return SimpleNamespace(messages=FakeMessages(**kw))


def _ok():
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"a":1}')],
        usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        model="claude-haiku-5-5",
        stop_reason="end_turn",
    )


def _status_error(cls, code):
    return cls("boom", response=httpx2.Response(code, request=REQUEST), body=None)


def test_maps_response_and_usage():
    client = _client(result=_ok())
    r = AnthropicProvider("k", client=client).complete("sys", [{"role": "user", "content": "hola"}], PARAMS)
    assert r.text == '{"a":1}' and (r.input_tokens, r.output_tokens) == (12, 7) and r.latency_s >= 0
    kw = client.messages.last_kwargs
    assert kw["system"] == "sys" and kw["model"] == "claude-haiku-5-5" and kw["max_tokens"] == 600


def test_does_not_send_sampling_params():
    client = _client(result=_ok())
    AnthropicProvider("k", client=client).complete("s", [{"role": "user", "content": "x"}], PARAMS)
    assert "temperature" not in client.messages.last_kwargs


def test_json_schema_uses_native_structured_output():
    client = _client(result=_ok())
    params = LLMParams(**{**PARAMS.__dict__, "json_schema": SCHEMA})
    AnthropicProvider("k", client=client).complete("s", [{"role": "user", "content": "x"}], params)
    fmt = client.messages.last_kwargs["output_config"]["format"]
    assert fmt["type"] == "json_schema" and fmt["schema"] == SCHEMA


def test_rate_limit_maps_to_transient():
    client = _client(error=_status_error(anthropic.RateLimitError, 429))
    with pytest.raises(TransientProviderError):
        AnthropicProvider("k", client=client).complete("s", [{"role": "user", "content": "x"}], PARAMS)


def test_server_error_maps_to_transient():
    client = _client(error=_status_error(anthropic.InternalServerError, 503))
    with pytest.raises(TransientProviderError):
        AnthropicProvider("k", client=client).complete("s", [{"role": "user", "content": "x"}], PARAMS)


def test_timeout_maps_to_transient():
    client = _client(error=anthropic.APITimeoutError(request=REQUEST))
    with pytest.raises(TransientProviderError):
        AnthropicProvider("k", client=client).complete("s", [{"role": "user", "content": "x"}], PARAMS)


def test_auth_error_maps_to_fatal():
    client = _client(error=_status_error(anthropic.AuthenticationError, 401))
    with pytest.raises(FatalProviderError):
        AnthropicProvider("k", client=client).complete("s", [{"role": "user", "content": "x"}], PARAMS)


def test_refusal_is_fatal():
    refused = _ok()
    refused.stop_reason, refused.content = "refusal", []
    with pytest.raises(RefusalError):
        AnthropicProvider("k", client=_client(result=refused)).complete(
            "s", [{"role": "user", "content": "x"}], PARAMS
        )
